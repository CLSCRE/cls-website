"""Regression coverage for specialty-hub market case-study libraries."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
HUBS = ("self-storage", "senior-living", "medical-office", "data-centers")


def market_section(slug: str) -> str:
    source = (ROOT / slug / "index.html").read_text(encoding="utf-8")
    return source[source.index("<!-- MARKETS -->"):source.index("<!-- BLOG -->")]


class SpecialtyMarketStudyTests(unittest.TestCase):
    def test_market_library_is_presented_as_case_studies(self):
        for slug in HUBS:
            with self.subTest(slug=slug):
                section = market_section(slug)
                self.assertIn('class="hub-section market-studies"', section)
                self.assertIn("Market Case Studies", section)
                self.assertIn("representative financing scenarios", section)
                self.assertNotIn("Coverage Across 30 US Markets", section)
                self.assertNotIn("Washington DC, DC", section)

    def test_all_market_scenario_links_are_preserved_without_inline_styles(self):
        for slug in HUBS:
            with self.subTest(slug=slug):
                section = market_section(slug)
                links = re.findall(r'href="(markets/[^"]+\.html)"', section)
                markets = re.findall(r'data-market="([^"]+)"', section)
                self.assertEqual(90, len(links))
                self.assertEqual(90, len(set(links)))
                self.assertEqual(30, len(markets))
                self.assertEqual(30, len(set(markets)))
                self.assertNotIn('style="', section)

    def test_component_has_featured_studies_and_a_collapsible_full_library(self):
        for slug in HUBS:
            with self.subTest(slug=slug):
                section = market_section(slug)
                self.assertEqual(6, section.count('class="market-study-card"'))
                self.assertEqual(24, section.count('class="market-index-item"'))
                self.assertIn('<details class="market-library">', section)
                self.assertIn("Browse 24 additional markets", section)

    def test_component_css_caps_the_grid_and_stacks_on_mobile(self):
        for slug in HUBS:
            with self.subTest(slug=slug):
                source = (ROOT / slug / "index.html").read_text(encoding="utf-8")
                self.assertIn(
                    ".market-study-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))",
                    source,
                )
                self.assertIn(".market-study-card{min-width:0", source)
                self.assertIn("#market-studies-title{scroll-margin-top:110px}", source)
                self.assertIn("@media (max-width:700px)", source)
                self.assertIn(".market-study-grid,.market-index-grid{grid-template-columns:1fr}", source)

    def test_mobile_header_exposes_the_menu_without_clipping_contact_actions(self):
        for slug in HUBS:
            with self.subTest(slug=slug):
                source = (ROOT / slug / "index.html").read_text(encoding="utf-8")
                self.assertIn(".nav-phone,.nav-inner>.nav-cta{display:none!important}", source)
                self.assertIn(".mobile-toggle{display:block", source)
                self.assertIn(".nav-links.nav-open{display:flex}", source)

    def test_specialty_hubs_do_not_render_markdown_code_fences(self):
        for slug in HUBS:
            with self.subTest(slug=slug):
                source = (ROOT / slug / "index.html").read_text(encoding="utf-8")
                self.assertNotIn("```", source)


if __name__ == "__main__":
    unittest.main()
