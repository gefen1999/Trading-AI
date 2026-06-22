import os

from dotenv import load_dotenv

from core import ActionType, ComparisonOperator, LogicMode, NumericCondition, TradingQuery
from parser.graph_state import ParserState
from parser.prompts import SYSTEM_PROMPT
from parser.schema import ParsedQuery


def _call_ollama(raw_text: str) -> ParsedQuery:
    from ollama import Client

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1")

    client = Client(host=host)
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        format=ParsedQuery.model_json_schema(),
    )
    content = response["message"]["content"]
    return ParsedQuery.model_validate_json(content)


def parse_node(state: ParserState) -> ParserState:
    """
    Sends state["raw_text"] + the system prompt (from prompts.py) to the
    local LLM (via Ollama), requesting structured output per the
    ParsedQuery schema. Updates and returns state with a fully populated
    parsed_query.
    """
    load_dotenv()
    raw_text = state["raw_text"]

    # TODO: implement clarification loop — if the query is ambiguous, set
    # needs_clarification=True and route back to ask_user_node instead of
    # calling the LLM again with the same text.

    try:
        parsed_query = _call_ollama(raw_text)
    except Exception as exc:
        state["validation_errors"].append(f"LLM parse failed: {exc}")
        return state

    state["parsed_query"] = parsed_query
    return state


def validate_node(state: ParserState) -> ParserState:
    """
    Builds a TradingQuery directly from parsed_query - this is now a
    straightforward field-by-field mapping, NOT tree construction:
        - action: ParsedQuery.action -> TradingQuery.action
        - ticker: ParsedQuery.ticker -> TradingQuery.ticker
        - conditions: each NumericConditionInput -> a core.NumericCondition
          (ticker, operator, value - direct copy, no wrapping)
        - logic: ParsedQuery.logic -> TradingQuery.logic
        - raw_text: state["raw_text"] -> TradingQuery.raw_text

    Also do basic semantic validation before building (e.g. ticker is a
    non-empty string, conditions list is non-empty - Pydantic already
    covers most of this during parse, this is a light extra check).

    Updates state["trading_query"] with the result, or
    state["validation_errors"] if it fails.
    """
    parsed = state.get("parsed_query")
    if parsed is None:
        if not state["validation_errors"]:
            state["validation_errors"].append("No parsed query to validate")
        return state

    errors: list[str] = []

    if not parsed.ticker or not parsed.ticker.strip():
        errors.append("ticker must be a non-empty string")

    if not parsed.conditions:
        errors.append("conditions list must not be empty")

    for i, cond in enumerate(parsed.conditions):
        if not cond.ticker or not cond.ticker.strip():
            errors.append(f"condition {i}: ticker must be a non-empty string")

    if errors:
        state["validation_errors"].extend(errors)
        return state

    conditions = [
        NumericCondition(
            ticker=cond.ticker.strip(),
            operator=ComparisonOperator(cond.operator),
            value=cond.value,
        )
        for cond in parsed.conditions
    ]

    state["trading_query"] = TradingQuery(
        action=ActionType(parsed.action),
        ticker=parsed.ticker.strip(),
        conditions=conditions,
        logic=LogicMode(parsed.logic),
        raw_text=state["raw_text"],
    )
    return state