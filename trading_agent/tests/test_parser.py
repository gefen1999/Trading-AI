import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import ActionType, ComparisonOperator, LogicMode, NumericCondition, TradingQuery
from parser.graph import _merge_clarifications, parse_trading_query, parse_trading_query_once
from parser.graph_state import ParserState
from parser.nodes import validate_node
from parser.schema import NumericConditionInput, ParsedQuery, ValidationAssessment


def _valid_assessment() -> ValidationAssessment:
    return ValidationAssessment(
        is_valid=True,
        needs_clarification=False,
        clarification_question=None,
        reason=None,
        issues=[],
    )


class TestNumericConditionInput(unittest.TestCase):
    def test_valid_condition(self):
        cond = NumericConditionInput(ticker="AAPL", operator=">", value=150.0)
        self.assertEqual(cond.ticker, "AAPL")
        self.assertEqual(cond.operator, ">")
        self.assertEqual(cond.value, 150.0)

    def test_invalid_operator_rejected(self):
        with self.assertRaises(ValidationError):
            NumericConditionInput(ticker="AAPL", operator="!=", value=100.0)

    def test_all_valid_operators(self):
        for op in (">", "<", ">=", "<=", "=="):
            cond = NumericConditionInput(ticker="AAPL", operator=op, value=1.0)
            self.assertEqual(cond.operator, op)


class TestParsedQuery(unittest.TestCase):
    def _minimal_query(self, **overrides):
        defaults = {
            "action": "BUY",
            "ticker": "AAPL",
            "conditions": [{"ticker": "AAPL", "operator": ">", "value": 100.0}],
            "logic": "AND",
        }
        defaults.update(overrides)
        return ParsedQuery(**defaults)

    def test_valid_query(self):
        query = self._minimal_query()
        self.assertEqual(query.action, "BUY")
        self.assertEqual(query.ticker, "AAPL")
        self.assertEqual(len(query.conditions), 1)
        self.assertEqual(query.logic, "AND")

    def test_empty_conditions_rejected(self):
        with self.assertRaises(ValidationError):
            self._minimal_query(conditions=[])

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValidationError):
            self._minimal_query(action="HOLD")

    def test_invalid_logic_rejected(self):
        with self.assertRaises(ValidationError):
            self._minimal_query(logic="XOR")

    def test_or_logic_accepted(self):
        query = self._minimal_query(logic="OR")
        self.assertEqual(query.logic, "OR")

    def test_sell_action_accepted(self):
        query = self._minimal_query(action="SELL")
        self.assertEqual(query.action, "SELL")

    def test_multiple_conditions(self):
        query = self._minimal_query(
            conditions=[
                {"ticker": "AAPL", "operator": ">", "value": 150.0},
                {"ticker": "MSFT", "operator": "<", "value": 400.0},
            ]
        )
        self.assertEqual(len(query.conditions), 2)


class TestValidationAssessment(unittest.TestCase):
    def test_clarification_fields(self):
        assessment = ValidationAssessment(
            is_valid=False,
            needs_clarification=True,
            clarification_question="Which stock did you mean?",
            reason="ambiguous_ticker",
            issues=["Ticker is ambiguous"],
        )
        self.assertTrue(assessment.needs_clarification)
        self.assertEqual(assessment.reason, "ambiguous_ticker")


