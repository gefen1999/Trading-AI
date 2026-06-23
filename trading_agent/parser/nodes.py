import os
from pathlib import Path

from dotenv import load_dotenv

from core import ActionType, ComparisonOperator, LogicMode, NumericCondition, TradingQuery
from parser.graph_state import ParserState
from parser.prompts import SYSTEM_PROMPT, VALIDATION_PROMPT
from parser.schema import ParsedQuery, ValidationAssessment

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


def _load_env() -> None:
    load_dotenv(_ENV_FILE)


def _get_llm_provider() -> str:
    _load_env()
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider in ("anthropic", "openai"):
        return provider
    if os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        return "openai"
    return "anthropic"


def _validation_user_message(raw_text: str, parsed_query: ParsedQuery) -> str:
    return VALIDATION_PROMPT.format(
        raw_text=raw_text,
        parsed_json=parsed_query.model_dump_json(indent=2),
    )


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


def _call_anthropic_validation(raw_text: str, parsed_query: ParsedQuery) -> ValidationAssessment:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    user_message = _validation_user_message(raw_text, parsed_query)

    message = client.beta.messages.parse(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": user_message}],
        output_format=ValidationAssessment,
    )
    if message.parsed_output is None:
        raise ValueError("LLM returned no structured validation output")
    return message.parsed_output


def _call_openai_validation(raw_text: str, parsed_query: ParsedQuery) -> ValidationAssessment:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    user_message = _validation_user_message(raw_text, parsed_query)

    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": user_message}],
        response_format=ValidationAssessment,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("LLM returned no structured validation output")
    return parsed


def _call_llm_validation(raw_text: str, parsed_query: ParsedQuery) -> ValidationAssessment:
    """Semantic validation via the configured LLM provider."""
    _load_env()
    provider = _get_llm_provider()
    if provider == "openai":
        return _call_openai_validation(raw_text, parsed_query)
    return _call_anthropic_validation(raw_text, parsed_query)


def _build_trading_query(state: ParserState, parsed: ParsedQuery) -> TradingQuery:
    conditions = [
        NumericCondition(
            ticker=cond.ticker.strip(),
            operator=ComparisonOperator(cond.operator),
            value=cond.value,
        )
        for cond in parsed.conditions
    ]

    return TradingQuery(
        action=ActionType(parsed.action),
        ticker=parsed.ticker.strip(),
        conditions=conditions,
        logic=LogicMode(parsed.logic),
        raw_text=state["raw_text"],
    )


def parse_node(state: ParserState) -> ParserState:
    """
    Sends state["raw_text"] + the system prompt (from prompts.py) to the
    LLM API, requesting structured output per the ParsedQuery schema.
    Updates and returns state with a fully populated parsed_query.
    """
    _load_env()
    raw_text = state["raw_text"]

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
    Phase A — fast rule checks, then Phase B — semantic LLM validation.

    If clarification is needed, sets needs_clarification and a user-facing
    question without treating it as a hard validation failure.
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

    try:
        assessment = _call_llm_validation(state["raw_text"], parsed)
    except Exception as exc:
        state["validation_errors"].append(f"Semantic validation failed: {exc}")
        return state

    if assessment.needs_clarification:
        state["needs_clarification"] = True
        state["clarification_question"] = assessment.clarification_question
        state["clarification_reason"] = assessment.reason
        return state

    if not assessment.is_valid:
        state["validation_errors"].extend(assessment.issues or ["Parse failed semantic validation"])
        return state

    state["needs_clarification"] = False
    state["clarification_question"] = None
    state["clarification_reason"] = None
    state["trading_query"] = _build_trading_query(state, parsed)
    return state
