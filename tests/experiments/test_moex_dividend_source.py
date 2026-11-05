import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.fetch_moex_dividends import inspect
from src.research.moex_dividend_source import DividendSourceUnavailable, decode_response


class MoexDividendSourceTests(unittest.TestCase):
    def test_subscription_html_is_not_an_empty_dividend_history(self):
        html = '<html>Информация доступна только подписчикам. The information is available only to subscribers.</html>'
        with self.assertRaisesRegex(DividendSourceUnavailable, "SUBSCRIPTION_REQUIRED"):
            decode_response(html.encode("utf-8"))

    def test_access_block_records_zero_verified_without_claiming_zero_dividends(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            universe = root / "universe.json"
            universe.write_text(json.dumps([{"SECID": "SBER"}, {"SECID": "SFIN"}]))
            with patch("scripts.fetch_moex_dividends.fetch_page",
                       side_effect=DividendSourceUnavailable("SUBSCRIPTION_REQUIRED")):
                result = inspect(universe, root / "dividends")
            self.assertEqual(result["status"], "SUBSCRIPTION_REQUIRED")
            self.assertEqual(result["verified_symbols"], 0)
            self.assertFalse(result["applied_in_results"])
            self.assertFalse((root / "dividends/latest.json").exists())


if __name__ == "__main__":
    unittest.main()