class TestValidateNode(unittest.TestCase):
    def setUp(self):
        self.validation_patcher = patch("parser.nodes._call_llm_validation")
        self.mock_validation = self.validation_patcher.start()
        self.mock_validation.return_value = _valid_assessment()

    def tearDown(self):
        self.validation_patcher.stop()

    def _base_state(self, parsed_query: ParsedQuery | None = None) -> ParserState:
        return {
            "raw_text": "Buy AAPL when price > 150",
            "parsed_query": parsed_query,
            "validation_errors": [],
            "needs_clarification": False,
            "clarification_question": None,
            "clarification_reason": None,
            "clarification_history": [],
            "trading_query": None,
        }

    def test_builds_trading_query_from_parsed_query(self):
        parsed = ParsedQuery(
            action="BUY",
            ticker="AAPL",
            conditions=[
                NumericConditionInput(ticker="AAPL", operator=">", value=150.0),
                NumericConditionInput(ticker="MSFT", operator="<", value=400.0),
            ],
            logic="AND",
        )
        state = self._base_state(parsed)
        result = validate_node(state)

        trading_query = result["trading_query"]
        self.assertIsNotNone(trading_query)
        self.assertEqual(trading_query.action, ActionType.BUY)
        self.assertEqual(trading_query.ticker, "AAPL")
        self.assertEqual(trading_query.logic, LogicMode.AND)
        self.assertEqual(trading_query.raw_text, "Buy AAPL when price > 150")
        self.assertEqual(len(trading_query.conditions), 2)

        self.assertEqual(trading_query.conditions[0], NumericCondition(
            ticker="AAPL", operator=ComparisonOperator.GREATER_THAN, value=150.0
        ))
        self.assertEqual(trading_query.conditions[1], NumericCondition(
            ticker="MSFT", operator=ComparisonOperator.LESS_THAN, value=400.0
        ))

    def test_or_logic_mapped_correctly(self):
        parsed = ParsedQuery(
            action="SELL",
            ticker="TSLA",
            conditions=[
                NumericConditionInput(ticker="TSLA", operator=">", value=300.0),
                NumericConditionInput(ticker="TSLA", operator="<", value=100.0),
            ],
            logic="OR",
        )
        result = validate_node(self._base_state(parsed))
        self.assertEqual(result["trading_query"].logic, LogicMode.OR)
        self.assertEqual(result["trading_query"].action, ActionType.SELL)

    def test_strips_ticker_whitespace(self):
        parsed = ParsedQuery(
            action="BUY",
            ticker="  AAPL  ",
            conditions=[NumericConditionInput(ticker=" AAPL ", operator=">=", value=50.0)],
            logic="AND",
        )
        result = validate_node(self._base_state(parsed))
        self.assertEqual(result["trading_query"].ticker, "AAPL")
        self.assertEqual(result["trading_query"].conditions[0].ticker, "AAPL")

    def test_no_parsed_query_adds_error(self):
        state = self._base_state()
        result = validate_node(state)
        self.assertIsNone(result["trading_query"])
        self.assertIn("No parsed query to validate", result["validation_errors"])
        self.mock_validation.assert_not_called()

    def test_empty_ticker_adds_error(self):
        parsed = ParsedQuery(
            action="BUY",
            ticker="",
            conditions=[NumericConditionInput(ticker="AAPL", operator=">", value=100.0)],
            logic="AND",
        )
        result = validate_node(self._base_state(parsed))
        self.assertIsNone(result["trading_query"])
        self.assertTrue(any("ticker" in e for e in result["validation_errors"]))
        self.mock_validation.assert_not_called()

    def test_empty_condition_ticker_adds_error(self):
        parsed = ParsedQuery(
            action="BUY",
            ticker="AAPL",
            conditions=[NumericConditionInput(ticker="", operator=">", value=100.0)],
            logic="AND",
        )
        result = validate_node(self._base_state(parsed))
        self.assertIsNone(result["trading_query"])
        self.assertTrue(any("condition 0" in e for e in result["validation_errors"]))
        self.mock_validation.assert_not_called()

    def test_all_operators_mapped(self):
        operator_map = {
            ">": ComparisonOperator.GREATER_THAN,
            "<": ComparisonOperator.LESS_THAN,
            ">=": ComparisonOperator.GREATER_OR_EQUAL,
            "<=": ComparisonOperator.LESS_OR_EQUAL,
            "==": ComparisonOperator.EQUAL,
        }
        for op_str, op_enum in operator_map.items():
            parsed = ParsedQuery(
                action="BUY",
                ticker="AAPL",
                conditions=[NumericConditionInput(ticker="AAPL", operator=op_str, value=100.0)],
                logic="AND",
            )
            result = validate_node(self._base_state(parsed))
            self.assertEqual(result["trading_query"].conditions[0].operator, op_enum)

    def test_needs_clarification_when_assessment_ambiguous(self):
        self.mock_validation.return_value = ValidationAssessment(
            is_valid=False,
            needs_clarification=True,
            clarification_question="Which stock did you mean — AAPL or something else?",
            reason="ambiguous_ticker",
            issues=[],
        )
        parsed = ParsedQuery(
            action="BUY",
            ticker="APPLE",
            conditions=[NumericConditionInput(ticker="APPLE", operator=">", value=150.0)],
            logic="AND",
        )
        result = validate_node(self._base_state(parsed))

        self.assertTrue(result["needs_clarification"])
        self.assertEqual(
            result["clarification_question"],
            "Which stock did you mean — AAPL or something else?",
        )
        self.assertEqual(result["clarification_reason"], "ambiguous_ticker")
        self.assertIsNone(result["trading_query"])
        self.assertEqual(result["validation_errors"], [])

    def test_builds_trading_query_when_assessment_valid(self):
        parsed = ParsedQuery(
            action="BUY",
            ticker="AAPL",
            conditions=[NumericConditionInput(ticker="AAPL", operator=">", value=150.0)],
            logic="AND",
        )
        result = validate_node(self._base_state(parsed))

        self.assertFalse(result["needs_clarification"])
        self.assertIsNotNone(result["trading_query"])
        self.assertEqual(result["trading_query"].ticker, "AAPL")

    def test_adds_validation_errors_when_invalid_without_clarification(self):
        self.mock_validation.return_value = ValidationAssessment(
            is_valid=False,
            needs_clarification=False,
            clarification_question=None,
            reason="other",
            issues=["Parse does not match raw text"],
        )
        parsed = ParsedQuery(
            action="BUY",
            ticker="AAPL",
            conditions=[NumericConditionInput(ticker="AAPL", operator=">", value=150.0)],
            logic="AND",
        )
        result = validate_node(self._base_state(parsed))

        self.assertIsNone(result["trading_query"])
        self.assertFalse(result["needs_clarification"])
        self.assertIn("Parse does not match raw text", result["validation_errors"])


