import json
import re
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


WEBSITE = Path(__file__).resolve().parents[2]
DATA = WEBSITE / "_generator" / "data"
TEMPLATES = WEBSITE / "_generator" / "templates"
GENERATE = WEBSITE / "_generator" / "generate.py"


class PermanentFlagshipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loan_types = json.loads((DATA / "loan_types.json").read_text(encoding="utf-8-sig"))
        cls.loan = next(item for item in loan_types if item["slug"] == "permanent-loans")

    def test_permanent_data_uses_two_million_floor(self):
        self.assertEqual(self.loan["min_amount_usd"], 2_000_000)
        self.assertEqual(self.loan["min_loan_display"], "$2MM")
        self.assertTrue(self.loan["key_features"]["loan_amount"].startswith("$2MM"))
        self.assertNotIn("$1M", self.loan["seo"]["meta_description"])
        self.assertEqual(self.loan["apply_query"], "program=permanent")

    def test_generator_selects_shared_conversion_template(self):
        source = GENERATE.read_text(encoding="utf-8")
        self.assertIn('"financing_conversion_page.html"', source)
        self.assertNotIn('loan["slug"] == "permanent-loans"', source)

    def test_rendered_page_is_complete_and_self_consistent(self):
        output = WEBSITE / "financing" / "permanent-loans.html"
        html = output.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<h1(?:\s|>)", html)), 1)
        self.assertIn('<link rel="canonical" href="https://clscre.com/financing/permanent-loans.html">', html)
        self.assertNotIn("Quick answer", html)
        self.assertNotRegex(html, r"\$1M(?:\b|\s|-)")
        self.assertNotIn("$1 million", html)

        apply_hrefs = re.findall(r'href="\.\./apply\.html([^\"]*)"', html)
        self.assertTrue(apply_hrefs)
        self.assertTrue(all(href == "?program=permanent" for href in apply_hrefs), apply_hrefs)

        versioned_assets = re.findall(
            r'(?:href|src)="\.\./(?:css|js)/[^\"]+\?v=([0-9a-f]{10})"', html
        )
        self.assertGreaterEqual(len(versioned_assets), 5)

        schema_blocks = re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            html,
            flags=re.DOTALL,
        )
        self.assertGreaterEqual(len(schema_blocks), 5)
        for block in schema_blocks:
            json.loads(block)

        for src in re.findall(r'<img[^>]+src="([^\"]+)"', html):
            if src.startswith(("http://", "https://", "data:")):
                continue
            clean_src = src.split("?", 1)[0]
            asset = (output.parent / clean_src).resolve()
            self.assertTrue(asset.exists(), f"Missing image: {src}")

        self.assertRegex(html, r'id="pf-faq-button-1"[^>]+aria-controls="pf-faq-panel-1"')
        self.assertRegex(html, r'id="pf-faq-panel-2"[^>]+hidden')

    def test_flagship_renders_credible_page_and_schema(self):
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template("financing_conversion_page.html")
        special_answer = 'Quoted "answer" with a backslash \\ and </script> text.'
        faqs = [
            {
                "q": "What is a permanent commercial real estate loan?",
                "a": special_answer,
            }
        ]
        html = template.render(
            loan=self.loan,
            seo=self.loan["seo"],
            canonical_path="financing/permanent-loans.html",
            depth="../",
            transactions=[],
            faqs=faqs,
            related_articles=[],
            all_loan_types=[self.loan],
            all_property_types=[],
            all_cities=[],
            regional_groups=[],
            total_market_count=0,
            current_date="2026-07-28",
            current_date_human="July 2026",
            has_glossary=False,
        )
        self.assertIn(self.loan["headline"], html)
        self.assertIn("$2MM", html)
        self.assertIn('"minValue":2000000', html)
        self.assertIn("apply.html?program=permanent", html)
        apply_hrefs = re.findall(r'href="\.\./apply\.html([^\"]*)"', html)
        self.assertTrue(apply_hrefs)
        self.assertTrue(all(href == "?program=permanent" for href in apply_hrefs), apply_hrefs)
        self.assertIn("How We Source", html)
        self.assertNotIn("Quick answer", html)
        self.assertNotIn("$1M", html)

        schema_blocks = re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            html,
            flags=re.DOTALL,
        )
        parsed = [json.loads(block) for block in schema_blocks]
        faq_schema = next(block for block in parsed if block.get("@type") == "FAQPage")
        self.assertEqual(
            faq_schema["mainEntity"][0]["acceptedAnswer"]["text"], special_answer
        )

        template_source = (TEMPLATES / "financing_conversion_page.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("font-size:0", template_source)


if __name__ == "__main__":
    unittest.main()
