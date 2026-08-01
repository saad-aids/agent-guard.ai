"""
End-to-end integration test for AgentGuard.ai.

Tests:
  - POST /v1/analyze-log against the deployed API Gateway endpoint
  - InterceptLogs DynamoDB table (us-east-1) written correctly
  - Raw payload is NEVER stored in the DynamoDB record

Requirements covered:
  - 3.1: Log record fields written after a successful analysis
  - 3.2: Raw payload must NEVER appear in the DynamoDB record
  - 6.1: Valid X-API-Key header is required

Skip conditions:
  The tests are skipped when the environment variables AGENTGUARD_API_URL
  and AGENTGUARD_API_KEY are not set, so they can run safely in CI without
  a live deployment.

Usage:
  export AGENTGUARD_API_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com"
  export AGENTGUARD_API_KEY="<your-api-key>"
  export AGENTGUARD_DEVELOPER_ID="demo"           # optional, defaults to "demo"
  export INTERCEPT_LOGS_TABLE="InterceptLogs"     # optional, defaults to "InterceptLogs"

  python -m pytest tests/test_integration/test_e2e.py -v -s
"""

import os
import time

import boto3
import pytest
import requests

# ---------------------------------------------------------------------------
# Environment / configuration
# ---------------------------------------------------------------------------

_API_URL = os.environ.get("AGENTGUARD_API_URL")
_API_KEY = os.environ.get("AGENTGUARD_API_KEY")
_DEVELOPER_ID = os.environ.get("AGENTGUARD_DEVELOPER_ID", "demo")
_TABLE_NAME = os.environ.get("INTERCEPT_LOGS_TABLE", "InterceptLogs")

# Skip the entire module when the deployment env vars are absent.
_DEPLOYED = bool(_API_URL and _API_KEY)
_SKIP_REASON = (
    "AGENTGUARD_API_URL and AGENTGUARD_API_KEY must be set to run integration tests"
)

pytestmark = pytest.mark.skipif(not _DEPLOYED, reason=_SKIP_REASON)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_RISK_LEVELS = {"low", "medium", "high", "unknown"}

# A recognisable, fixed payload long enough to produce a non-zero tokens_estimated
_PAYLOAD = "e2e test payload: " + "x" * 200


def _analyze_endpoint() -> str:
    """Return the full URL for POST /v1/analyze-log."""
    return f"{_API_URL.rstrip('/')}/v1/analyze-log"


def _post_analyze(payload: str = _PAYLOAD, developer_id: str = _DEVELOPER_ID) -> requests.Response:
    """Call POST /v1/analyze-log and return the raw Response."""
    return requests.post(
        _analyze_endpoint(),
        json={"developer_id": developer_id, "payload": payload},
        headers={"X-API-Key": _API_KEY, "Content-Type": "application/json"},
        timeout=30,
    )


