import boto3
import json
import logging

from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

logger = logging.getLogger(__name__)

BEDROCK_TIMEOUT_SECONDS = 10
MODEL_ID = "amazon.nova-micro-v1:0"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1",
    config=Config(
        connect_timeout=BEDROCK_TIMEOUT_SECONDS,
        read_timeout=BEDROCK_TIMEOUT_SECONDS,
    ),
)

PROMPT_TEMPLATE = """You are a cost-optimization assistant for AI agent developers.
A tool-call payload has been submitted with an estimated token cost of {tokens_estimated} tokens.
This exceeds the developer's budget threshold.

Analyze the payload and respond with ONLY a JSON object — no markdown, no explanation outside the JSON.
The JSON must exactly match this schema:
{{
  "alternative_type": "<cli_command|python_script|bash_script|api_call>",
  "alternative_command": "<the cheaper command or script>",
  "estimated_token_savings_pct": <integer 0-100>,
  "explanation": "<one sentence explaining the savings>"
}}

Payload:
{payload}"""


def generate(
    payload: str, tokens_estimated: int
) -> tuple[dict | None, int, str | None]:
    """Invoke Amazon Bedrock Nova Micro to generate a cheaper alternative for the payload.

    Args:
        payload: The tool-call payload text that exceeds the budget threshold.
        tokens_estimated: The estimated token count for the payload.

    Returns:
        A tuple of (alternative_dict_or_none, tokens_saved, fallback_reason_or_none).
        On success: (alternative_dict, tokens_saved, None)
        On failure: (None, 0, "fallback_timeout" | "fallback_service_error" | "fallback_parse_error")
    """
    prompt = PROMPT_TEMPLATE.format(
        tokens_estimated=tokens_estimated,
        payload=payload,
    )

    try:
        response = bedrock.converse(
            modelId=MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
        )
    except ReadTimeoutError:
        logger.warning(
            "Bedrock request timed out after %d seconds for model %s",
            BEDROCK_TIMEOUT_SECONDS,
            MODEL_ID,
        )
        return (None, 0, "fallback_timeout")
    except ClientError as exc:
        logger.error(
            "Bedrock ClientError during alternative generation: %s",
            exc,
            exc_info=True,
        )
        return (None, 0, "fallback_service_error")

    raw_text = response["output"]["message"]["content"][0]["text"]

    try:
        alternative_dict = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error(
            "Failed to parse Bedrock response as JSON. Raw response: %s",
            raw_text,
        )
        return (None, 0, "fallback_parse_error")

    savings_pct = alternative_dict.get("estimated_token_savings_pct", 0)
    tokens_saved = int(tokens_estimated * savings_pct / 100)

    return (alternative_dict, tokens_saved, None)
