# Implementation Plan: AgentGuard.ai

## Overview

Build a serverless cost-guardrail service for AI agent developers. The backend is Python 3.12 on AWS Lambda, deployed via AWS SAM. The frontend is a React 18 + TypeScript SPA built with Vite and deployed on AWS Amplify. Implementation proceeds in this order: project scaffolding → core Python modules → Lambda handlers → SAM infrastructure → frontend components → integration wiring.

---

## Tasks

- [x] 1. Scaffold project structure and install dependencies
  - Create the directory tree: `src/handlers/`, `src/core/`, `tests/`, `tests/test_integration/`, `frontend/src/`, `frontend/src/api/`, `frontend/src/__tests__/`, `frontend/src/__tests__/components/`, `scripts/`
  - Create `src/requirements.txt` with `boto3`, `botocore`, `hypothesis`
  - Create `frontend/package.json` with React 18, TypeScript, Tailwind CSS, Vite, Vitest, fast-check, React Testing Library dependencies (pinned versions)
  - Create `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tailwind.config.js`
  - Create empty `__init__.py` files under `src/` and `src/handlers/` and `src/core/`
  - _Requirements: 12.1, 12.2_

- [x] 2. Implement core backend modules
  - [x] 2.1 Implement `src/core/token_estimator.py`
    - Write `estimate(payload: str) -> int` returning `len(payload) // 4`
    - Write `estimate_cost(tokens: int) -> float` using `PRICE_PER_1K_INPUT_TOKENS = 0.000035`
    - Add docstring: "NOTE: placeholder heuristic — replace with tiktoken before production"
    - _Requirements: 1.2_

  - [ ]* 2.2 Write property test for token estimator (Property 1)
    - **Property 1: Token estimator is floor division by four**
    - **Validates: Requirements 1.2**
    - File: `tests/test_token_estimator.py`; use `@given(st.text())`, assert `estimate(s) == len(s) // 4`
    - Tag: `# Feature: agent-guard-ai, Property 1: Token estimator is floor division by four`

  - [x] 2.3 Implement `src/core/risk_classifier.py`
    - Write `classify(tokens: int) -> str` with thresholds `LOW_THRESHOLD = 1000`, `HIGH_THRESHOLD = 10000`
    - Return `"low"` / `"medium"` / `"high"` per the boundary table in the design
    - _Requirements: 1.3, 1.4, 1.5_

  - [ ]* 2.4 Write property test for risk classifier (Property 2)
    - **Property 2: Risk classifier covers all token ranges without gaps**
    - **Validates: Requirements 1.3, 1.4, 1.5**
    - File: `tests/test_risk_classifier.py`; use `@given(st.integers(min_value=0))`, assert correct bucket and value in `{"low","medium","high"}`
    - Tag: `# Feature: agent-guard-ai, Property 2: Risk classifier covers all token ranges without gaps`

  - [x] 2.5 Implement `src/core/auth.py`
    - Write `validate_key(api_key: str) -> str | None` using SHA-256 hash of key as SSM path segment `/agentguard/api-keys/{hash}`
    - Implement in-memory per-instance cache (`_cache: dict[str, str] = {}`)
    - Catch `ParameterNotFound` and any SSM client error → return `None` (fail-closed)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 2.6 Implement `src/core/dynamo.py`
    - Write `get_rule(developer_id: str) -> dict` returning `{budget_threshold_usd, action}` with defaults `0.01` / `"reroute"` when no record exists
    - Write `upsert_rule(developer_id, budget_threshold_usd, action) -> None`
    - Write `put_log(developer_id, tokens_estimated, cost_usd, risk_level, tokens_saved) -> None` — never write raw payload
    - Write `query_logs(developer_id, limit=20) -> list[dict]` using `ScanIndexForward=False`
    - Read table names from env vars `AGENT_RULES_TABLE` and `INTERCEPT_LOGS_TABLE`
    - _Requirements: 2.2, 3.1, 3.2, 5.1_

  - [x] 2.7 Implement `src/core/alternative_gen.py`
    - Write `generate(payload: str, tokens_estimated: int) -> tuple[dict | None, int, str | None]`
    - Configure `botocore.config.Config(connect_timeout=10, read_timeout=10)` on the Bedrock client
    - Build prompt from `PROMPT_TEMPLATE` requesting only the strict JSON schema defined in the design
    - Parse response from `response["output"]["message"]["content"][0]["text"]`
    - Handle `ReadTimeoutError` → return `(None, 0, "fallback_timeout")`; `ClientError` → `(None, 0, "fallback_service_error")`; `JSONDecodeError` → log raw response → `(None, 0, "fallback_parse_error")`
    - _Requirements: 2.1, 2.4, 2.5, 2.6_