def _poll_dynamo_record(
    developer_id: str,
    after_ts: str,
    table_name: str = _TABLE_NAME,
    max_wait: float = 3.0,
    interval: float = 0.5,
) -> dict | None:
    """
    Poll InterceptLogs for a record matching *developer_id* whose timestamp
    is lexicographically >= *after_ts*.  Returns the first matching item or
    None if the timeout elapses.

    Parameters
    ----------
    developer_id:
        The developer_id to query.
    after_ts:
        ISO-8601 string; only records at-or-after this timestamp are considered
        (prevents stale records from a previous test run from matching).
    table_name:
        DynamoDB table to query. Defaults to ``InterceptLogs``.
    max_wait:
        Maximum seconds to wait before giving up.
    interval:
        Polling interval in seconds.
    """
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(table_name)
    from boto3.dynamodb.conditions import Key

    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        response = table.query(
            KeyConditionExpression=(
                Key("developer_id").eq(developer_id)
                & Key("timestamp").gte(after_ts)
            ),
            ScanIndexForward=False,
            Limit=5,
        )
        items = response.get("Items", [])
        if items:
            return items[0]
        time.sleep(interval)
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzeEndpointE2E:
    """E2E tests for POST /v1/analyze-log against the real deployed API."""

    def test_successful_analysis_returns_200_with_correct_shape(self):
        """
        A valid request must return HTTP 200 with all expected fields present
        and correctly typed.

        Validates: Requirements 1.1, 6.1
        """
        resp = _post_analyze()

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}. Body: {resp.text}"
        )

        body = resp.json()

        # Required fields must all be present
        required_fields = {
            "tokens_estimated",
            "cost_usd",
            "risk_level",
            "suggested_alternative",
            "tokens_saved",
            "developer_id",
        }
        missing = required_fields - body.keys()
        assert not missing, f"Response missing fields: {missing}"

    def test_tokens_estimated_matches_heuristic(self):
        """
        tokens_estimated must equal len(payload) // 4 (the character-count
        heuristic defined in Requirements 1.2).
        """
        resp = _post_analyze()
        assert resp.status_code == 200

        body = resp.json()
        expected_tokens = len(_PAYLOAD) // 4
        assert body["tokens_estimated"] == expected_tokens, (
            f"Expected tokens_estimated={expected_tokens}, "
            f"got {body['tokens_estimated']}"
        )

    def test_cost_usd_is_positive_float(self):
        """cost_usd must be a positive number."""
        resp = _post_analyze()
        assert resp.status_code == 200

        cost = resp.json()["cost_usd"]
        assert isinstance(cost, (int, float)), f"cost_usd is not numeric: {cost!r}"
        assert cost > 0, f"cost_usd must be positive, got {cost}"

    def test_risk_level_is_valid_enum(self):
        """risk_level must be one of the four permitted values."""
        resp = _post_analyze()
        assert resp.status_code == 200

        risk = resp.json()["risk_level"]
        assert risk in VALID_RISK_LEVELS, (
            f"risk_level {risk!r} is not in {VALID_RISK_LEVELS}"
        )

    def test_developer_id_echoed_in_response(self):
        """developer_id in the response must match the developer_id sent."""
        resp = _post_analyze()
        assert resp.status_code == 200

        assert resp.json()["developer_id"] == _DEVELOPER_ID, (
            f"developer_id mismatch: sent {_DEVELOPER_ID!r}, "
            f"got {resp.json()['developer_id']!r}"
        )

    def test_missing_api_key_returns_401(self):
        """
        A request without X-API-Key must be rejected with HTTP 401.

        Validates: Requirements 6.1, 6.2
        """
        resp = requests.post(
            _analyze_endpoint(),
            json={"developer_id": _DEVELOPER_ID, "payload": _PAYLOAD},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code == 401, (
            f"Expected 401 for missing API key, got {resp.status_code}"
        )


class TestDynamoDBLoggingE2E:
    """
    E2E tests that verify DynamoDB logging behaviour.

    These tests call the API and then directly inspect the InterceptLogs table
    to confirm:
      1. A record was written with the expected fields (Req 3.1).
      2. The raw payload was NOT stored in the record (Req 3.2).
    """

    def test_dynamo_record_written_after_successful_analysis(self):
        """
        After a 200 response the InterceptLogs table must contain a record
        for the developer_id with all required fields.

        Validates: Requirements 3.1
        """
        # Capture a timestamp just before the call so the poll can filter
        # out older records (ISO-8601, sortable lexicographically).
        before_ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

        resp = _post_analyze()
        assert resp.status_code == 200, (
            f"API call failed ({resp.status_code}): {resp.text}"
        )

        # Give Lambda up to 3 s to complete the async DynamoDB write
        record = _poll_dynamo_record(_DEVELOPER_ID, after_ts=before_ts)

        assert record is not None, (
            f"No DynamoDB record found for developer_id={_DEVELOPER_ID!r} "
            f"in table {_TABLE_NAME!r} within 3 seconds of the API call."
        )

        # Validate expected fields are present (Req 3.1)
        expected_fields = {
            "developer_id",
            "timestamp",
            "tokens_estimated",
            "cost_usd",
            "risk_level",
            "tokens_saved",
        }
        missing = expected_fields - record.keys()
        assert not missing, f"DynamoDB record is missing fields: {missing}"

        # Validate field values are consistent with the API response
        api_body = resp.json()
        assert record["developer_id"] == _DEVELOPER_ID
        assert int(record["tokens_estimated"]) == api_body["tokens_estimated"]
        assert record["risk_level"] == api_body["risk_level"]
        assert int(record["tokens_saved"]) == api_body["tokens_saved"]

    def test_dynamo_record_does_not_contain_raw_payload(self):
        """
        The DynamoDB record must NEVER contain the raw payload string,
        either as a top-level key named 'payload' or as a value in any field.

        Validates: Requirements 3.2
        """
        before_ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

        resp = _post_analyze()
        assert resp.status_code == 200

        record = _poll_dynamo_record(_DEVELOPER_ID, after_ts=before_ts)
        assert record is not None, (
            "No DynamoDB record found — cannot assert payload absence."
        )

        # 1. The key "payload" must not exist in the record
        assert "payload" not in record, (
            f"DynamoDB record contains forbidden key 'payload': {record}"
        )

        # 2. The raw payload string must not appear in any field value
        for field_name, field_value in record.items():
            value_str = str(field_value)
            assert _PAYLOAD not in value_str, (
                f"Raw payload found in DynamoDB field '{field_name}': "
                f"{value_str[:120]!r}"
            )
