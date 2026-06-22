from dataclasses import dataclass
from enum import Enum


class ComparisonOperator(str, Enum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_OR_EQUAL = ">="
    LESS_OR_EQUAL = "<="
    EQUAL = "=="


class LogicMode(str, Enum):
    AND = "AND"
    OR = "OR"


class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class NumericCondition:
    """
    A single flat condition on a ticker's price. v1 supports price only -
    there is intentionally no `metric` field (no RSI/volume yet).
    """
    ticker: str
    operator: ComparisonOperator
    value: float


@dataclass
class TradingQuery:
    """
    The structured representation of what the user wants. Does not execute
    anything itself - describes action + the conditions that must hold.
    `logic` applies to the ENTIRE list of conditions - either all must hold
    (AND) or at least one must hold (OR). There is no nesting: the user
    picks exactly one logic mode for the whole query, not a tree of
    mixed AND/OR.
    """
    action: ActionType
    ticker: str
    conditions: list[NumericCondition]
    logic: LogicMode
    raw_text: str
