import hashlib
import boto3

SSM = boto3.client("ssm", region_name="us-east-1")
_cache: dict[str, str] = {}  # in-memory per Lambda instance


def validate_key(api_key: str) -> str | None:
    """Returns developer_id or None if invalid.

    Hashes the raw API key with SHA-256 and looks up the resulting hex
    digest as an SSM path segment: /agentguard/api-keys/{hash}.
    The SSM parameter value is the developer_id associated with that key.

    Results are cached in-memory so each Lambda instance only makes one
    SSM call per unique key (not per request).  Cache is intentionally
    never invalidated — key rotation requires a Lambda cold start.

    Returns None (fail-closed) on ParameterNotFound or any SSM error.
    """
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if key_hash in _cache:
        return _cache[key_hash]

    path = f"/agentguard/api-keys/{key_hash}"
    try:
        resp = SSM.get_parameter(Name=path, WithDecryption=True)
        developer_id = resp["Parameter"]["Value"]
        _cache[key_hash] = developer_id
        return developer_id
    except SSM.exceptions.ParameterNotFound:
        return None
    except Exception:
        # Fail-closed on any other SSM client error (network, permissions, etc.)
        return None
