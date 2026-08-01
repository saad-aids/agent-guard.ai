# Feature: agent-guard-ai, Property 2: Risk classifier covers all token ranges without gaps
"""
Property-based tests for src/core/risk_classifier.py

Property 2: Risk classifier covers all token ranges without gaps
Validates: Requirements 1.3, 1.4, 1.5
"""

import sys
import os

# Ensure src/ is on the path so the core modules can be imported directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from core.risk_classifier import classify, LOW_THRESHOLD, HIGH_THRESHOLD


# ---------------------------------------------------------------------------
# Property 2: Risk classifier covers all token ranges without gaps
# Validates: Requirements 1.3, 1.4, 1.5
# ---------------------------------------------------------------------------

@given(st.integers(min_value=0))
@settings(max_examples=500)
def test_classify_always_returns_valid_bucket(tokens: int) -> None:
    """classify() must always return one of the three valid risk levels."""
    result = classify(tokens)
    assert result in {"low", "medium", "high"}


@given(st.integers(min_value=0, max_value=LOW_THRESHOLD - 1))
@settings(max_examples=200)
def test_classify_low_range(tokens: int) -> None:
    """Tokens in [0, 999] must be classified as 'low'. Validates: Req 1.3"""
    assert classify(tokens) == "low"


@given(st.integers(min_value=LOW_THRESHOLD, max_value=HIGH_THRESHOLD - 1))
@settings(max_examples=200)
def test_classify_medium_range(tokens: int) -> None:
    """Tokens in [1000, 9999] must be classified as 'medium'. Validates: Req 1.4"""
    assert classify(tokens) == "medium"


@given(st.integers(min_value=HIGH_THRESHOLD))
@settings(max_examples=200)
def test_classify_high_range(tokens: int) -> None:
    """Tokens >= 10000 must be classified as 'high'. Validates: Req 1.5"""
    assert classify(tokens) == "high"


# ---------------------------------------------------------------------------
# Boundary / example-based tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tokens,expected", [
    (0,          "low"),
    (999,        "low"),
    (1000,       "medium"),
    (9999,       "medium"),
    (10000,      "high"),
    (100000,     "high"),
])
def test_classify_boundary_examples(tokens: int, expected: str) -> None:
    assert classify(tokens) == expected
