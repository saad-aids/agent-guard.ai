# Feature: agent-guard-ai, Property 1: Token estimator is floor division by four
"""
Property-based tests for src/core/token_estimator.py

Property 1: Token estimator is floor division by four
Validates: Requirements 1.2
"""

import sys
import os

# Ensure src/ is on the path so the core modules can be imported directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from core.token_estimator import estimate, estimate_cost, PRICE_PER_1K_INPUT_TOKENS


# ---------------------------------------------------------------------------
# Property 1: Token estimator is floor division by four
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------

@given(st.text())
@settings(max_examples=500)
def test_estimate_is_floor_div_4(s: str) -> None:
    """For any string s, estimate(s) must equal len(s) // 4."""
    assert estimate(s) == len(s) // 4


# ---------------------------------------------------------------------------
# Additional unit tests (example-based) for clarity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload,expected", [
    ("", 0),
    ("a", 0),
    ("abcd", 1),
    ("abcde", 1),
    ("a" * 1000, 250),
    ("a" * 4000, 1000),
])
def test_estimate_examples(payload: str, expected: int) -> None:
    assert estimate(payload) == expected


def test_estimate_returns_non_negative() -> None:
    assert estimate("") >= 0
    assert estimate("x") >= 0


def test_estimate_cost_uses_correct_constant() -> None:
    tokens = 1000
    expected = tokens * PRICE_PER_1K_INPUT_TOKENS / 1000
    assert estimate_cost(tokens) == pytest.approx(expected)


def test_estimate_cost_zero_tokens() -> None:
    assert estimate_cost(0) == 0.0
