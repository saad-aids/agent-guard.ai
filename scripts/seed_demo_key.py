#!/usr/bin/env python3
"""
seed_demo_key.py — Pre-provision a demo API key in AWS SSM Parameter Store.

Usage:
    python scripts/seed_demo_key.py <api_key_value>
    python scripts/seed_demo_key.py          # prompts for the key interactively

The script computes sha256(key).hexdigest() and stores developer_id="demo" at
the SSM path /agentguard/api-keys/{hash} as a SecureString.

The raw key is NEVER stored anywhere — only the SHA-256 hex digest is used as
the SSM path segment, consistent with the auth middleware in src/core/auth.py.

After running this script, set VITE_API_KEY=<raw_key> in your Amplify
environment or local .env file.

Requirements: 6.3 — API keys must never be hard-coded in source code or SAM
templates.
"""

import hashlib
import sys

import boto3
from botocore.exceptions import ClientError


SSM_PATH_PREFIX = "/agentguard/api-keys"
DEVELOPER_ID = "demo"
REGION = "us-east-1"


def hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def put_ssm_parameter(ssm_client, path: str, developer_id: str) -> None:
    """Store developer_id at the given SSM path as a SecureString."""
    ssm_client.put_parameter(
        Name=path,
        Value=developer_id,
        Type="SecureString",
        Overwrite=True,
    )


def main() -> None:
    # Accept the key from argv[1] or prompt the user interactively.
    if len(sys.argv) >= 2:
        raw_key = sys.argv[1]
    else:
        raw_key = input("Enter the demo API key value: ").strip()

    if not raw_key:
        print("ERROR: API key must not be empty.", file=sys.stderr)
        sys.exit(1)

    key_hash = hash_key(raw_key)
    ssm_path = f"{SSM_PATH_PREFIX}/{key_hash}"

    ssm = boto3.client("ssm", region_name=REGION)

    try:
        put_ssm_parameter(ssm, ssm_path, DEVELOPER_ID)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        print(f"ERROR: SSM put_parameter failed [{error_code}]: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Print the values the operator needs to note — raw key goes into VITE_API_KEY.
    print(f"Demo key seeded successfully.")
    print(f"  VITE_API_KEY  : {raw_key}")
    print(f"  SSM path      : {ssm_path}")
    print(f"  developer_id  : {DEVELOPER_ID}")
    print()
    print("Set VITE_API_KEY to the value above in your Amplify environment or .env file.")


if __name__ == "__main__":
    main()
