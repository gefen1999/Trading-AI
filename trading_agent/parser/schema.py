from typing import Literal

from pydantic import BaseModel, Field


class ValidationAssessment(BaseModel):
    """Semantic validation result from the LLM assessor."""
    is_valid: bool
    needs_clarification: bool
    clarification_question: str | None
    reason: Literal[
        "unknown_ticker",
        "ambiguous_ticker",
        "ambiguous_logic",
        "missing_info",
        "contradictory",
        "other",
    ] | None
    issues: list[str]


class NumericConditionInput(BaseModel):
    """A single flat condition, as the LLM returns it. No `field`/`metric`
    split - just the ticker directly (v1 supports price only)."""
    ticker: str
    operator: Literal[">", "<", ">=", "<=", "=="]
    value: float


class ParsedQuery(BaseModel):
    """
    The JSON structure the LLM returns. Maps almost 1:1 onto TradingQuery -
    there is no tree to build, no required_tickers to compute (that field
    no longer exists anywhere in the project).
    """
    action: Literal["BUY", "SELL"]
    ticker: str
    conditions: list[NumericConditionInput] = Field(min_length=1)
    logic: Literal["AND", "OR"]
