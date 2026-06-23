import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import ActionType, ComparisonOperator, LogicMode, NumericCondition
from parser.graph import parse_trading_query
from parser.graph_state import ParserState
from parser.nodes import validate_node
from parser.schema import NumericConditionInput, ParsedQuery, ValidationAssessment


def _valid_assessment(**overrides) -> ValidationAssessment:
    defaults = {
        "is_valid": True,
        "needs_clarification": False,
        "clarification_question": None,
        "reason": None,
        "issues": [],
    }
    defaults.update(overrides)
    return ValidationAssessment(**defaults)


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
            issues=["Ticker APPLE could be AAPL or APLE"],
        )
        self.assertTrue(assessment.needs_clarification)
        self.assertEqual(assessment.reason, "ambiguous_ticker")


class TestValidateNode(unittest.TestCase):
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

    def _minimal_parsed(self, **overrides) -> ParsedQuery:
        defaults = {
            "action": "BUY",
            "ticker": "AAPL",
            "conditions": [NumericConditionInput(ticker="AAPL", operator=">", value=150.0)],
            "logic": "AND",
        }
        defaults.update(overrides)
        return ParsedQuery(**defaults)

    @patch("parser.nodes._call_ollama_validation", return_value=_valid_assessment())
    def test_builds_trading_query_from_parsed_query(self, _mock_validation):
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

    @patch("parser.nodes._call_ollama_validation", return_value=_valid_assessment())
    def test_or_logic_mapped_correctly(self, _mock_validation):
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

    @patch("parser.nodes._call_ollama_validation", return_value=_valid_assessment())
    def test_strips_ticker_whitespace(self, _mock_validation):
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

    @patch("parser.nodes._call_ollama_validation", return_value=_valid_assessment())
    def test_all_operators_mapped(self, _mock_validation):
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

    @patch(
        "parser.nodes._call_ollama_validation",
        return_value=ValidationAssessment(
            is_valid=False,
            needs_clarification=True,
            clarification_question="Which stock did you mean — AAPL or something else?",
            reason="ambiguous_ticker",
            issues=["Ticker is ambiguous"],
        ),
    )
    def test_needs_clarification_on_ambiguous_ticker(self, _mock_validation):
        result = validate_node(self._base_state(self._minimal_parsed()))
        self.assertTrue(result["needs_clarification"])
        self.assertIsNone(result["trading_query"])
        self.assertEqual(
            result["clarification_question"],
            "Which stock did you mean — AAPL or something else?",
        )
        self.assertEqual(result["clarification_reason"], "ambiguous_ticker")
        self.assertEqual(result["validation_errors"], [])

    @patch(
        "parser.nodes._call_ollama_validation",
        return_value=ValidationAssessment(
            is_valid=False,
            needs_clarification=False,
            clarification_question=None,
            reason=None,
            issues=["Parse does not match user intent", "Wrong action"],
        ),
    )
    def test_validation_errors_when_invalid_without_clarification(self, _mock_validation):
        result = validate_node(self._base_state(self._minimal_parsed()))
        self.assertFalse(result["needs_clarification"])
        self.assertIsNone(result["trading_query"])
        self.assertIn("Parse does not match user intent", result["validation_errors"])
        self.assertIn("Wrong action", result["validation_errors"])


class TestClarificationLoop(unittest.TestCase):
    @patch("parser.graph.build_parser_graph")
    def test_clarification_merge_appends_answer_to_raw_text(self, mock_build_graph):
        mock_graph = mock_build_graph.return_value
        mock_graph.invoke.side_effect = [
            {
                "trading_query": None,
                "needs_clarification": True,
                "clarification_question": "Which stock?",
                "validation_errors": [],
            },
            {
                "trading_query": None,
                "needs_clarification": False,
                "clarification_question": None,
                "validation_errors": ["Parse does not match user intent"],
            },
        ]

        answers = iter(["AAPL"])
        with self.assertRaises(ValueError):
            parse_trading_query(
                "buy apple when price > 100",
                ask_user=lambda q: next(answers),
            )

        second_call_state = mock_graph.invoke.call_args_list[1][0][0]
        self.assertEqual(
            second_call_state["raw_text"],
            "buy apple when price > 100\n\nClarification: AAPL",
        )
        self.assertEqual(
            second_call_state["clarification_history"],
            [("Which stock?", "AAPL")],
        )


if __name__ == "__main__":
    unittest.main()
