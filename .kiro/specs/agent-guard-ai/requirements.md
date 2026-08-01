# Requirements Document

## Introduction

AgentGuard.ai is a pre-execution cost guardrail tool for AI agent developers. AI agents routinely burn 32,000–82,000 tokens on a single multi-step MCP tool call — the equivalent work costs roughly 200 tokens as a direct CLI command. Existing billing dashboards only report cost after it is spent. AgentGuard.ai intercepts a tool-call payload before execution, estimates its token cost, classifies it as low/medium/high risk, and — when the cost exceeds a developer-defined budget threshold — calls Amazon Bedrock (Nova Micro) to generate a cheaper CLI or script alternative. Every analysis is logged (without storing the raw payload) and a live dashboard shows cumulative savings.

The MVP scope is: the Analyze endpoint (`POST /v1/analyze-log`) plus the frontend Analyze tab and live savings counter. Everything else (proxy/intercept, full rules management, full metrics table) is stretch.

---

## Glossary

- **System**: The AgentGuard.ai backend application running on AWS Lambda + API Gateway.
- **Dashboard**: The React + Tailwind CSS single-page frontend application.
- **Developer**: An authenticated API user identified by a unique `developer_id`.
- **API_Key**: A secret token issued per Developer, sent in the `X-API-Key` request header.
- **Payload**: The tool-call text (JSON, log lines, or free text) pasted by the Developer for analysis.
- **Token_Estimator**: The component that estimates the token count of a Payload using a character-count heuristic (`character_count / 4`).
- **Risk_Classifier**: The component that maps an estimated token count and cost to a risk level.
- **Risk_Level**: One of `low`, `medium`, `high`, or `unknown`.
- **Budget_Threshold**: A Developer-configured maximum acceptable cost in USD per tool call, stored in the AgentRules DynamoDB table.
- **Alternative_Generator**: The Amazon Bedrock (Nova Micro) integration that returns a cheaper CLI or script alternative for a high-cost Payload.
- **AgentRules**: DynamoDB table with PK `developer_id` storing per-Developer rules (budget threshold, reroute/block preference).
- **InterceptLogs**: DynamoDB table with PK `developer_id` and SK `timestamp` storing per-analysis metrics (no raw Payload text).
- **Analyzer**: The Lambda handler for `POST /v1/analyze-log`.
- **Interceptor**: The Lambda handler for `POST /v1/proxy/intercept` (stretch).
- **MetricsService**: The Lambda handler for `GET /v1/metrics/dashboard`.
- **RulesService**: The Lambda handler for `POST /v1/rules`.
- **SAM**: AWS Serverless Application Model, used for infrastructure-as-code and deployment.
- **Nova_Micro**: The `amazon.nova-micro-v1:0` Amazon Bedrock foundation model used for alternative generation.

---

## Requirements

### Requirement 1: Tool-Call Payload Analysis

**User Story:** As a Developer, I want to paste a tool-call payload or log and receive an instant token-cost estimate with a risk classification, so that I understand the cost impact before the agent executes.

#### Acceptance Criteria

1. WHEN a `POST /v1/analyze-log` request is received with a non-empty `payload` field and a valid `API_Key`, THE Analyzer SHALL return an HTTP 200 response containing `tokens_estimated`, `cost_usd`, `risk_level`, `suggested_alternative`, and `tokens_saved`.
2. THE Token_Estimator SHALL estimate token count as `floor(character_count / 4)`, clearly documented in code as a placeholder to be replaced with a real tokenizer.
3. WHEN `tokens_estimated` is fewer than 1,000, THE Risk_Classifier SHALL set `risk_level` to `"low"`.
4. WHEN `tokens_estimated` is between 1,000 and 9,999 inclusive, THE Risk_Classifier SHALL set `risk_level` to `"medium"`.
5. WHEN `tokens_estimated` is 10,000 or greater, THE Risk_Classifier SHALL set `risk_level` to `"high"`.
6. WHEN a `POST /v1/analyze-log` request is received with an empty or missing `payload` field, THE Analyzer SHALL return an HTTP 400 response with a descriptive error message.
7. IF a Bedrock timeout or service error occurs during alternative generation, THEN THE Analyzer SHALL return an HTTP 200 response with `risk_level` set to `"unknown"`, `suggested_alternative` set to `null`, and a `message` field containing a human-readable explanation of the fallback.
8. THE System SHALL never return an HTTP 5xx response to the client for a Bedrock failure; all Bedrock errors SHALL be caught and handled as specified in criterion 7.

---

### Requirement 2: Cheap-Alternative Generation via Amazon Bedrock

**User Story:** As a Developer, I want to receive a Bedrock-generated cheaper CLI or script alternative when my tool call exceeds my budget threshold, so that I can accomplish the same task at a fraction of the token cost.

#### Acceptance Criteria

