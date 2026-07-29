"""Regression coverage for the homepage transaction gallery."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"


def transaction_source() -> str:
    source = INDEX.read_text(encoding="utf-8")
    return source[source.index('<div class="txn-grid"') : source.index("<!-- TEAM -->")]


def deals():
    pattern = re.compile(
        r'<a class="txn-card" data-cat="(?P<category>[^"]+)"[^>]*>'
        r'(?P<body>.*?)'
        r'<div class="txn-amount">\$(?P<amount>[\d,]+)</div>'
        r'(?P<tail>.*?)</a>',
        re.DOTALL,
    )
    return [
        {
            "category": match.group("category"),
            "amount": int(match.group("amount").replace(",", "")),
            "markup": match.group(0),
        }
        for match in pattern.finditer(transaction_source())
    ]


class HomepageTransactionTests(unittest.TestCase):
    def test_each_deal_is_one_complete_grid_card(self):
        source = transaction_source()
        parsed_deals = deals()

        self.assertEqual(len(parsed_deals), 71)
        self.assertEqual(source.count('<a class="txn-card"'), 71)
        self.assertEqual(source.count('<div class="txn-body">'), 71)
        self.assertTrue(
            all(deal["markup"].endswith("</div></div></a>") for deal in parsed_deals),
            "Every transaction must close .txn-body before closing its card anchor; "
            "otherwise browsers split the image and details into separate grid items.",
        )
        self.assertTrue(
            all(deal["markup"].count('<div class="txn-body">') == 1 for deal in parsed_deals)
        )

    def test_deals_are_ordered_largest_to_smallest_within_each_tab(self):
        parsed_deals = deals()

        for category in ("perm", "constr", "bridge"):
            amounts = [
                deal["amount"] for deal in parsed_deals if deal["category"] == category
            ]
            with self.subTest(category=category):
                self.assertTrue(amounts)
                self.assertEqual(amounts, sorted(amounts, reverse=True))


if __name__ == "__main__":
    unittest.main()
