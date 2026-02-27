"""E2E golden-question regression scaffolds."""

import pytest

GOLDEN_QUESTIONS = [
    {
        "id": "q_portfolio_value",
        "question": "What is my portfolio value?",
        "expected_contains": [],
    },
    {
        "id": "q_top_holdings",
        "question": "Show my top 3 holdings.",
        "expected_contains": [],
    },
    {
        "id": "q_monthly_pnl",
        "question": "What is my PnL this month?",
        "expected_contains": [],
    },
]


@pytest.mark.e2e
@pytest.mark.external
@pytest.mark.parametrize("case", GOLDEN_QUESTIONS, ids=[c["id"] for c in GOLDEN_QUESTIONS])
def test_golden_questions_regression_scaffold(case):
    """TODO: send question through end-to-end path and assert expected answer contract."""
    # Example future flow:
    # 1. submit case["question"] through Telegram webhook or API query endpoint
    # 2. capture final answer text
    # 3. assert expected invariants and expected substrings
    assert case["question"]
    assert isinstance(case["expected_contains"], list)
