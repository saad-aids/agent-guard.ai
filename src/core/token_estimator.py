# core/token_estimator.py
# NOTE: This is a placeholder heuristic. Replace with tiktoken or a
# model-specific tokenizer (e.g., amazon.nova tokenizer) before production.

# Nova Micro pricing (us-east-1, as of hackathon build)
# Input:  $0.000035 per 1,000 input tokens
# NOTE: Update this constant if pricing changes.
PRICE_PER_1K_INPUT_TOKENS = 0.000035


def estimate(payload: str) -> int:
    """Estimate token count as floor(character_count / 4).

    NOTE: placeholder heuristic — replace with tiktoken before production
    """
    return len(payload) // 4


def estimate_cost(tokens: int) -> float:
    """Return estimated cost in USD for the given token count."""
    return tokens * PRICE_PER_1K_INPUT_TOKENS / 1000
