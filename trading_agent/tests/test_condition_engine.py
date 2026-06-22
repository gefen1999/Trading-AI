import unittest

from core.condition_engine import (
    ComparisonOperator,
    LogicOperator,
    NumericCondition,
)
from core.trading_query import ActionType, TradingQuery
from data.base import DataFeed
from data.market_state import MarketState, TickerSnapshot


def make_market_state(
    *,
    prices: dict[str, float] | None = None,
) -> MarketState:
    prices = prices or {}
    current = {
        ticker: TickerSnapshot(price=price, volume=0.0)
        for ticker, price in prices.items()
    }
    return MarketState(current=current, computed_features={})


class FakeDataFeed(DataFeed):
    def __init__(self, market_state: MarketState) -> None:
        self._market_state = market_state
        self.last_tickers: list[str] | None = None

    def get_market_state(self, tickers: list[str]) -> MarketState:
        self.last_tickers = tickers
        return self._market_state


def leaf(ticker: str, operator: ComparisonOperator, value: float) -> NumericCondition:
    return NumericCondition(ticker=ticker, operator=operator, value=value)


class TestNumericCondition(unittest.TestCase):
    def test_evaluate_price_true(self) -> None:
        condition = leaf("AAPL", ComparisonOperator.GREATER_THAN, 100.0)
        feed = FakeDataFeed(make_market_state(prices={"AAPL": 150.0}))

        self.assertTrue(condition.evaluate(feed, ["AAPL"]))

    def test_evaluate_price_false(self) -> None:
        condition = leaf("AAPL", ComparisonOperator.GREATER_THAN, 200.0)
        feed = FakeDataFeed(make_market_state(prices={"AAPL": 150.0}))

        self.assertFalse(condition.evaluate(feed, ["AAPL"]))

    def test_evaluate_missing_ticker_returns_false(self) -> None:
        condition = leaf("MSFT", ComparisonOperator.EQUAL, 300.0)
        feed = FakeDataFeed(make_market_state(prices={"AAPL": 150.0}))

        self.assertFalse(condition.evaluate(feed, ["AAPL"]))

    def test_and_logic(self) -> None:
        true_child = leaf("AAPL", ComparisonOperator.GREATER_THAN, 100.0)
        false_child = leaf("AAPL", ComparisonOperator.GREATER_THAN, 200.0)
        feed = FakeDataFeed(make_market_state(prices={"AAPL": 150.0}))

        all_true = NumericCondition(
            logic=LogicOperator.AND,
            conditions=[true_child, true_child],
        )
        mixed = NumericCondition(
            logic=LogicOperator.AND,
            conditions=[true_child, false_child],
        )

        self.assertTrue(all_true.evaluate(feed, ["AAPL"]))
        self.assertFalse(mixed.evaluate(feed, ["AAPL"]))

    def test_or_logic(self) -> None:
        true_child = leaf("AAPL", ComparisonOperator.GREATER_THAN, 100.0)
        false_child = leaf("AAPL", ComparisonOperator.GREATER_THAN, 200.0)
        feed = FakeDataFeed(make_market_state(prices={"AAPL": 150.0}))

        any_true = NumericCondition(
            logic=LogicOperator.OR,
            conditions=[false_child, true_child],
        )
        all_false = NumericCondition(
            logic=LogicOperator.OR,
            conditions=[false_child, false_child],
        )

        self.assertTrue(any_true.evaluate(feed, ["AAPL"]))
        self.assertFalse(all_false.evaluate(feed, ["AAPL"]))

    def test_nested_or_and(self) -> None:
        feed = FakeDataFeed(
            make_market_state(prices={"AAPL": 150.0, "MSFT": 80.0})
        )

        condition = NumericCondition(
            logic=LogicOperator.OR,
            conditions=[
                NumericCondition(
                    logic=LogicOperator.AND,
                    conditions=[
                        leaf("AAPL", ComparisonOperator.GREATER_THAN, 200.0),
                        leaf("MSFT", ComparisonOperator.GREATER_THAN, 100.0),
                    ],
                ),
                leaf("AAPL", ComparisonOperator.GREATER_THAN, 100.0),
            ],
        )

        self.assertTrue(condition.evaluate(feed, ["AAPL", "MSFT"]))


class TestTradingQueryEvaluate(unittest.TestCase):
    def test_evaluate_end_to_end(self) -> None:
        feed = FakeDataFeed(
            make_market_state(prices={"AAPL": 150.0, "USO": 60.0})
        )

        query = TradingQuery(
            action=ActionType.BUY,
            ticker="AAPL",
            condition=NumericCondition(
                logic=LogicOperator.AND,
                conditions=[
                    leaf("AAPL", ComparisonOperator.GREATER_THAN, 100.0),
                    leaf("USO", ComparisonOperator.LESS_THAN, 70.0),
                ],
            ),
            required_tickers=["AAPL", "USO"],
            raw_text="Buy AAPL when price > 100 and oil < 70",
        )

        self.assertTrue(query.condition.evaluate(feed, query.required_tickers))
        self.assertEqual(feed.last_tickers, ["AAPL", "USO"])

    def test_evaluate_returns_false_when_condition_fails(self) -> None:
        feed = FakeDataFeed(make_market_state(prices={"AAPL": 90.0}))

        query = TradingQuery(
            action=ActionType.SELL,
            ticker="AAPL",
            condition=leaf("AAPL", ComparisonOperator.GREATER_THAN, 100.0),
            required_tickers=["AAPL"],
            raw_text="Sell AAPL when price > 100",
        )

        self.assertFalse(query.condition.evaluate(feed, query.required_tickers))


if __name__ == "__main__":
    unittest.main()
