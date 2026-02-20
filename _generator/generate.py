#!/usr/bin/env python3
"""
CLS CRE — Programmatic SEO Static Site Generator

Generates ~192 static HTML pages for commercial lending SEO:
  - 6 loan type hub pages
  - 6 property type hub pages
  - 90 city × loan type pages
  - 90 city × property type pages
  - sitemap.xml + robots.txt
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import os
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
TEMPLATE_DIR = SCRIPT_DIR / "templates"
WEBSITE_DIR = SCRIPT_DIR.parent  # website/

BASE_URL = "https://commerciallendingsolutions.ai"
TODAY = date.today().isoformat()


def load_json(name: str):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_transactions(transactions, loan_slug=None, prop_slug=None, city=None, state=None):
    """Filter transactions by loan type slug, property slug, and/or city/state."""
    results = transactions
    if loan_slug:
        results = [t for t in results if t.get("loan_type_slug") == loan_slug]
    if prop_slug:
        results = [t for t in results if t.get("property_slug") == prop_slug]
    if state:
        results = [t for t in results if t.get("state") == state]
    if city:
        # Fuzzy: match if city name appears in the transaction city
        city_lower = city.lower()
        results = [t for t in results if city_lower in t.get("city", "").lower()]
    # Sort by amount descending
    results.sort(key=lambda x: x.get("amount_num", 0), reverse=True)
    return results


def build_city_faqs(templates, loan=None, prop=None, city=None):
    """Build city-specific FAQs from templates with variable substitution."""
    key = "financing" if loan else "property"
    faq_templates = templates.get(key, [])
    faqs = []
    for tpl in faq_templates:
        q = tpl["q"]
        a = tpl["a"]
        replacements = {
            "{city}": city["city"] if city else "",
            "{metro}": city["metro"] if city else "",
            "{loan_type}": loan["name"].lower() if loan else "",
            "{property_type}": prop["name"].lower() if prop else "",
            "{rate_low}": "5.34%",
            "{rate_high}": "8.25%",
            "{context_snippet}": (city.get("context", "")[:120] + "...") if city else "",
        }
        for k, v in replacements.items():
            q = q.replace(k, v)
            a = a.replace(k, v)
        faqs.append({"q": q, "a": a})
    return faqs


def main():
    # ── Load data ──────────────────────────────────────────────────────
    transactions = load_json("transactions.json")
    loan_types = load_json("loan_types.json")
    property_types = load_json("property_types.json")
    cities = load_json("cities.json")
    faqs_data = load_json("faqs.json")

    # ── Setup Jinja2 ───────────────────────────────────────────────────
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Shared context for nav/footer
    shared = {
        "all_loan_types": loan_types,
        "all_property_types": property_types,
        "all_cities": cities,
    }

    # Track all generated URLs for sitemap
    sitemap_urls = [
        {"loc": f"{BASE_URL}/", "lastmod": TODAY, "changefreq": "weekly", "priority": "1.0"},
        {"loc": f"{BASE_URL}/market-data.html", "lastmod": TODAY, "changefreq": "daily", "priority": "0.8"},
        {"loc": f"{BASE_URL}/about.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{BASE_URL}/contact.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.8"},
    ]

    page_count = 0

    # ── Ensure output dirs ─────────────────────────────────────────────
    (WEBSITE_DIR / "financing").mkdir(exist_ok=True)
    (WEBSITE_DIR / "property").mkdir(exist_ok=True)

    # ── 1. Loan Type Hub Pages ─────────────────────────────────────────
    print("\n=== Generating Loan Type Hub Pages ===")
    tpl_financing = env.get_template("financing_page.html")
    for loan in loan_types:
        txns = filter_transactions(transactions, loan_slug=loan["slug"])
        loan_faqs = faqs_data.get("loan_types", {}).get(loan["slug"], [])
        html = tpl_financing.render(
            **shared,
            loan=loan,
            seo=loan["seo"],
            canonical_path=f"financing/{loan['slug']}.html",
            depth="../",
            transactions=txns,
            faqs=loan_faqs,
        )
        out_path = WEBSITE_DIR / "financing" / f"{loan['slug']}.html"
        out_path.write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/financing/{loan['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.9",
        })
        print(f"  [OK] financing/{loan['slug']}.html  ({len(txns)} txns)")

    # ── 2. Property Type Hub Pages ─────────────────────────────────────
    print("\n=== Generating Property Type Hub Pages ===")
    tpl_property = env.get_template("property_page.html")
    for prop in property_types:
        txns = filter_transactions(transactions, prop_slug=prop["slug"])
        prop_faqs = faqs_data.get("property_types", {}).get(prop["slug"], [])
        html = tpl_property.render(
            **shared,
            prop=prop,
            seo=prop["seo"],
            canonical_path=f"property/{prop['slug']}.html",
            depth="../",
            transactions=txns,
            faqs=prop_faqs,
        )
        out_path = WEBSITE_DIR / "property" / f"{prop['slug']}.html"
        out_path.write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/property/{prop['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.9",
        })
        print(f"  [OK] property/{prop['slug']}.html  ({len(txns)} txns)")

    # ── 3. City × Loan Type Pages ──────────────────────────────────────
    print("\n=== Generating City × Loan Type Pages ===")
    tpl_city_fin = env.get_template("city_financing.html")
    for loan in loan_types:
        for city in cities:
            # Filter txns: same loan type + same state (broader match for city pages)
            txns = filter_transactions(transactions, loan_slug=loan["slug"], state=city["state"])
            if not txns:
                txns = filter_transactions(transactions, loan_slug=loan["slug"])[:3]
            city_faqs = build_city_faqs(
                faqs_data.get("city_templates", {}), loan=loan, city=city
            )
            seo = {
                "title": f"{loan['name']} in {city['city']}, {city['state']} | CLS CRE",
                "meta_description": f"{loan['name']} for commercial real estate in {city['city']}, {city['state']}. Competitive rates from 1,000+ lenders. Get a free quote from CLS CRE.",
            }
            slug = f"{loan['slug']}-{city['slug']}"
            html = tpl_city_fin.render(
                **shared,
                loan=loan,
                city=city,
                seo=seo,
                canonical_path=f"financing/{slug}.html",
                depth="../",
                transactions=txns,
                faqs=city_faqs,
            )
            out_path = WEBSITE_DIR / "financing" / f"{slug}.html"
            out_path.write_text(html, encoding="utf-8")
            page_count += 1
            sitemap_urls.append({
                "loc": f"{BASE_URL}/financing/{slug}.html",
                "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
            })
        print(f"  [OK] financing/{loan['slug']}-*.html  (15 city pages)")

    # ── 4. City × Property Type Pages ──────────────────────────────────
    print("\n=== Generating City × Property Type Pages ===")
    tpl_city_prop = env.get_template("city_property.html")
    for prop in property_types:
        for city in cities:
            txns = filter_transactions(transactions, prop_slug=prop["slug"], state=city["state"])
            if not txns:
                txns = filter_transactions(transactions, prop_slug=prop["slug"])[:3]
            city_faqs = build_city_faqs(
                faqs_data.get("city_templates", {}), prop=prop, city=city
            )
            seo = {
                "title": f"{prop['name']} Financing in {city['city']}, {city['state']} | CLS CRE",
                "meta_description": f"{prop['name']} financing in {city['city']}, {city['state']}. Banks, life companies, CMBS, bridge & construction loans. Free quote from CLS CRE.",
            }
            slug = f"{prop['slug']}-{city['slug']}"
            html = tpl_city_prop.render(
                **shared,
                prop=prop,
                city=city,
                seo=seo,
                canonical_path=f"property/{slug}.html",
                depth="../",
                transactions=txns,
                faqs=city_faqs,
            )
            out_path = WEBSITE_DIR / "property" / f"{slug}.html"
            out_path.write_text(html, encoding="utf-8")
            page_count += 1
            sitemap_urls.append({
                "loc": f"{BASE_URL}/property/{slug}.html",
                "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
            })
        print(f"  [OK] property/{prop['slug']}-*.html  (15 city pages)")

    # ── 5. Sitemap.xml ─────────────────────────────────────────────────
    print("\n=== Generating sitemap.xml ===")
    tpl_sitemap = env.get_template("sitemap.xml.j2")
    sitemap_xml = tpl_sitemap.render(urls=sitemap_urls)
    (WEBSITE_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    print(f"  [OK] sitemap.xml  ({len(sitemap_urls)} URLs)")

    # ── 6. Robots.txt ──────────────────────────────────────────────────
    print("\n=== Generating robots.txt ===")
    robots = f"""User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap.xml
"""
    (WEBSITE_DIR / "robots.txt").write_text(robots, encoding="utf-8")
    print("  [OK] robots.txt")

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  TOTAL PAGES GENERATED: {page_count}")
    print(f"  Sitemap URLs: {len(sitemap_urls)}")
    print(f"  Output: {WEBSITE_DIR}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
