# coursor_1

Natural-language trading query agent. Parses free-text buy/sell instructions (Hebrew or English), fetches live prices, and evaluates whether the conditions are met.

## How it works

1. **Parse** — An LLM (Anthropic or OpenAI) converts natural language into a structured `TradingQuery` via a LangGraph pipeline.
2. **Fetch** — Current prices are loaded from Yahoo Finance using [yfinance](https://github.com/ranaroussi/yfinance) (no API key required).
3. **Evaluate** — Conditions are checked against the fetched prices using AND/OR logic.

Example query:

```
buy apple if price is above 200 and oil is below 50
```

## Requirements

- Python 3.10+
- Internet access (LLM API + Yahoo Finance)
- An API key for Anthropic or OpenAI

## Setup

```bash
git clone https://github.com/gefen1999/coursor_1.git
cd coursor_1
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
# Required — pick one provider
ANTHROPIC_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here

# Optional
LLM_PROVIDER=anthropic          # anthropic | openai (auto-detected if omitted)
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4o
```

If `LLM_PROVIDER` is not set, Anthropic is used when `ANTHROPIC_API_KEY` is present; OpenAI is used when only `OPENAI_API_KEY` is set.

## Run

The entry point is `run.py`. It currently uses a hardcoded query for quick testing — edit `RAW_QUERY` in that file to try different inputs.

```bash
python3 run.py
```

Expected output (values will vary with live prices):

```
[1/4] Raw query: buy apple if price is above 200 and oil is below 50
[2/4] Parsed query: action=ActionType.BUY, ticker=AAPL, logic=LogicMode.AND, conditions=[...]
[3/4] Fetching prices for: ['AAPL', 'CL=F']
       Prices received: {'AAPL': 198.5, 'CL=F': 72.3}
[4/4] Result: should ActionType.BUY AAPL? -> False
```

## Run tests

Unit tests cover the condition engine, parser validation, and price fetching (mocked — no network calls).

```bash
python3 -m unittest discover -s trading_agent/tests -v
```

Or run a single module:

```bash
python3 -m unittest trading_agent.tests.test_evaluation -v
python3 -m unittest trading_agent.tests.test_parser -v
python3 -m unittest trading_agent.tests.test_prices -v
```

## Project structure

```
coursor_1/
├── run.py                      # End-to-end demo entry point
├── requirements.txt
├── trading_agent/
│   ├── core.py                 # TradingQuery, conditions, enums
│   ├── evaluation.py           # check_query — evaluates conditions vs prices
│   ├── prices.py               # get_prices — yfinance wrapper
│   ├── parser/
│   │   ├── graph.py            # LangGraph pipeline (parse → validate)
│   │   ├── nodes.py            # LLM calls + validation node
│   │   ├── prompts.py          # System prompt for the parser
│   │   └── schema.py           # Pydantic models for LLM output
│   └── tests/
│       ├── test_evaluation.py
│       ├── test_parser.py
│       └── test_prices.py
```

## Query format

A parsed query has:

| Field | Description |
|-------|-------------|
| `action` | `BUY` or `SELL` |
| `ticker` | Primary asset to trade (e.g. `AAPL`) |
| `conditions` | List of price comparisons (`ticker`, `operator`, `value`) |
| `logic` | `AND` (all conditions must hold) or `OR` (at least one) |

Supported operators: `>`, `<`, `>=`, `<=`, `==`.

Company names in Hebrew or English are mapped to ticker symbols (e.g. "apple" / "אפל" → `AAPL`, "oil" / "נפט" → `CL=F`).

## Open in Cursor

1. **File → Open Folder** and select the `coursor_1` directory.
2. Open Terminal (`` Ctrl+` ``), activate your virtualenv, and run `python3 run.py` or the test command above.
