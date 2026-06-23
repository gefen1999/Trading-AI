import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "trading_agent"))

import prices

sys.modules["data_feed"] = prices

from parser.graph import parse_trading_query_once
from data_feed import get_prices
from evaluation import check_query

# Fixed input for now - a single hardcoded query string for quick testing.
# Not read from stdin/argv - just a constant in the code.
RAW_QUERY = "buy apple if price is above 200 and oil is below 50"
MAX_CLARIFICATION_ROUNDS = 3


def main():
    try:
        print(f"[1/4] Raw query: {RAW_QUERY}")

        history: list[tuple[str, str]] = []
        query = None

        for round_num in range(1, MAX_CLARIFICATION_ROUNDS + 1):
            outcome = parse_trading_query_once(RAW_QUERY, history=history)

            if outcome.query is not None:
                query = outcome.query
                break

            if outcome.needs_clarification:
                print(f"[Clarification {round_num}] {outcome.clarification_question}")
                answer = input("> ")
                history.append((outcome.clarification_question or "", answer))
                continue

            raise ValueError("; ".join(outcome.errors) or "Failed to parse query")
        else:
            raise ValueError("Too many clarification rounds")

        print(f"[2/4] Parsed query: action={query.action}, ticker={query.ticker}, "
              f"logic={query.logic}, conditions={query.conditions}")

        # Step 2: extract the tickers needed to check the conditions.
        # Note: TradingQuery has no `required_tickers` field (removed earlier) -
        # this is plain one-off wiring code, computed here directly from
        # query.conditions, not a reusable piece of logic in core.py/evaluation.py.
        tickers_needed = [condition.ticker for condition in query.conditions]
        print(f"[3/4] Fetching prices for: {tickers_needed}")

        # Step 3: fetch current prices
        prices = get_prices(tickers_needed)
        print(f"       Prices received: {prices}")

        # Step 4: evaluate the query against the fetched prices
        result = check_query(query, prices)
        print(f"[4/4] Result: should {query.action} {query.ticker}? -> {result}")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
