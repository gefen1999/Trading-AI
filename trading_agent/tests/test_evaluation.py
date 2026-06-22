import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import (
    ActionType,
    ComparisonOperator,
    LogicMode,
    NumericCondition,
    TradingQuery,
)
from evaluation import check_query


def make_query(
    conditions: list[NumericCondition],
    logic: LogicMode = LogicMode.AND,
) -> TradingQuery:
    return TradingQuery(
        action=ActionType.BUY,
        ticker="AAPL",
        conditions=conditions,
        logic=logic,
        raw_text="test query",
    )


class TestCheckQuery(unittest.TestCase):
    def test_single_condition_and_holds(self):
        query = make_query(
            [NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 100.0)]
        )
        self.assertTrue(check_query(query, {"AAPL": 150.0}))

    def test_single_condition_does_not_hold(self):
        query = make_query(
            [NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 100.0)]
        )
        self.assertFalse(check_query(query, {"AAPL": 50.0}))

    def test_multiple_conditions_and_all_hold(self):
        query = make_query(
            [
                NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 100.0),
                NumericCondition("MSFT", ComparisonOperator.LESS_THAN, 400.0),
            ]
        )
        self.assertTrue(check_query(query, {"AAPL": 150.0, "MSFT": 300.0}))

    def test_multiple_conditions_and_one_fails(self):
        query = make_query(
            [
                NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 100.0),
                NumericCondition("MSFT", ComparisonOperator.LESS_THAN, 200.0),
            ]
        )
        self.assertFalse(check_query(query, {"AAPL": 150.0, "MSFT": 300.0}))

    def test_multiple_conditions_or_at_least_one_holds(self):
        query = make_query(
            [
                NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 200.0),
                NumericCondition("MSFT", ComparisonOperator.LESS_THAN, 400.0),
            ],
            logic=LogicMode.OR,
        )
        self.assertTrue(check_query(query, {"AAPL": 150.0, "MSFT": 300.0}))

    def test_multiple_conditions_or_none_hold(self):
        query = make_query(
            [
                NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 200.0),
                NumericCondition("MSFT", ComparisonOperator.LESS_THAN, 100.0),
            ],
            logic=LogicMode.OR,
        )
        self.assertFalse(check_query(query, {"AAPL": 150.0, "MSFT": 300.0}))

    def test_missing_ticker_evaluates_to_false(self):
        query = make_query(
            [
                NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 100.0),
                NumericCondition("GOOG", ComparisonOperator.GREATER_THAN, 100.0),
            ]
        )
        self.assertFalse(check_query(query, {"AAPL": 150.0}))

    def test_missing_ticker_does_not_raise(self):
        query = make_query(
            [NumericCondition("MISSING", ComparisonOperator.EQUAL, 10.0)]
        )
        try:
            result = check_query(query, {})
        except KeyError:
            self.fail("check_query raised KeyError for missing ticker")
        self.assertFalse(result)

    def test_operator_greater_than(self):
        query = make_query(
            [NumericCondition("AAPL", ComparisonOperator.GREATER_THAN, 100.0)]
        )
        self.assertTrue(check_query(query, {"AAPL": 100.01}))
        self.assertFalse(check_query(query, {"AAPL": 100.0}))

    def test_operator_less_than(self):
        query = make_query(
            [NumericCondition("AAPL", ComparisonOperator.LESS_THAN, 100.0)]
        )
        self.assertTrue(check_query(query, {"AAPL": 99.99}))
        self.assertFalse(check_query(query, {"AAPL": 100.0}))

    def test_operator_greater_or_equal(self):
        query = make_query(
            [NumericCondition("AAPL", ComparisonOperator.GREATER_OR_EQUAL, 100.0)]
        )
        self.assertTrue(check_query(query, {"AAPL": 100.0}))
        self.assertFalse(check_query(query, {"AAPL": 99.99}))

    def test_operator_less_or_equal(self):
        query = make_query(
            [NumericCondition("AAPL", ComparisonOperator.LESS_OR_EQUAL, 100.0)]
        )
        self.assertTrue(check_query(query, {"AAPL": 100.0}))
        self.assertFalse(check_query(query, {"AAPL": 100.01}))

    def test_operator_equal(self):
        query = make_query(
            [NumericCondition("AAPL", ComparisonOperator.EQUAL, 100.0)]
        )
        self.assertTrue(check_query(query, {"AAPL": 100.0}))
        self.assertFalse(check_query(query, {"AAPL": 100.01}))


if __name__ == "__main__":
    unittest.main()
