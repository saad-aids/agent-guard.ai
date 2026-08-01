"""
Risk classifier for AgentGuard.ai.

Classifies an estimated token count into a risk level based on
predefined thresholds.
"""

LOW_THRESHOLD = 1000    # tokens < 1000  → low
HIGH_THRESHOLD = 10000  # tokens >= 10000 → high
                        # 1000 <= tokens < 10000 → medium


def classify(tokens: int) -> str:
    """Classify token count into risk level.

    Parameters
    ----------
    tokens : int
        Non-negative estimated token count.

    Returns
    -------
    str
        One of ``"low"``, ``"medium"``, or ``"high"``.

    Examples
    --------
    >>> classify(0)
    'low'
    >>> classify(999)
    'low'
    >>> classify(1000)
    'medium'
    >>> classify(9999)
    'medium'
    >>> classify(10000)
    'high'
    """
    if tokens < LOW_THRESHOLD:
        return "low"
    elif tokens < HIGH_THRESHOLD:
        return "medium"
    else:
        return "high"
