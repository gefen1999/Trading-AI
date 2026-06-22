from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from data.base import DataFeed
from data.market_state import MarketState


class ComparisonOperator(str, Enum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_OR_EQUAL = ">="
    LESS_OR_EQUAL = "<="
    EQUAL = "=="


class LogicOperator(str, Enum):
    AND = "AND"
    OR = "OR"


class Condition(ABC):
    def evaluate(self, feed: DataFeed, required_tickers: list[str]) -> bool:
        market_state = feed.get_market_state(required_tickers)
        return self._evaluate(market_state)

    @abstractmethod
    def _evaluate(self, market_state: MarketState) -> bool:
        ...


@dataclass
class NumericCondition(Condition):
    ticker: str = ""
    operator: ComparisonOperator = ComparisonOperator.EQUAL
    value: float = 0.0
    logic: LogicOperator | None = None
    conditions: list["NumericCondition"] = field(default_factory=list)

    def _evaluate(self, market_state: MarketState) -> bool:
        if self.conditions:
            results = [child._evaluate(market_state) for child in self.conditions]
            if self.logic == LogicOperator.AND:
                return all(results)
            return any(results)

        snapshot = market_state.current.get(self.ticker)
        if snapshot is None:
            return False
        actual = snapshot.price

        match self.operator:
            case ComparisonOperator.GREATER_THAN:
                return actual > self.value
            case ComparisonOperator.LESS_THAN:
                return actual < self.value
            case ComparisonOperator.GREATER_OR_EQUAL:
                return actual >= self.value
            case ComparisonOperator.LESS_OR_EQUAL:
                return actual <= self.value
            case ComparisonOperator.EQUAL:
                return actual == self.value
