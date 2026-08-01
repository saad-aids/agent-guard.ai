"""
Lambda handler for GET /v1/metrics/dashboard.

Implements the 5-step metrics flow:
  1. Authenticate via X-API-Key header
  2. Extract developer_id from query string parameters
  3. Query InterceptLogs via DynamoDB
  4. Aggregate totals (calls, tokens saved, cost saved)
  5. Return 200 with aggregates + recent_calls

On empty logs: all numeric fields are 0 and recent_calls is [].
On DynamoDB error: returns 200 with {"message": "Metrics temporarily unavailable"}.
Never returns 5xx — all infrastructure errors are absorbed.
"""

import json
import logging

from core import auth, dynamo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Nova Micro pricing: $0.000035 per 1,000 input tokens
# Used to convert tokens_saved into cost_saved_usd
_PRICE_PER_1K_INPUT_TOKENS = 0.000035

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
# Handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context) -> dict:  # noqa: ANN001
    """Entry point for GET /v1/metrics/dashboard.

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

    if auth.validate_key(api_key) is None:
        return _error(401, "Unauthorized: invalid or missing X-API-Key")

    # ------------------------------------------------------------------
    # Step 2: Extract developer_id from query string parameters
    # ------------------------------------------------------------------
    query_params = event.get("queryStringParameters") or {}
    developer_id = query_params.get("developer_id", "").strip()

    if not developer_id:
        return _error(400, "developer_id query parameter is required")

    # ------------------------------------------------------------------
    # Step 3: Query InterceptLogs — up to 20 records, newest first
    # ------------------------------------------------------------------
    try:
        logs = dynamo.query_logs(developer_id, limit=20)
    except Exception as exc:  # noqa: BLE001
        logger.error("DynamoDB metrics query failed: %s", exc)
        return _response(200, {"message": "Metrics temporarily unavailable"})

    # ------------------------------------------------------------------
    # Step 4: Aggregate totals from returned records
    # ------------------------------------------------------------------
    total_calls_analyzed = len(logs)
    total_tokens_saved = sum(r.get("tokens_saved", 0) for r in logs)
    total_cost_saved_usd = round(
        sum(r.get("tokens_saved", 0) * _PRICE_PER_1K_INPUT_TOKENS / 1000 for r in logs),
        8,
    )

    # ------------------------------------------------------------------
    # Step 5: Return 200 with aggregates and recent call list
    # ------------------------------------------------------------------
    return _response(
        200,
        {
            "developer_id": developer_id,
            "total_calls_analyzed": total_calls_analyzed,
            "total_tokens_saved": total_tokens_saved,
            "total_cost_saved_usd": total_cost_saved_usd,
            "recent_calls": logs,
        },
    )