- [x] 3. Checkpoint — core modules
  - Ensure all core module unit and property tests pass (`python -m pytest tests/test_token_estimator.py tests/test_risk_classifier.py -v`)
  - Ask the user if any questions arise before continuing to handlers.

- [x] 4. Implement Lambda handlers
  - [x] 4.1 Implement `src/handlers/analyze.py`
    - Entry point: `lambda_handler(event, context)`
    - Follow the 9-step flow from the design: auth → validate body → estimate tokens → calculate cost → classify risk → fetch rule → conditionally call alternative_gen → write log (fire-and-forget, catch DynamoDB errors to CW) → return 200
    - Apply Bedrock fallback: set `risk_level="unknown"`, `suggested_alternative=null`, add `message` field on any Bedrock error
    - Never return 5xx; all infrastructure errors are absorbed
    - _Requirements: 1.1, 1.6, 1.7, 1.8, 2.1, 2.2, 2.3, 3.1, 3.3, 6.1, 6.2_

  - [ ]* 4.2 Write property tests for analyze handler (Properties 3, 4, 5, 6, 7)
    - **Property 3: Analysis response always contains all required fields for valid input**
    - **Validates: Requirements 1.1**
    - **Property 4: Empty and whitespace-only payloads are always rejected with 400**
    - **Validates: Requirements 1.6**
    - **Property 5: Bedrock errors never produce a 5xx response**
    - **Validates: Requirements 1.7, 1.8**
    - **Property 6: Alternative generation is triggered if and only if cost exceeds threshold**
    - **Validates: Requirements 2.1, 2.3**
    - **Property 7: Log record never contains the raw payload**
    - **Validates: Requirements 3.1, 3.2**
    - File: `tests/test_analyze_handler.py`; mock SSM, DynamoDB, Bedrock; use `@given` strategies per design Testing Strategy table
    - Tag each: `# Feature: agent-guard-ai, Property {N}: {title}`

  - [x] 4.3 Implement `src/handlers/rules.py`
    - Entry point: `lambda_handler(event, context)`
    - Follow the 4-step flow: auth → validate body (`budget_threshold_usd > 0`, `action in {"reroute","block"}`) → `dynamo.upsert_rule` → return 200 with saved rule + `updated_at`
    - Return 400 with descriptive message for invalid `budget_threshold_usd` or `action`
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2_

  - [ ]* 4.4 Write property tests for rules handler (Properties 8, 9)
    - **Property 8: Rules validation rejects all invalid threshold values**
    - **Validates: Requirements 4.2**
    - **Property 9: Rules validation rejects all non-enum action values**
    - **Validates: Requirements 4.3**
    - File: `tests/test_rules_handler.py`; use `@given(st.floats())` and `@given(st.text())`
    - Tag: `# Feature: agent-guard-ai, Property 8: ...` and `# Feature: agent-guard-ai, Property 9: ...`

  - [x] 4.5 Implement `src/handlers/metrics.py`
    - Entry point: `lambda_handler(event, context)`
    - Follow the 5-step flow: auth → extract `developer_id` from query params → `dynamo.query_logs` → aggregate totals → return 200
    - On empty logs: return 200 with all numeric fields = 0 and `recent_calls = []`
    - On DynamoDB error: return 200 with `{"message": "Metrics temporarily unavailable"}`, log error to CW
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2_

  - [ ]* 4.6 Write property test for metrics handler (Property 10)
    - **Property 10: Metrics aggregation is consistent with stored log records**
    - **Validates: Requirements 5.1**
    - File: `tests/test_metrics_handler.py`; generate lists of synthetic log records, assert `total_calls_analyzed`, `total_tokens_saved`, `total_cost_saved_usd`, and ordering of `recent_calls`
    - Tag: `# Feature: agent-guard-ai, Property 10: Metrics aggregation is consistent with stored log records`

  - [ ]* 4.7 Write property test for auth module (Property 11)
    - **Property 11: Missing or invalid API key returns 401 for all endpoints**
    - **Validates: Requirements 6.1, 6.2**
    - File: `tests/test_auth.py`; use `@given(st.text())`, mock SSM to raise `ParameterNotFound`, assert `validate_key` returns `None`; drive analyze/rules/metrics handlers with no key → assert 401
    - Tag: `# Feature: agent-guard-ai, Property 11: Missing or invalid API key returns 401 for all endpoints`

  - [x] 4.8 Implement `src/handlers/intercept.py` (stretch)
    - Reuse the same analysis flow as `analyze.py`
    - After analysis, lookup Developer `action` from AgentRules and determine `status`: `"blocked"` / `"rerouted"` / `"allowed"` per requirements 7.2–7.4
    - Return 200 with `status`, `risk_level`, `suggested_alternative`, `tokens_estimated`, `cost_usd`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 4.9 Write unit tests for handlers (example-based)
    - Test default budget threshold (0.01) when no AgentRules record exists — Req 2.2
    - Test Bedrock invalid JSON → `suggested_alternative` is null — Req 2.5
    - Test DynamoDB write failure → response still 200 — Req 3.3
    - Test empty metrics result → all zeros — Req 5.2
    - Test DynamoDB read failure → 200 with message — Req 5.3
    - Test proxy intercept status for all (risk, action) combinations — Req 7.2–7.4
    - Files: `tests/test_analyze_handler.py`, `tests/test_rules_handler.py`, `tests/test_metrics_handler.py`

