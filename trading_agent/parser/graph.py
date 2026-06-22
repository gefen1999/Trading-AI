from langgraph.graph import END, START, StateGraph

from core import TradingQuery
from parser.graph_state import ParserState
from parser.nodes import parse_node, validate_node


def build_parser_graph():
    """
    Builds and returns the compiled graph:
    START -> parse_node -> validate_node -> END

    This is v1 - a linear graph only. Keeping the infrastructure (state
    with needs_clarification) allows adding a conditional edge in the
    future: validate_node -> {needs_clarification?} -> ask_user_node / END
    without changing existing nodes.
    """
    graph = StateGraph(ParserState)
    graph.add_node("parse", parse_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


def parse_trading_query(raw_text: str) -> TradingQuery:
    """
    Convenient entry point - runs the graph on raw_text, returns a
    TradingQuery (or raises/returns an error if validation fails -
    depending on what ParserState holds).
    """
    graph = build_parser_graph()
    initial_state: ParserState = {
        "raw_text": raw_text,
        "parsed_query": None,
        "validation_errors": [],
        "needs_clarification": False,
        "trading_query": None,
    }
    result = graph.invoke(initial_state)

    if result["validation_errors"]:
        raise ValueError("; ".join(result["validation_errors"]))

    if result["trading_query"] is None:
        raise ValueError("Failed to produce a TradingQuery")

    return result["trading_query"]