1. WHEN `cost_usd` exceeds the Developer's `Budget_Threshold` stored in AgentRules, THE Alternative_Generator SHALL invoke Nova_Micro with a prompt requesting ONLY a JSON object in the form `{"alternative_type": string, "alternative_command": string, "estimated_token_savings_pct": number, "explanation": string}`.
2. WHEN no AgentRules record exists for the Developer, THE Alternative_Generator SHALL use a default `Budget_Threshold` of `0.01` USD.
3. WHEN `cost_usd` does not exceed the `Budget_Threshold`, THE Analyzer SHALL set `suggested_alternative` to `null` and `tokens_saved` to `0`.
4. WHEN the Alternative_Generator receives a valid JSON response from Nova_Micro, THE Analyzer SHALL include the parsed alternative object in the `suggested_alternative` field of the response.
5. IF the Nova_Micro response cannot be parsed as valid JSON, THEN THE Alternative_Generator SHALL log the raw response to CloudWatch and return `null` for `suggested_alternative`.
6. THE Alternative_Generator SHALL set a request timeout of 10 seconds when calling Nova_Micro; IF the timeout is exceeded, THEN THE Analyzer SHALL apply the fallback behavior defined in Requirement 1, criterion 7.

---

### Requirement 3: Analysis Logging (Zero Payload Retention)

**User Story:** As a Developer, I want every analysis to be logged for metrics purposes without storing my raw payload, so that I can review my savings history without risking data leakage.

#### Acceptance Criteria

1. AFTER returning a successful analysis response, THE Analyzer SHALL write a record to InterceptLogs containing `developer_id`, `timestamp` (ISO 8601 UTC), `tokens_estimated`, `cost_usd`, `risk_level`, and `tokens_saved`.
2. THE System SHALL never write the raw `payload` text to InterceptLogs, any other DynamoDB table, CloudWatch Logs, or any other persistent store.
3. WHEN writing to InterceptLogs fails, THE Analyzer SHALL log the DynamoDB error to CloudWatch and return the analysis response to the client unaffected; THE System SHALL not return an error to the client due to a logging failure.

---

### Requirement 4: Developer Rules Configuration

**User Story:** As a Developer, I want to save my budget threshold and preferred action (reroute vs. block) so that the system applies my preferences automatically on every analysis.

#### Acceptance Criteria

1. WHEN a `POST /v1/rules` request is received with a valid `API_Key`, `developer_id`, `budget_threshold_usd` (positive number), and `action` (`"reroute"` or `"block"`), THE RulesService SHALL upsert the record in AgentRules and return HTTP 200 with the saved rule.
2. WHEN `budget_threshold_usd` is zero or negative, THE RulesService SHALL return HTTP 400 with a descriptive error message.
3. WHEN `action` is a value other than `"reroute"` or `"block"`, THE RulesService SHALL return HTTP 400 with a descriptive error message.
4. WHILE a valid AgentRules record exists for a Developer, THE Analyzer SHALL read and apply that Developer's `budget_threshold_usd` for all subsequent analyses.

---

### Requirement 5: Metrics Dashboard API

**User Story:** As a Developer, I want a dashboard API endpoint that returns my cumulative tokens and cost saved, so that I can see the total value AgentGuard.ai has delivered.

#### Acceptance Criteria

1. WHEN a `GET /v1/metrics/dashboard` request is received with a valid `API_Key` and `developer_id` query parameter, THE MetricsService SHALL query all InterceptLogs records for that Developer and return `total_calls_analyzed`, `total_tokens_saved`, `total_cost_saved_usd`, and `recent_calls` (up to the 20 most recent records, ordered by timestamp descending).
2. WHEN no InterceptLogs records exist for the Developer, THE MetricsService SHALL return HTTP 200 with all numeric fields set to `0` and `recent_calls` as an empty array.
3. IF a DynamoDB error occurs during the metrics query, THEN THE MetricsService SHALL return HTTP 200 with a `message` field explaining the temporary unavailability rather than an HTTP 5xx.

---

### Requirement 6: API Key Authentication

**User Story:** As a Developer, I want all API endpoints to require a valid API key, so that my usage data and rules are protected from unauthorized access.

#### Acceptance Criteria

1. THE System SHALL require an `X-API-Key` header on every request to `POST /v1/analyze-log`, `POST /v1/rules`, `GET /v1/metrics/dashboard`, and `POST /v1/proxy/intercept`.
2. WHEN a request is received without an `X-API-Key` header or with an invalid key, THE System SHALL return HTTP 401 with a descriptive error message.
3. THE System SHALL validate API keys against a set of pre-provisioned keys stored in AWS Systems Manager Parameter Store (SSM); THE System SHALL never hard-code API key values in source code or SAM templates.

---

### Requirement 7: Proxy Intercept Endpoint (Stretch)

**User Story:** As a Developer, I want to route my AI agent's tool calls through AgentGuard.ai so that every call is automatically analyzed and potentially rerouted before execution.

#### Acceptance Criteria