- [x] 5. Checkpoint — handler tests
  - Run `python -m pytest tests/ -v` (excluding integration tests)
  - All handler property tests and unit tests must pass before continuing.
  - Ask the user if questions arise.

- [x] 6. Create the `scripts/seed_demo_key.py` utility
  - Write a standalone Python script that accepts a demo API key value, computes `sha256(key).hexdigest()`, and calls SSM `put_parameter` to store `developer_id = "demo"` at path `/agentguard/api-keys/{hash}`
  - Print the raw key and SSM path to stdout so the operator can note the `VITE_API_KEY` value
  - _Requirements: 6.3_

- [x] 7. Create the SAM infrastructure template
  - Write `template.yaml` with all resources from the design: `AgentGuardApi` (HTTP API with CORS), `AnalyzerFunction`, `RulesFunction`, `MetricsFunction`, IAM policies scoped as designed, `AgentRulesTable`, `InterceptLogsTable`, and `Outputs` section
  - Set `Globals.Function` to `Runtime: python3.12`, `Timeout: 30`, `MemorySize: 256`, env vars for table names and model ID
  - Add `samconfig.toml` with default stack name `agent-guard-ai`, region `us-east-1`, `--resolve-s3`
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.7_

- [x] 8. Implement frontend API client and TypeScript types
  - [x] 8.1 Create `frontend/src/types.ts` with TypeScript interfaces: `AnalysisResult`, `SuggestedAlternative`, `RulesConfig`, `MetricsResponse`, `RecentCall`
    - _Requirements: 8.1, 9.1, 10.1, 11.1_

  - [x] 8.2 Create `frontend/src/api/client.ts`
    - Implement `analyzePayload(developerId, payload)`, `saveRules(config)`, `fetchMetrics(developerId)` using `fetch` with `X-API-Key` and `Content-Type: application/json` headers
    - Read `VITE_API_BASE_URL` and `VITE_API_KEY` from `import.meta.env`
    - _Requirements: 8.1, 8.2, 9.2, 10.2, 11.3_

- [x] 9. Implement React UI components
  - [x] 9.1 Create `frontend/src/components/RiskBadge.tsx`
    - Accept `riskLevel: "low" | "medium" | "high" | "unknown"` prop
    - Render color-coded badge using Tailwind: green/yellow/red/grey per design styling conventions
    - _Requirements: 8.3_

  - [ ]* 9.2 Write unit tests for RiskBadge
    - File: `frontend/src/__tests__/components/RiskBadge.test.tsx`
    - Test all four risk levels render the correct Tailwind class and label text
    - _Requirements: 8.3_

  - [x] 9.3 Create `frontend/src/components/SavingsCounter.tsx`
    - Accept `totalTokensSaved: number` and `totalCostSaved: number` props
    - Render tokens saved and dollars saved in the page header, visible on all tabs
    - _Requirements: 9.1_

  - [x] 9.4 Create `frontend/src/components/AnalyzeTab.tsx`
    - Render `PayloadTextarea`, `AnalyzeButton` (disabled + spinner when `isLoading`), and `ResultCard`
    - `ResultCard` shows `RiskBadge`, `tokens_estimated`, `cost_usd`, `AlternativeBlock` (conditional on non-null `suggested_alternative`), and `ErrorBanner`
    - On "Analyze" click: call `analyzePayload`, update result state, call `onSavingsUpdate` if `tokens_saved > 0`
    - _Requirements: 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [ ]* 9.5 Write unit tests for AnalyzeTab
    - File: `frontend/src/__tests__/components/AnalyzeTab.test.tsx`
    - Test: button disabled while loading, error banner on API error, alternative block shown/hidden based on response
    - _Requirements: 8.5, 8.6, 8.7_

  - [x] 9.6 Create `frontend/src/components/RulesTab.tsx`
    - Render numeric `BudgetThresholdInput` (USD) and `ActionToggle` (`"reroute"` | `"block"`)
    - Client-side validation: show error if `budgetThreshold <= 0` before calling API
    - On save: call `saveRules`, show `SuccessBanner` or `ErrorBanner`
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 9.7 Create `frontend/src/components/MetricsTab.tsx`
    - Render `CallsTable` (columns: timestamp, tokens estimated, cost USD, risk level, tokens saved) from `recent_calls`
    - Render a bar or line chart of `tokens_saved` per call using the `recent_calls` data
    - Fetch `GET /v1/metrics/dashboard` when the tab becomes active
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 9.8 Create `frontend/src/App.tsx`
    - Mount `Header` (logo + `SavingsCounter` + `TabNav`), `AnalyzeTab`, `RulesTab`, `MetricsTab`
    - Manage `AppState`: `developer_id` (hardcoded `"demo"` for MVP), `totalTokensSaved`, `totalCostSaved`, `recentCalls`
    - On mount: call `fetchMetrics` to populate counters; pass `onSavingsUpdate` to `AnalyzeTab`
    - Dark background `bg-gray-950`, electric blue `#3B82F6` accents, per design styling conventions
    - _Requirements: 8.1, 9.1, 9.2, 9.3, 9.4_

  - [ ]* 9.9 Write property test for savings counter increment (Property 12)
    - **Property 12: Live savings counter increments exactly by tokens_saved**
    - **Validates: Requirements 9.3**
    - File: `frontend/src/__tests__/counter.test.ts`; use `fc.integer({min: 0})` for `oldTotal` and `fc.integer({min: 1})` for `tokensSaved`, assert `newTotal === oldTotal + tokensSaved`
    - Tag: `// Feature: agent-guard-ai, Property 12: Live savings counter increments exactly by tokens_saved`

