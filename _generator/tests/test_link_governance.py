#!/usr/bin/env python3
"""Tests for internal link governance."""
from __future__ import annotations

import re
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

WEBSITE_DIR = Path(__file__).resolve().parents[2]
GENERATOR_DIR = WEBSITE_DIR / "_generator"
SCRIPTS_DIR = WEBSITE_DIR / "scripts"
sys.path.insert(0, str(GENERATOR_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from link_governance import LinkGovernor  # noqa: E402
import rewrite_active_retired_links as rewrite_module  # noqa: E402
from rewrite_active_retired_links import (  # noqa: E402
    cleanup_misleading_location_anchors,
    retarget_semantic_market_card_anchors,
)


class LinkGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gov = LinkGovernor(WEBSITE_DIR)

    def test_active_core_pages_not_forbidden(self):
        for path in ("index.html", "locations.html", "apply.html", "thank-you.html"):
            with self.subTest(path=path):
                self.assertFalse(self.gov.is_forbidden_dest(path))

    def test_non_content_paths_never_forbidden(self):
        self.assertFalse(self.gov.is_forbidden_dest("bookwithme/user/x@clscre.com"))
        self.assertFalse(self.gov.is_forbidden_dest("css/styles.css"))

    def test_retired_financing_city_resolves_to_market_or_hub(self):
        resolved = self.gov.resolve("financing/permanent-loans-dallas.html")
        self.assertIsNotNone(resolved)
        self.assertTrue(
            resolved.startswith("markets/dallas/")
            or resolved == "financing/permanent-loans.html"
        )
        self.assertFalse(self.gov.is_forbidden_dest(resolved))

    def test_redirect_map_target_preferred(self):
        # submit-deal is in protect-equity map
        resolved = self.gov.resolve("submit-deal.html")
        self.assertEqual(resolved, "apply.html")

    def test_market_links_for_program_are_active_only(self):
        links = self.gov.market_links_for_program("permanent-loans", limit=15)
        self.assertEqual(15, len(links))
        for link in links:
            self.assertFalse(self.gov.is_forbidden_dest(link["path"]))
            self.assertIn("href_suffix", link)

    def test_program_links_for_city_exclude_forbidden(self):
        links = self.gov.program_links_for_city("miami")
        self.assertGreater(len(links), 5)
        for link in links:
            self.assertFalse(self.gov.is_forbidden_dest(link["path"]))

    def test_city_directory_links_are_unique_topical_and_never_self_links(self):
        for city_slug in self.gov.city_by_slug:
            market_path = f"markets/{city_slug}/index.html"
            link_groups = (
                self.gov.program_links_for_city(city_slug),
                self.gov.property_links_for_city(city_slug),
                self.gov.specialty_links_for_city(city_slug),
            )
            for links in link_groups:
                paths = [link["path"] for link in links]
                with self.subTest(city=city_slug, group_size=len(links)):
                    self.assertEqual(len(paths), len(set(paths)))
                    self.assertNotIn("locations.html", paths)
                for link in links:
                    with self.subTest(city=city_slug, link=link["name"]):
                        self.assertNotEqual(market_path, link["path"])
                        self.assertFalse(link["path"].startswith("markets/"))
                        self.assertFalse(self.gov.is_forbidden_dest(link["path"]))
            self.assertNotEqual(
                f"markets/{city_slug}/",
                self.gov.commercial_mortgage_href_for_city(city_slug),
            )

    def test_neighborhood_links_only_include_active_topical_pages(self):
        retired_omitted = 0
        for city_slug, city in self.gov.city_by_slug.items():
            neighborhoods = []
            for name in city.get("neighborhoods", []):
                slug = name.lower().replace("&", "and").replace("'", "")
                slug = re.sub(r"[^a-z0-9\s-]", "", slug)
                slug = re.sub(r"[\s]+", "-", slug.strip())
                slug = re.sub(r"-+", "-", slug)
                neighborhoods.append({"name": name, "slug": slug})
            links = self.gov.neighborhood_links_for_city(city_slug, neighborhoods)
            paths = [link["path"] for link in links]
            self.assertEqual(len(paths), len(set(paths)))
            self.assertNotIn("locations.html", paths)
            for path in paths:
                self.assertTrue(self.gov.is_active(path))
                self.assertFalse(self.gov.is_forbidden_dest(path))
                self.assertTrue(path.startswith(f"markets/{city_slug}/"))
            retired_omitted += len(neighborhoods) - len(links)
        self.assertGreater(retired_omitted, 0)

    def test_unrecognized_retired_neighborhood_has_no_generic_fallback(self):
        path = "markets/dallas/uptown.html"
        self.assertTrue(self.gov.is_forbidden_dest(path))
        self.assertIsNone(self.gov.resolve(path))

    def test_semantic_cards_retarget_from_market_to_national_hubs(self):
        html = """
        <div class="cross-link-grid">
          <a href="../markets/dallas/" class="cross-link-card reveal">
            <div class="cl-title">Permanent Loans</div><div>Dallas, TX</div>
          </a>
          <a href="../markets/dallas/" class="cross-link-card reveal">
            <div class="cl-title">Industrial</div><div>Dallas, TX</div>
          </a>
          <a href="../financing/bridge-loans-bakersfield.html" class="cross-link-card reveal">
            <div class="cl-title">Bridge-to-Perm Loans</div><div>Bakersfield, CA</div>
          </a>
        </div>
        """
        cleaned, stats = retarget_semantic_market_card_anchors(
            html, "property/multifamily-dallas.html", self.gov
        )
        self.assertIn('href="../financing/permanent-loans.html"', cleaned)
        self.assertIn('href="industrial.html"', cleaned)
        self.assertIn('href="../financing/bridge-to-perm-loans.html"', cleaned)
        self.assertEqual(3, stats["semantic_cards_retargeted"])

    def test_misleading_locations_anchors_are_removed_or_unwrapped(self):
        html = """
        <nav><a href="../locations.html">Locations</a></nav>
        <a href="../locations.html" class="pill-link reveal">View All 171 Markets →</a>
        <section><div class="cross-link-grid">
        <a href="../locations.html" class="cross-link-card reveal"><span>Uptown</span></a>
        </div></section>
        <p>See <a href="../locations.html">permanent loans in Dallas</a> today.</p>
        <a href="../markets/dallas/uptown.html" class="pill-link">Uptown</a>
        """
        cleaned, stats = cleanup_misleading_location_anchors(
            html, "financing/example.html", self.gov
        )
        self.assertIn(">Locations</a>", cleaned)
        self.assertIn("View All 171 Markets", cleaned)
        self.assertNotIn("cross-link-card", cleaned)
        self.assertNotIn("cross-link-grid", cleaned)
        self.assertIn("permanent loans in Dallas", cleaned)
        self.assertNotIn('href="../locations.html">permanent', cleaned)
        self.assertNotIn('class="pill-link">Uptown', cleaned)
        self.assertEqual(2, stats["misleading_cards_removed"])
        self.assertEqual(1, stats["misleading_inline_unwrapped"])

    def test_parent_market_fallback_pills_and_exact_duplicates_are_removed(self):
        html = """
        <section><div class="pill-links">
          <a href="./" class="pill-link">Downtown Jackson</a>
          <a href="./" class="pill-link">Pearl</a>
        </div></section>
        <section><div class="cross-link-grid">
          <a href="../" class="cross-link-card reveal">Jackson Hub</a>
          <a href="../" class="cross-link-card reveal">Jackson Hub</a>
        </div></section>
        """
        cleaned, stats = cleanup_misleading_location_anchors(
            html, "markets/jackson/madison.html", self.gov
        )
        self.assertNotIn("Downtown Jackson", cleaned)
        self.assertNotIn("Pearl", cleaned)
        self.assertEqual(1, cleaned.count(">Jackson Hub</a>"))
        self.assertEqual(2, stats["parent_market_pills_removed"])
        self.assertEqual(1, stats["duplicate_adjacent_anchors_removed"])

    def test_rewrite_active_corpus_scans_all_active_families_by_default(self):
        fake_files = ["states/california.html", "tools/index.html", "about.html"]
        fake_result = {"stats": {}, "sample": [], "changed": False}
        with patch.object(rewrite_module, "load_active_files", return_value=fake_files), patch.object(
            rewrite_module, "rewrite_file", return_value=fake_result
        ) as rewrite:
            result = rewrite_module.rewrite_active_corpus(
                self.gov,
                dry_run=True,
                write_report=False,
                progress=False,
            )
        self.assertEqual(3, result["files_scanned"])
        self.assertEqual(3, rewrite.call_count)

    def test_full_generator_runs_governance_after_final_sitemap(self):
        source = (GENERATOR_DIR / "generate.py").read_text(encoding="utf-8")
        sitemap_pos = source.index('(WEBSITE_DIR / "sitemap.xml").write_text')
        governor_pos = source.index("_post_gov = LinkGovernor", sitemap_pos)
        rewrite_pos = source.index("rewrite_active_corpus(", governor_pos)
        stamp_pos = source.index("    stamp_asset_versions()", rewrite_pos)
        self.assertLess(sitemap_pos, governor_pos)
        self.assertLess(governor_pos, rewrite_pos)
        self.assertLess(rewrite_pos, stamp_pos)

    def test_forbidden_unresolved_link_metadata_is_removed(self):
        html = '<link rel="next" href="https://clscre.com/blog/page/2.html">'
        self.assertTrue(self.gov.is_forbidden_dest("blog/page/2.html"))
        cleaned, stats = cleanup_misleading_location_anchors(
            html, "blog/index.html", self.gov
        )
        self.assertNotIn("page/2.html", cleaned)
        self.assertEqual(1, stats["unresolved_link_tags_removed"])

    def test_self_link_returns_none(self):
        # Resolving a page to itself should yield None when source matches
        src = "markets/dallas/index.html"
        if self.gov.is_active(src):
            self.assertIsNone(self.gov.resolve(src, source_path=src))


if __name__ == "__main__":
    unittest.main()