1. WHEN a `POST /v1/proxy/intercept` request is received with a valid `API_Key` and a tool-call payload, THE Interceptor SHALL apply the same token estimation and risk classification logic as the Analyzer.
2. WHEN `risk_level` is `"high"` and the Developer's `action` is `"block"`, THE Interceptor SHALL return HTTP 200 with `status: "blocked"` and the `suggested_alternative`.
3. WHEN `risk_level` is `"high"` and the Developer's `action` is `"reroute"`, THE Interceptor SHALL return HTTP 200 with `status: "rerouted"` and the `suggested_alternative`.
4. WHEN `risk_level` is `"low"` or `"medium"`, THE Interceptor SHALL return HTTP 200 with `status: "allowed"` and no alternative.

---

### Requirement 8: Frontend — Analyze Tab

**User Story:** As a Developer, I want a web UI where I can paste a tool-call payload and instantly see the risk badge, cost estimate, and any suggested alternative, so that I can evaluate calls without writing API requests manually.

#### Acceptance Criteria

1. THE Dashboard SHALL render a single-page application with a dark background (near-black) and electric blue (`#3B82F6`) accents.
2. THE Dashboard SHALL display a textarea for pasting a Payload and an "Analyze" button on the Analyze tab.
3. WHEN the Developer clicks "Analyze" with a non-empty textarea, THE Dashboard SHALL call `POST /v1/analyze-log` and display the returned `risk_level` as a color-coded badge: green for `"low"`, yellow for `"medium"`, red for `"high"`, and grey for `"unknown"`.
4. THE Dashboard SHALL display `tokens_estimated` and `cost_usd` in a result card below the textarea.
5. WHEN `suggested_alternative` is non-null, THE Dashboard SHALL display the `alternative_command` in a styled code block and the `explanation` as supporting text.
6. WHEN the API call is in-flight, THE Dashboard SHALL display a loading indicator and disable the "Analyze" button to prevent duplicate submissions.
7. WHEN the API returns an error, THE Dashboard SHALL display a human-readable error message without exposing raw HTTP error codes.

---

### Requirement 9: Frontend — Live Savings Counter

**User Story:** As a Developer, I want to see a live cumulative "Tokens Saved" and "$ Saved" counter at the top of the dashboard, so that I get immediate feedback on the value AgentGuard.ai has delivered.

#### Acceptance Criteria

1. THE Dashboard SHALL display a "Tokens Saved" counter and a "$ Saved" counter in the page header, visible on all tabs.
2. WHEN the Dashboard loads, THE Dashboard SHALL call `GET /v1/metrics/dashboard` to populate the counters with the Developer's current totals.
3. AFTER a successful analysis that returns `tokens_saved` greater than `0`, THE Dashboard SHALL increment the displayed counters immediately without requiring a full page reload.
4. THE Dashboard SHALL display a sparkline chart of tokens saved per call using the `recent_calls` data from the metrics API.

---

### Requirement 10: Frontend — Rules Tab

**User Story:** As a Developer, I want a simple form to set my budget threshold and reroute/block preference, so that I can configure AgentGuard.ai without calling the API directly.

#### Acceptance Criteria

1. THE Dashboard SHALL render a Rules tab containing a numeric input for `Budget_Threshold` in USD and a toggle for `action` (`"reroute"` or `"block"`).
2. WHEN the Developer submits the Rules form with valid values, THE Dashboard SHALL call `POST /v1/rules` and display a success confirmation.
3. WHEN the Rules form is submitted with a non-positive `budget_threshold_usd`, THE Dashboard SHALL display a validation error before making any API call.

---

### Requirement 11: Frontend — Metrics Tab

**User Story:** As a Developer, I want a metrics tab showing a table and chart of past intercepted calls, so that I can review my usage history at a glance.

#### Acceptance Criteria

1. THE Dashboard SHALL render a Metrics tab containing a table of `recent_calls` with columns: timestamp, tokens estimated, cost (USD), risk level, and tokens saved.
2. THE Dashboard SHALL render a bar or line chart of `tokens_saved` per call using the `recent_calls` data.
3. WHEN the Metrics tab is active, THE Dashboard SHALL call `GET /v1/metrics/dashboard` to refresh the data.

---

### Requirement 12: Infrastructure and Deployment

**User Story:** As a Developer, I want AgentGuard.ai deployed on AWS using Free Tier-eligible services, so that the hackathon demo incurs minimal cost.

#### Acceptance Criteria

1. THE System SHALL be deployable via a single `sam deploy` command using an AWS SAM template (`template.yaml`).
2. THE System SHALL use AWS Lambda (Python 3.12) for all backend compute.
3. THE System SHALL use Amazon API Gateway (HTTP API) for all HTTP routing.
4. THE System SHALL use Amazon DynamoDB (on-demand billing mode) for AgentRules and InterceptLogs tables.
5. THE System SHALL use Amazon Bedrock with the `amazon.nova-micro-v1:0` model for alternative generation.
6. THE Dashboard SHALL be hosted as a static site on Amazon S3 with public read access and static website hosting enabled, or on AWS Amplify.
7. THE System SHALL emit structured logs to Amazon CloudWatch Logs via the Lambda execution role.
8. WHERE a CloudWatch Logs error occurs, THE System SHALL continue normal operation and not propagate the logging failure to the client.