- [x] 10. Create Amplify deployment configuration
  - Write `amplify.yml` with `preBuild: npm ci`, `build: npm run build`, `artifacts.baseDirectory: dist`
  - Write `.env.example` documenting `VITE_API_BASE_URL`, `VITE_API_KEY`, `VITE_DEVELOPER_ID` — no real values in source
  - _Requirements: 12.6_

- [x] 11. Checkpoint — full test suite
  - Run Python tests: `python -m pytest tests/ -v`
  - Run frontend tests: `cd frontend && npx vitest --run`
  - All property tests and unit tests must be green before continuing.
  - Ask the user if questions arise.

- [x] 12. Wire everything together and final validation
  - [x] 12.1 Write `tests/test_integration/test_e2e.py`
    - End-to-end test: `POST /v1/analyze-log` with LocalStack DynamoDB + mock SSM; assert 200 response shape and DynamoDB log record written without raw payload
    - API key lookup flow via SSM (LocalStack)
    - _Requirements: 3.1, 3.2, 6.1_

  - [ ]* 12.2 Write smoke tests
    - Verify Bedrock client is configured with 10 s timeout (Req 2.6)
    - Verify no API key values are hard-coded in source files — grep for known key patterns (Req 6.3)
    - Verify `sam build` completes without errors (Req 12.1)
    - _Requirements: 2.6, 6.3, 12.1_

  - [x] 12.3 Final frontend build verification
    - Run `cd frontend && npm run build` and confirm `dist/` output is generated without TypeScript or Tailwind errors
    - _Requirements: 12.6_

- [ ] 13. Final checkpoint — all systems green
  - Run `python -m pytest tests/ -v` and `cd frontend && npx vitest --run`
  - Run `sam build` to verify SAM template and Lambda packaging
  - Ensure all tests pass; ask the user if any questions arise before handing off.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints (tasks 3, 5, 11, 13) ensure incremental validation throughout the build
- Property tests use **Hypothesis** (Python backend) and **fast-check** (TypeScript frontend)
- Unit tests use **pytest** (backend) and **Vitest + React Testing Library** (frontend)
- The stretch intercept handler (task 4.8) can be deferred without blocking any other task
- Raw payload must NEVER appear in logs, DynamoDB, or CloudWatch — this is a hard constraint enforced by Properties 7 and verified in integration tests

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.3", "2.5", "2.6"] },
    { "id": 2, "tasks": ["2.2", "2.4", "2.7"] },
    { "id": 3, "tasks": ["4.1", "4.3", "4.5", "6.1"] },
    { "id": 4, "tasks": ["4.2", "4.4", "4.6", "4.7", "4.8", "4.9"] },
    { "id": 5, "tasks": ["7.1", "8.1"] },
    { "id": 6, "tasks": ["8.2"] },
    { "id": 7, "tasks": ["9.1", "9.3"] },
    { "id": 8, "tasks": ["9.2", "9.4", "9.6", "9.7"] },
    { "id": 9, "tasks": ["9.5", "9.8", "9.9", "10.1"] },
    { "id": 10, "tasks": ["12.1", "12.2", "12.3"] }
  ]
}
```
