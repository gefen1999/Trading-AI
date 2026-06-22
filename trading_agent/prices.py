import yfinance as yf


def get_prices(tickers: list[str]) -> dict[str, float]:
    """
    Fetches current prices for a list of tickers via yfinance (no API key
    needed). Returns only the tickers that succeeded - a single bad/missing
    ticker must not raise and must not prevent the others from being
    returned.

    Note: yfinance accesses query1/query2.finance.yahoo.com - requires
    normal internet access (will not work in a sandboxed environment with
    a restricted network allowlist).

    Implementation:
    1. For each ticker in `tickers`, call yf.Ticker(ticker).fast_info and
       read `lastPrice`.
    2. Wrap each individual fetch in a try/except - on any failure
       (network error, invalid ticker, missing price) skip that ticker
       (do not add it to the result dict), do not raise.
    3. Return a dict mapping ticker -> float price, containing only the
       tickers that were successfully fetched.
    """
    prices: dict[str, float] = {}

    for ticker in tickers:
        try:
            last_price = yf.Ticker(ticker).fast_info["lastPrice"]
            if last_price is None:
                continue
            prices[ticker] = float(last_price)
        except Exception:
            continue

    return prices
