import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prices import get_prices


class TestGetPrices(unittest.TestCase):
    @patch("prices.yf.Ticker")
    def test_returns_prices_for_valid_tickers(self, mock_ticker_cls):
        def make_ticker(symbol, price):
            mock = MagicMock()
            mock.fast_info = {"lastPrice": price}
            return mock

        mock_ticker_cls.side_effect = [
            make_ticker("AAPL", 150.0),
            make_ticker("MSFT", 300.0),
        ]

        result = get_prices(["AAPL", "MSFT"])

        self.assertEqual(result, {"AAPL": 150.0, "MSFT": 300.0})

    @patch("prices.yf.Ticker")
    def test_skips_invalid_ticker_without_raising(self, mock_ticker_cls):
        good = MagicMock()
        good.fast_info = {"lastPrice": 150.0}

        bad = MagicMock()
        bad.fast_info = {"lastPrice": None}

        mock_ticker_cls.side_effect = [good, bad]

        result = get_prices(["AAPL", "INVALID"])

        self.assertEqual(result, {"AAPL": 150.0})

    @patch("prices.yf.Ticker")
    def test_skips_ticker_on_fetch_failure(self, mock_ticker_cls):
        good = MagicMock()
        good.fast_info = {"lastPrice": 150.0}

        bad = MagicMock()
        type(bad).fast_info = property(lambda self: (_ for _ in ()).throw(KeyError("boom")))

        mock_ticker_cls.side_effect = [good, bad]

        result = get_prices(["AAPL", "BROKEN"])

        self.assertEqual(result, {"AAPL": 150.0})

    @patch("prices.yf.Ticker")
    def test_returns_empty_dict_when_all_fail(self, mock_ticker_cls):
        bad = MagicMock()
        type(bad).fast_info = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("network"))
        )
        mock_ticker_cls.return_value = bad

        result = get_prices(["A", "B"])

        self.assertEqual(result, {})

    @patch("prices.yf.Ticker")
    def test_skips_missing_last_price(self, mock_ticker_cls):
        mock = MagicMock()
        mock.fast_info = {"lastPrice": None}
        mock_ticker_cls.return_value = mock

        result = get_prices(["AAPL"])

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
