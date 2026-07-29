import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "_generator" / "data"


class PropertyConversionSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.properties = json.loads(
            (DATA_DIR / "property_types.json").read_text(encoding="utf-8-sig")
        )

    def test_every_property_hub_uses_the_cls_two_million_floor(self):
        self.assertEqual(len(self.properties), 12)
        legacy_floor = re.compile(r"\$1(?:,?000,?000|M(?!M)| million)", re.IGNORECASE)
        for prop in self.properties:
            with self.subTest(slug=prop["slug"]):
                self.assertEqual(prop.get("min_amount_usd"), 2_000_000)
                self.assertEqual(prop.get("min_loan_display"), "$2MM")
                self.assertNotRegex(prop["seo"]["meta_description"], legacy_floor)

    def test_all_property_hubs_render_through_the_conversion_system(self):
        from _generator.render_property_hubs import render_hubs

        rendered = render_hubs(write=False)
        self.assertEqual(set(rendered), {prop["slug"] for prop in self.properties})
        legacy_floor = re.compile(r"\$1(?:,?000,?000|M(?!M)| million)", re.IGNORECASE)
        for prop in self.properties:
            html = rendered[prop["slug"]]
            with self.subTest(slug=prop["slug"]):
                schema_blocks = re.findall(
                    r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
                )
                self.assertGreaterEqual(len(schema_blocks), 4)
                for block in schema_blocks:
                    json.loads(block)
                self.assertIn("css/financing-hub.css?v=", html)
                self.assertIn("class=\"pf-hero\"", html)
                self.assertIn("At a Glance", html)
                self.assertIn("$2MM+", html)
                self.assertIn(f"apply.html?property={prop['slug']}", html)
                self.assertGreaterEqual(
                    html.count(f"apply.html?property={prop['slug']}"),
                    4,
                    "hero, nav, sticky, and final CTAs must preserve the property",
                )
                self.assertNotIn("Quick answer:", html)
                self.assertNotRegex(html, legacy_floor)
                self.assertNotIn('"@type":"PriceSpecification"', html)
                self.assertNotIn('"minPrice"', html)
                self.assertRegex(html, re.compile(r"\$2MM\+?"))
                self.assertEqual(len(re.findall(r"<h1(?:\s|>)", html)), 1)
                self.assertLessEqual(html.count("pf-market-extra"), 6)

    def test_property_capital_paths_explain_transitional_and_construction_fit(self):
        from _generator.render_property_hubs import render_hubs

        multifamily = render_hubs(slugs=["multifamily"], write=False)["multifamily"]
        self.assertIn("short-term capital for acquisition, lease-up, renovation", multifamily)
        self.assertIn("ground-up development, major renovation, or conversion", multifamily)

    def test_apply_page_accepts_every_property_hub_query(self):
        apply_source = (ROOT / "apply.html").read_text(encoding="utf-8")
        self.assertIn("params.get('property')", apply_source)
        self.assertIn('name="Property Hub Source"', apply_source)
        self.assertIn("propertySource.value = propertyRaw", apply_source)
        for prop in self.properties:
            with self.subTest(slug=prop["slug"]):
                self.assertIn(f'"{prop["slug"]}":', apply_source)


if __name__ == "__main__":
    unittest.main()
