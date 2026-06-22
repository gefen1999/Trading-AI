import os
from pathlib import Path

from dotenv import load_dotenv

from core import ActionType, ComparisonOperator, LogicMode, NumericCondition, TradingQuery

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


def _load_env() -> None:
    load_dotenv(_ENV_FILE)
from parser.graph_state import ParserState
from parser.prompts import SYSTEM_PROMPT
from parser.schema import ParsedQuery


def _get_llm_provider() -> str:
    _load_env()
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider in ("anthropic", "openai"):
        return provider
    if os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        return "openai"
    return "anthropic"


def _call_anthropic(raw_text: str) -> ParsedQuery:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    message = client.beta.messages.parse(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": raw_text}],
        output_format=ParsedQuery,
    )
    if message.parsed_output is None:
        raise ValueError("LLM returned no structured output")
    return message.parsed_output


def _call_openai(raw_text: str) -> ParsedQuery:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        response_format=ParsedQuery,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("LLM returned no structured output")
    return parsed


def parse_node(state: ParserState) -> ParserState:
    """
    Sends state["raw_text"] + the system prompt (from prompts.py) to the
    LLM API, requesting structured output per the ParsedQuery schema.
    Updates and returns state with a fully populated parsed_query.
    """
    _load_env()
    raw_text = state["raw_text"]

    # TODO: implement clarification loop — if the query is ambiguous, set
    # needs_clarification=True and route back to ask_user_node instead of
    # calling the LLM again with the same text.

    try:
        provider = _get_llm_provider()
        if provider == "openai":
            parsed_query = _call_openai(raw_text)
        else:
            parsed_query = _call_anthropic(raw_text)
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
