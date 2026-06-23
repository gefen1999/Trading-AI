from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph

from core import TradingQuery
from parser.graph_state import ParserState
from parser.nodes import parse_node, validate_node


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

    Clarification looping lives in run.py, not inside the graph.
    """
    graph = StateGraph(ParserState)
    graph.add_node("parse", parse_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


def _merge_clarifications(raw_text: str, history: list[tuple[str, str]]) -> str:
    if not history:
        return raw_text
    parts = [raw_text]
    for question, answer in history:
        parts.append(f"Clarification Q: {question}\nClarification A: {answer}")
    return "\n\n".join(parts)


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


def parse_trading_query_once(
    raw_text: str,
    *,
    history: list[tuple[str, str]] | None = None,
) -> ParseOutcome:
    """Run a single parse+validate pass and return structured outcome."""
    graph = build_parser_graph()
    clarification_history = history or []
    current_text = _merge_clarifications(raw_text, clarification_history)
    result = graph.invoke(_initial_state(current_text, clarification_history))

    return ParseOutcome(
        query=result["trading_query"],
        needs_clarification=result["needs_clarification"],
        clarification_question=result.get("clarification_question"),
        errors=list(result["validation_errors"]),
    )


def parse_trading_query(raw_text: str) -> TradingQuery:
    """
    Single-pass entry point — runs the graph once and returns a TradingQuery.
    Raises ValueError on hard validation failure or when clarification is needed.
    """
    outcome = parse_trading_query_once(raw_text)

    if outcome.query is not None:
        return outcome.query

    if outcome.needs_clarification:
        question = outcome.clarification_question or "Please clarify your query."
        raise ValueError(f"Clarification needed: {question}")

    if outcome.errors:
        raise ValueError("; ".join(outcome.errors))

    raise ValueError("Failed to produce a TradingQuery")
