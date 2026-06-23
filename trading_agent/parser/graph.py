from dataclasses import dataclass
from typing import Callable

from langgraph.graph import END, START, StateGraph

from core import TradingQuery
from parser.graph_state import ParserState
from parser.nodes import parse_node, validate_node


def _default_ask_user(question: str) -> str:
    return input(f"{question}\n> ")


@dataclass
class ParseOutcome:
    query: TradingQuery | None
    needs_clarification: bool
    clarification_question: str | None
    errors: list[str]


def build_parser_graph():
    """
    Builds and returns the compiled graph:
    START -> parse_node -> validate_node -> END

    Clarification looping lives in parse_trading_query, not inside the graph.
    """
    graph = StateGraph(ParserState)
    graph.add_node("parse", parse_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


def _initial_state(raw_text: str, history: list[tuple[str, str]]) -> ParserState:
    return {
        "raw_text": raw_text,
        "parsed_query": None,
        "validation_errors": [],
        "needs_clarification": False,
        "clarification_question": None,
        "clarification_reason": None,
        "clarification_history": history,
        "trading_query": None,
    }


def parse_trading_query(
    raw_text: str,
    *,
    ask_user: Callable[[str], str] = _default_ask_user,
    max_rounds: int = 3,
) -> TradingQuery:
    """
    Runs the parser graph with an outer clarification loop. Returns a
    TradingQuery or raises ValueError on hard validation failure.
    """
    graph = build_parser_graph()
    history: list[tuple[str, str]] = []
    current_text = raw_text

    for _ in range(max_rounds):
        result = graph.invoke(_initial_state(current_text, history))

        if result["trading_query"] is not None:
            return result["trading_query"]

        if result["needs_clarification"]:
            question = result.get("clarification_question") or "Could you clarify your request?"
            answer = ask_user(question)
            history.append((question, answer))
            current_text = f"{raw_text}\n\nClarification: {answer}"
            continue

        if result["validation_errors"]:
            raise ValueError("; ".join(result["validation_errors"]))

        raise ValueError("Failed to produce a TradingQuery")

    raise ValueError("Too many clarification rounds")


def parse_trading_query_outcome(
    raw_text: str,
    *,
    ask_user: Callable[[str], str] = _default_ask_user,
    max_rounds: int = 3,
) -> ParseOutcome:
    """Like parse_trading_query but returns a ParseOutcome instead of raising."""
    graph = build_parser_graph()
    history: list[tuple[str, str]] = []
    current_text = raw_text

    for _ in range(max_rounds):
        result = graph.invoke(_initial_state(current_text, history))

        if result["trading_query"] is not None:
            return ParseOutcome(
                query=result["trading_query"],
                needs_clarification=False,
                clarification_question=None,
                errors=[],
            )

        if result["needs_clarification"]:
            question = result.get("clarification_question")
            answer = ask_user(question or "Could you clarify your request?")
            history.append((question or "", answer))
            current_text = f"{raw_text}\n\nClarification: {answer}"
            continue

        return ParseOutcome(
            query=None,
            needs_clarification=False,
            clarification_question=None,
            errors=result["validation_errors"],
        )

    return ParseOutcome(
        query=None,
        needs_clarification=False,
        clarification_question=None,
        errors=["Too many clarification rounds"],
    )
