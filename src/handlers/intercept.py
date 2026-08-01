"""
Lambda handler for POST /v1/proxy/intercept (stretch).

Implements the same analysis flow as analyze.py, then determines an
intercept status based on the developer's configured action and the
classified risk level.

Flow:
  1. Authenticate via X-API-Key header
  2. Validate request body (developer_id + payload)
  3. Estimate tokens
  4. Calculate cost
  5. Classify risk
  6. Fetch developer's budget rule (budget_threshold_usd + action)
  7. Conditionally invoke alternative generator
  8. Write log record (fire-and-forget)
  9. Determine intercept status per requirements 7.2–7.4:
       - risk_level == "high" and action == "block"   → "blocked"
       - risk_level == "high" and action == "reroute" → "rerouted"
       - otherwise                                    → "allowed"
  10. Return 200 with status, risk_level, suggested_alternative,
      tokens_estimated, cost_usd

Never returns 5xx — all infrastructure errors are absorbed.

Requirements: 7.1, 7.2, 7.3, 7.4
"""

import json
import logging

from core import auth, dynamo, risk_classifier, token_estimator
from core.alternative_gen import generate as generate_alternative
from core.token_estimator import PRICE_PER_1K_INPUT_TOKENS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

_JSON_CONTENT_TYPE = {"Content-Type": "application/json"}


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": _JSON_CONTENT_TYPE,
        "body": json.dumps(body),
    }


def _error(status_code: int, message: str) -> dict:
    return _response(status_code, {"error": message})


# ---------------------------------------------------------------------------
# Status determination (Requirements 7.2, 7.3, 7.4)
# ---------------------------------------------------------------------------

def _determine_status(risk_level: str, action: str) -> str:
    """Determine the intercept status from risk level and developer action.

    Parameters
    ----------
    risk_level : str
        One of ``"low"``, ``"medium"``, ``"high"``, or ``"unknown"``.
    action : str
        The developer's configured action: ``"block"`` or ``"reroute"``.

    Returns
    -------
    str
        ``"blocked"`` — Requirement 7.2: risk_level == "high" and action == "block"
        ``"rerouted"`` — Requirement 7.3: risk_level == "high" and action == "reroute"
        ``"allowed"``  — Requirement 7.4: risk_level is "low", "medium", or any other value
    """
    if risk_level == "high" and action == "block":
        return "blocked"
    if risk_level == "high" and action == "reroute":
        return "rerouted"
    return "allowed"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context) -> dict:  # noqa: ANN001
    """Entry point for POST /v1/proxy/intercept.

    Parameters
    ----------
    event : dict
        API Gateway HTTP API proxy event.
    context :
        Lambda context object (unused).

    Returns
    -------
    dict
        API Gateway proxy response with statusCode, headers, and body.
    """
    # ------------------------------------------------------------------
    # Step 1: Authenticate — extract X-API-Key and validate via SSM
    # ------------------------------------------------------------------
    headers = event.get("headers") or {}
    # AWS API Gateway HTTP API lowercases all header names
    api_key = headers.get("x-api-key")

    if not api_key:
        return _error(401, "Unauthorized: X-API-Key header is required")

    developer_id_from_key = auth.validate_key(api_key)
    if developer_id_from_key is None:
        return _error(401, "Unauthorized: invalid or missing X-API-Key")

    # ------------------------------------------------------------------
    # Step 2: Parse and validate request body
    # ------------------------------------------------------------------
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _error(400, "Request body must be valid JSON")

    developer_id = body.get("developer_id", "").strip()
    if not developer_id:
        return _error(400, "developer_id field is required and must be non-empty")

    payload = body.get("payload", "")
    if not isinstance(payload, str) or not payload.strip():
        return _error(400, "payload field is required and must be non-empty")

    # ------------------------------------------------------------------
    # Step 3: Estimate tokens
    # ------------------------------------------------------------------
    tokens_estimated = token_estimator.estimate(payload)

    # ------------------------------------------------------------------
    # Step 4: Calculate cost
    # ------------------------------------------------------------------
    cost_usd = tokens_estimated * PRICE_PER_1K_INPUT_TOKENS / 1000

    # ------------------------------------------------------------------
    # Step 5: Classify risk
    # ------------------------------------------------------------------
    risk_level = risk_classifier.classify(tokens_estimated)

    # ------------------------------------------------------------------
    # Step 6: Fetch developer's budget rule from AgentRules
    # ------------------------------------------------------------------
    rule = dynamo.get_rule(developer_id)
    budget_threshold_usd = rule["budget_threshold_usd"]
    action = rule["action"]

    # ------------------------------------------------------------------
    # Step 7: Conditionally generate cheaper alternative via Bedrock
    # ------------------------------------------------------------------
    suggested_alternative = None
    tokens_saved = 0
    fallback_message = None

    if cost_usd > budget_threshold_usd:
        alternative, alt_tokens_saved, fallback_reason = generate_alternative(
            payload, tokens_estimated
        )

        if fallback_reason is not None:
            # Bedrock timeout / service error / parse error → apply fallback
            risk_level = "unknown"
            suggested_alternative = None
            tokens_saved = 0
            fallback_message = (
                "Alternative generation temporarily unavailable. "
                "Analysis results are still valid."
            )
        else:
            suggested_alternative = alternative
            tokens_saved = alt_tokens_saved

    # ------------------------------------------------------------------
    # Step 8: Write log record — fire-and-forget, absorb DynamoDB errors
    # ------------------------------------------------------------------
    try:
        dynamo.put_log(
            developer_id=developer_id,
            tokens_estimated=tokens_estimated,
            cost_usd=cost_usd,
            risk_level=risk_level,
            tokens_saved=tokens_saved,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("DynamoDB log write failed: %s", exc)

    # ------------------------------------------------------------------
    # Step 9: Determine intercept status
    # ------------------------------------------------------------------
    status = _determine_status(risk_level, action)

    # ------------------------------------------------------------------
    # Step 10: Return 200 with intercept result
    # ------------------------------------------------------------------
    response_body: dict = {
        "status": status,
        "risk_level": risk_level,
        "suggested_alternative": suggested_alternative,
        "tokens_estimated": tokens_estimated,
        "cost_usd": cost_usd,
    }

    # Include message field only when a Bedrock fallback occurred
    if fallback_message is not None:
        response_body["message"] = fallback_message

    return _response(200, response_body)
