import json
import html as html_lib
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

WEBSITE_DIR = Path(__file__).resolve().parents[2]
GENERATOR_DIR = WEBSITE_DIR / "_generator"
DATA_DIR = GENERATOR_DIR / "data"
TEMPLATES_DIR = GENERATOR_DIR / "templates"

if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))


class FinancingConversionSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loans = json.loads((DATA_DIR / "loan_types.json").read_text(encoding="utf-8"))
        cls.cities = json.loads((DATA_DIR / "cities.json").read_text(encoding="utf-8"))
        cls.properties = json.loads((DATA_DIR / "property_types.json").read_text(encoding="utf-8"))
        cls.faqs = json.loads((DATA_DIR / "faqs.json").read_text(encoding="utf-8"))
        cls.env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)

    def render(self, loan):
        template = self.env.get_template("financing_conversion_page.html")
        return template.render(
            loan=loan,
            seo=loan["seo"],
            canonical_path=f"financing/{loan['slug']}.html",
            depth="../",
            current_year=2026,
            all_loan_types=self.loans,
            all_cities=self.cities,
            all_property_types=self.properties,
            transactions=[],
            faqs=self.faqs.get("loan_types", {}).get(loan["slug"], []),
            related_articles=[],
            market_links=[{"city":"Dallas","state":"TX","slug":"dallas","path":"markets/dallas/index.html","href_suffix":"markets/dallas/"}],
        )

    def test_every_program_has_shared_minimum_and_application_route(self):
        self.assertEqual(42, len(self.loans))
        for loan in self.loans:
            with self.subTest(slug=loan["slug"]):
                self.assertEqual(2_000_000, loan.get("min_amount_usd"))
                self.assertEqual("$2MM", loan.get("min_loan_display"))
                expected_query = f"program={loan['slug'].removesuffix('-loans')}"
                self.assertEqual(expected_query, loan.get("apply_query"))
                serialized = json.dumps(loan)
                self.assertNotRegex(serialized, r"\$1M(?!M)|\$500K|\$500,000")

    def test_shared_template_renders_every_program_without_exposed_seo_copy(self):
        for loan in self.loans:
            with self.subTest(slug=loan["slug"]):
                html = self.render(loan)
                self.assertEqual(1, len(re.findall(r"<h1\b", html, re.I)))
                self.assertNotIn("Quick answer", html)
                self.assertNotRegex(html, r"\$1M(?!M)|\$500K|\$500,000")
                self.assertIn(f"apply.html?{loan['apply_query']}", html)
                # Market chips must not point at retired city×program URLs.
                self.assertIn("markets/", html)
                self.assertNotRegex(html, rf"financing/{loan['slug']}-[a-z0-9-]+\.html")
                self.assertIn("At a Glance", html)
                self.assertIn("How We Source", html)

                blocks = re.findall(
                    r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                    html,
                    re.S,
                )
                schemas = [json.loads(block) for block in blocks]
                loan_schema = next(item for item in schemas if item.get("@type") == "LoanOrCredit")
                self.assertEqual(2_000_000, loan_schema["amount"]["minValue"])

    def test_shared_template_accessibility_contract(self):
        template_source = (TEMPLATES_DIR / "financing_conversion_page.html").read_text(encoding="utf-8")
        css_source = (WEBSITE_DIR / "css" / "financing-hub.css").read_text(encoding="utf-8")
        nav_source = (TEMPLATES_DIR / "_nav.html").read_text(encoding="utf-8")
        self.assertIn(".pf-faq-a[hidden]{display:none}", css_source)
        self.assertIn('aria-controls="pfMarketList"', template_source)
        self.assertIn('aria-controls="pf-faq-panel-{{ loop.index }}"', template_source)
        self.assertIn('role="region"', template_source)
        self.assertIn("loan.min_amount_usd|tojson", template_source)
        self.assertIn('aria-expanded="false" aria-controls="navLinks"', nav_source)

    def test_targeted_renderer_produces_all_hubs_without_writing(self):
        from render_financing_hubs import render_hubs

        rendered = render_hubs(write=False)
        self.assertEqual({loan["slug"] for loan in self.loans}, set(rendered))
        self.assertTrue(all("Quick answer" not in html for html in rendered.values()))

    def test_asset_versions_are_stable_across_line_endings(self):
        import generate

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "css").mkdir()
            (root / "js").mkdir()
            crlf = bytes((13, 10))
            (root / "css" / "sample.css").write_bytes(b"a" + crlf + b"b" + crlf)
            (root / "js" / "sample.js").write_bytes(b"a\nb\n")
            original_root = generate.WEBSITE_DIR
            try:
                generate.WEBSITE_DIR = root
                versions = generate.compute_asset_versions()
            finally:
                generate.WEBSITE_DIR = original_root

        expected = hashlib.md5(b"a\nb\n").hexdigest()[:10]
        self.assertEqual(expected, versions["css/sample.css"])
        self.assertEqual(expected, versions["js/sample.js"])

    def test_application_flow_enforces_two_million_and_maps_all_routes(self):
        html = (WEBSITE_DIR / "apply.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, r"\$1M(?!M)")
        self.assertIn('min="2000000"', html)
        self.assertIn("Our focus is $2MM+ CRE loans", html)
        for loan in self.loans:
            route = loan["apply_query"].split("=", 1)[1]
            self.assertRegex(
                html,
                rf"['\"]{re.escape(route)}['\"]\s*:\s*['\"]{re.escape(loan['name'])}['\"]",
            )
            escaped_name = html_lib.escape(loan["name"], quote=True)
            self.assertIn(f'<option value="{escaped_name}">{escaped_name}</option>', html)


if __name__ == "__main__":
    unittest.main()
