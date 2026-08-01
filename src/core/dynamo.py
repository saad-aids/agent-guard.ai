"""
DynamoDB helpers for AgentGuard.ai.

Provides read/write helpers for two tables:
  - AgentRules    (PK: developer_id)
  - InterceptLogs (PK: developer_id, SK: timestamp)

Table names are read from environment variables:
  AGENT_RULES_TABLE   — defaults to "AgentRules"
  INTERCEPT_LOGS_TABLE — defaults to "InterceptLogs"

IMPORTANT: The raw payload is NEVER written to any table or log.
"""

import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

# ---------------------------------------------------------------------------
# Client / table references (module-level for Lambda instance reuse)
# ---------------------------------------------------------------------------

_dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

_AGENT_RULES_TABLE_NAME = os.environ.get("AGENT_RULES_TABLE", "AgentRules")
_INTERCEPT_LOGS_TABLE_NAME = os.environ.get("INTERCEPT_LOGS_TABLE", "InterceptLogs")

_rules_table = _dynamodb.Table(_AGENT_RULES_TABLE_NAME)
_logs_table = _dynamodb.Table(_INTERCEPT_LOGS_TABLE_NAME)

# ---------------------------------------------------------------------------
# Default rule values (Requirements 2.2)
# ---------------------------------------------------------------------------

_DEFAULT_BUDGET_THRESHOLD_USD = 0.01
_DEFAULT_ACTION = "reroute"


# ---------------------------------------------------------------------------
# AgentRules helpers
# ---------------------------------------------------------------------------


def get_rule(developer_id: str) -> dict:
    """Return the budget rule for a developer.

    Fetches the record from AgentRules. If no record exists, returns the
    system defaults: ``budget_threshold_usd=0.01``, ``action="reroute"``.

    Parameters
    ----------
    developer_id : str
        Unique developer identifier.

    Returns
    -------
    dict
        ``{"budget_threshold_usd": float, "action": str}``
    """
    response = _rules_table.get_item(Key={"developer_id": developer_id})
    item = response.get("Item")

    if item is None:
        return {
            "budget_threshold_usd": _DEFAULT_BUDGET_THRESHOLD_USD,
            "action": _DEFAULT_ACTION,
        }

    return {
        "budget_threshold_usd": float(item["budget_threshold_usd"]),
        "action": item["action"],
    }


def upsert_rule(
    developer_id: str,
    budget_threshold_usd: float,
    action: str,
) -> str:
    """Create or replace a developer's budget rule in AgentRules.

    Parameters
    ----------
    developer_id : str
        Unique developer identifier.
    budget_threshold_usd : float
        Maximum acceptable cost per call in USD.
    action : str
        One of ``"reroute"`` or ``"block"``.

    Returns
    -------
    str
        The ISO 8601 UTC timestamp written to the ``updated_at`` field,
        allowing callers to echo it back in the response without a
        second DynamoDB read.
    """
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _rules_table.put_item(
        Item={
            "developer_id": developer_id,
            "budget_threshold_usd": Decimal(str(budget_threshold_usd)),
            "action": action,
            "updated_at": updated_at,
        }
    )
    return updated_at


# ---------------------------------------------------------------------------
# InterceptLogs helpers
# ---------------------------------------------------------------------------


def put_log(
    developer_id: str,
    tokens_estimated: int,
    cost_usd: float,
    risk_level: str,
    tokens_saved: int,
) -> None:
    """Write an analysis log record to InterceptLogs.

    The raw payload is NEVER included in this record (Requirements 3.1, 3.2).
    The timestamp uses microsecond precision to ensure SK uniqueness for
    developers that submit multiple calls within the same second.

    Parameters
    ----------
    developer_id : str
        Unique developer identifier.
    tokens_estimated : int
        Estimated token count for the analysis.
    cost_usd : float
        Estimated cost in USD (stored as Decimal for DynamoDB compatibility).
    risk_level : str
        One of ``"low"``, ``"medium"``, ``"high"``, or ``"unknown"``.
    tokens_saved : int
        Tokens saved by the suggested alternative, or 0 if none was generated.
    """
    # ISO 8601 UTC with microsecond precision ensures sort key uniqueness
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

    _logs_table.put_item(
        Item={
            "developer_id": developer_id,
            "timestamp": timestamp,
            "tokens_estimated": tokens_estimated,
            # DynamoDB requires Decimal for floating-point numbers (Requirements 5.1)
            "cost_usd": Decimal(str(cost_usd)),
            "risk_level": risk_level,
            "tokens_saved": tokens_saved,
        }
    )


def query_logs(developer_id: str, limit: int = 20) -> list[dict]:
    """Return the most recent InterceptLogs records for a developer.

    Records are returned in descending timestamp order (newest first),
    consistent with the metrics dashboard requirements (Requirements 5.1).

    Parameters
    ----------
    developer_id : str
        Unique developer identifier.
    limit : int, optional
        Maximum number of records to return (default 20).

    Returns
    -------
    list[dict]
        Each dict contains ``developer_id``, ``timestamp``,
        ``tokens_estimated``, ``cost_usd``, ``risk_level``, ``tokens_saved``.
    """
    response = _logs_table.query(
        KeyConditionExpression=Key("developer_id").eq(developer_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    items = response.get("Items", [])

    # Normalise Decimal values back to Python native types for JSON serialisation
    return [
        {
            "developer_id": item["developer_id"],
            "timestamp": item["timestamp"],
            "tokens_estimated": int(item["tokens_estimated"]),
            "cost_usd": float(item["cost_usd"]),
            "risk_level": item["risk_level"],
            "tokens_saved": int(item["tokens_saved"]),
        }
        for item in items
    ]
