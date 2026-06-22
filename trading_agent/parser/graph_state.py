from typing import Optional, TypedDict

from core import TradingQuery
from parser.schema import ParsedQuery


class ParserState(TypedDict):
    """The state that flows between nodes in the LangGraph."""
    raw_text: str
    parsed_query: Optional[ParsedQuery]
    validation_errors: list[str]
    needs_clarification: bool          # TODO: not implemented in v1, placeholder
    trading_query: Optional[TradingQuery]   # the final output
