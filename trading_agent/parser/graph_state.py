from typing import Optional, TypedDict

from core import TradingQuery
from parser.schema import ParsedQuery


class ParserState(TypedDict):
    """The state that flows between nodes in the LangGraph."""
    raw_text: str
    parsed_query: Optional[ParsedQuery]
    validation_errors: list[str]
    needs_clarification: bool
    clarification_question: Optional[str]
    clarification_reason: Optional[str]
    clarification_history: list[tuple[str, str]]
    trading_query: Optional[TradingQuery]