class TestParseTradingQueryOnce(unittest.TestCase):
    @patch("parser.graph.build_parser_graph")
    def test_returns_query_on_success(self, mock_build_graph):
        trading_query = TradingQuery(
            action=ActionType.BUY,
            ticker="AAPL",
            conditions=[NumericCondition(ticker="AAPL", operator=ComparisonOperator.GREATER_THAN, value=150.0)],
            logic=LogicMode.AND,
            raw_text="buy apple",
        )
        mock_graph = mock_build_graph.return_value
        mock_graph.invoke.return_value = {
            "trading_query": trading_query,
            "needs_clarification": False,
            "clarification_question": None,
            "validation_errors": [],
        }

        outcome = parse_trading_query_once("buy apple")
        self.assertIs(outcome.query, trading_query)
        self.assertFalse(outcome.needs_clarification)
        self.assertEqual(outcome.errors, [])

    @patch("parser.graph.build_parser_graph")
    def test_returns_clarification_outcome(self, mock_build_graph):
        mock_graph = mock_build_graph.return_value
        mock_graph.invoke.return_value = {
            "trading_query": None,
            "needs_clarification": True,
            "clarification_question": "Which ticker?",
            "validation_errors": [],
        }

        outcome = parse_trading_query_once("buy apple")
        self.assertIsNone(outcome.query)
        self.assertTrue(outcome.needs_clarification)
        self.assertEqual(outcome.clarification_question, "Which ticker?")

    @patch("parser.graph.build_parser_graph")
    def test_merge_includes_prior_q_and_a(self, mock_build_graph):
        mock_graph = mock_build_graph.return_value
        mock_graph.invoke.return_value = {
            "trading_query": None,
            "needs_clarification": True,
            "clarification_question": "Which ticker?",
            "validation_errors": [],
        }

        history = [("Which ticker?", "AAPL")]
        parse_trading_query_once("buy apple", history=history)

        state = mock_graph.invoke.call_args[0][0]
        self.assertIn("Clarification Q: Which ticker?", state["raw_text"])
        self.assertIn("Clarification A: AAPL", state["raw_text"])
        self.assertEqual(state["clarification_history"], history)


class TestParseTradingQuery(unittest.TestCase):
    @patch("parser.graph.parse_trading_query_once")
    def test_raises_when_clarification_needed(self, mock_once):
        mock_once.return_value = type("Outcome", (), {
            "query": None,
            "needs_clarification": True,
            "clarification_question": "Which ticker?",
            "errors": [],
        })()

        with self.assertRaises(ValueError) as ctx:
            parse_trading_query("buy apple")
        self.assertIn("Clarification needed", str(ctx.exception))


class TestMergeClarifications(unittest.TestCase):
    def test_returns_raw_text_when_no_history(self):
        self.assertEqual(_merge_clarifications("buy apple", []), "buy apple")

    def test_merge_clarifications_accumulates_history(self):
        merged = _merge_clarifications(
            "buy apple",
            [
                ("Which ticker?", "AAPL"),
                ("What threshold?", "200"),
            ],
        )
        self.assertIn("buy apple", merged)
        self.assertIn("Clarification Q: Which ticker?", merged)
        self.assertIn("Clarification A: AAPL", merged)
        self.assertIn("Clarification Q: What threshold?", merged)
        self.assertIn("Clarification A: 200", merged)


if __name__ == "__main__":
    unittest.main()
