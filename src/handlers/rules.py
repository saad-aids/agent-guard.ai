"""
Lambda handler for POST /v1/rules

Upserts a developer's budget threshold and action preference in AgentRules.

4-step flow:
  1. Extract X-API-Key header → auth.validate_key() → 401 if missing/invalid
  2. Parse JSON body → validate developer_id, budget_threshold_usd, action → 400 if invalid
  3. dynamo.upsert_rule(developer_id, budget_threshold_usd, action) → returns updated_at
  4. Return 200 with {developer_id, budget_threshold_usd, action, updated_at}
"""

import json
import logging

from core import auth, dynamo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_JSON_HEADERS = {"Content-Type": "application/json"}
_VALID_ACTIONS = {"reroute", "block"}


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": _JSON_HEADERS,
        "body": json.dumps(body),
    }


def lambda_handler(event: dict, context) -> dict:
    """Entry point for POST /v1/rules.

    Parameters
    ----------
    event : dict
        API Gateway HTTP API event. Headers are lowercased by HTTP API.
    context :
        Lambda context object (unused).

    Returns
    -------
    dict
        API Gateway-compatible response with statusCode, headers, and body.
    """
    # ------------------------------------------------------------------
    # Step 1: Authenticate via X-API-Key header
    # ------------------------------------------------------------------
    headers = event.get("headers") or {}
    api_key = headers.get("x-api-key", "").strip()

    if not api_key:
        return _response(401, {"error": "Unauthorized: X-API-Key header is required"})

    developer_id_from_key = auth.validate_key(api_key)
    if developer_id_from_key is None:
        return _response(401, {"error": "Unauthorized: invalid or missing X-API-Key"})

    # ------------------------------------------------------------------
    # Step 2: Parse and validate request body
    # ------------------------------------------------------------------
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Request body must be valid JSON"})

    # Validate developer_id
    developer_id = body.get("developer_id", "")
    if not isinstance(developer_id, str) or not developer_id.strip():
        return _response(400, {"error": "developer_id is required and must be a non-empty string"})
    developer_id = developer_id.strip()

    # Validate budget_threshold_usd — must be present and strictly positive
    if "budget_threshold_usd" not in body:
        return _response(400, {"error": "budget_threshold_usd is required"})

    budget_threshold_usd = body["budget_threshold_usd"]
    # Reject booleans (bool is a subclass of int in Python) and non-numbers
    if isinstance(budget_threshold_usd, bool) or not isinstance(budget_threshold_usd, (int, float)):
        return _response(400, {"error": "budget_threshold_usd must be a positive number"})
    if budget_threshold_usd <= 0:
        return _response(400, {"error": "budget_threshold_usd must be a positive number"})

    # Validate action — must be "reroute" or "block"
    action = body.get("action")
    if action not in _VALID_ACTIONS:
        return _response(400, {"error": "action must be one of: reroute, block"})

    # ------------------------------------------------------------------
    # Step 3: Upsert rule in DynamoDB
    # ------------------------------------------------------------------
    updated_at = dynamo.upsert_rule(developer_id, float(budget_threshold_usd), action)

    logger.info(
        "Rule upserted: developer_id=%s budget_threshold_usd=%s action=%s updated_at=%s",
        developer_id,
        budget_threshold_usd,
        action,
        updated_at,
    )

    # ------------------------------------------------------------------
    # Step 4: Return 200 with the saved rule
    # ------------------------------------------------------------------
    return _response(200, {
        "developer_id": developer_id,
        "budget_threshold_usd": float(budget_threshold_usd),
        "action": action,
        "updated_at": updated_at,
    })
