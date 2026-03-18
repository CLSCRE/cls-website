#!/usr/bin/env python3
"""
CLS CRE — Programmatic SEO Static Site Generator

Generates ~560+ static HTML pages for commercial lending SEO:
  - 6 loan type hub pages
  - 6 property type hub pages
  - 90 city × loan type pages
  - 90 city × property type pages
  - 366 submarket / neighborhood pages (61 cities × 6 neighborhoods)
  - sitemap.xml + robots.txt
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from generate_articles import main as generate_articles_main


# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
TEMPLATE_DIR = SCRIPT_DIR / "templates"
WEBSITE_DIR = SCRIPT_DIR.parent  # website/

BASE_URL = "https://clscre.com"
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


def slugify_neighborhood(name: str) -> str:
    """Convert a neighborhood name to a URL-safe slug."""
    slug = name.lower()
    # Replace & with "and", common in neighborhood names
    slug = slug.replace("&", "and")
    # Replace apostrophes, dots, and other special chars
    slug = slug.replace("'", "").replace("'", "")
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)
    return slug


def build_neighborhood_faqs(city, neighborhood, city_data=None):
    """Build neighborhood-specific FAQs with city stats where available."""
    city_name = city["city"]
    state = city["state"]
    stats = city_data.get("stats", {}) if city_data else {}

    rate_info = ""
    if stats.get("multifamily_cap_rate"):
        rate_info = f" Current cap rates for multifamily in the {city_name} metro range from {stats['multifamily_cap_rate']}, with industrial at {stats.get('industrial_cap_rate', 'competitive levels')}."

    vacancy_info = ""
    if stats.get("multifamily_vacancy"):
        vacancy_info = f" The {city_name} metro currently has multifamily vacancy around {stats['multifamily_vacancy']} and industrial vacancy near {stats.get('industrial_vacancy', 'low levels')}."

    faqs = [
        {
            "q": f"What commercial loan options are available in {neighborhood}?",
            "a": f"CLS CRE provides a full range of commercial loan products for {neighborhood}, {city_name} properties, including permanent loans, bridge loans, construction financing, SBA 504/7(a) loans, mezzanine debt, and specialty financing. We source from 1,000+ lenders to find the most competitive terms for your specific property and business plan.{rate_info}",
        },
        {
            "q": f"What types of commercial properties are in {neighborhood}?",
            "a": f"{neighborhood} features a diverse mix of commercial real estate, including multifamily apartments, industrial and warehouse space, retail centers, office buildings, mixed-use developments, and hospitality properties. CLS CRE finances all major property types in {neighborhood} and the broader {city_name} market.{vacancy_info}",
        },
        {
            "q": f"How do I get a commercial mortgage in {neighborhood}, {city_name}?",
            "a": f"Contact CLS CRE for a free, no-obligation quote on commercial financing in {neighborhood}, {city_name}, {state}. Our team will analyze your property, business plan, and financial profile to identify the best lender match from our network of 1,000+ capital sources. Most borrowers receive term sheets within 48-72 hours of submitting a complete loan request.",
        },
        {
            "q": f"What are commercial real estate rates in {neighborhood}?",
            "a": f"Commercial real estate rates in {neighborhood} and the {city_name} metro vary by loan type, property type, leverage, and borrower profile. Permanent loan rates typically range from 5.34% to 8.25%, bridge loans from 7.5% to 12%, and construction loans from 8% to 13%. CLS CRE leverages lender competition to secure the most aggressive pricing available for your deal.",
        },
    ]
    return faqs


def minify_css(src_path: Path, dst_path: Path):
    """Simple CSS minification: strip comments, collapse whitespace."""
    css = src_path.read_text(encoding="utf-8")
    # Remove comments
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    # Collapse whitespace around symbols
    css = re.sub(r'\s+', ' ', css)
    css = re.sub(r'\s*([{}:;,>~+])\s*', r'\1', css)
    css = re.sub(r';\s*}', '}', css)
    dst_path.write_text(css.strip(), encoding="utf-8")
    orig = src_path.stat().st_size
    mini = dst_path.stat().st_size
    print(f"  [OK] {dst_path.name}  ({orig} -> {mini} bytes, -{100-mini*100//orig}%)")


def build_article_map(articles, tag_to_slug):
    """Build reverse mapping from loan/property slug -> matching articles."""
    slug_articles = {}
    for article in articles:
        tags = [t.lower() for t in article.get("tags", [])]
        slug_title = article["slug"].lower()
        matched_slugs = set()
        for tag in tags:
            if tag in tag_to_slug:
                _, type_slug = tag_to_slug[tag]
                matched_slugs.add(type_slug)
        for key, (_, type_slug) in tag_to_slug.items():
            if key.replace(" ", "-") in slug_title:
                matched_slugs.add(type_slug)
        for s in matched_slugs:
            slug_articles.setdefault(s, []).append(article)
    return slug_articles


def main():
    # ── Pre-generate programmatic blog articles ───────────────────────
    generate_articles_main()

    # ── Load data ──────────────────────────────────────────────────────
    transactions = load_json("transactions.json")
    loan_types = load_json("loan_types.json")
    property_types = load_json("property_types.json")
    cities = load_json("cities.json")
    faqs_data = load_json("faqs.json")
    article_city_data = load_json("article_city_data.json")

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
        {"loc": f"{BASE_URL}/submit-deal.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7"},
    ]

    page_count = 0

    # ── Load articles ─────────────────────────────────────────────────
    articles = load_json("articles.json")
    # Format dates and sort by date descending
    for a in articles:
        a["date_formatted"] = datetime.strptime(a["date"], "%Y-%m-%d").strftime("%B %d, %Y")
    articles.sort(key=lambda x: x["date"], reverse=True)

    # ── Ensure output dirs ─────────────────────────────────────────────
    (WEBSITE_DIR / "financing").mkdir(exist_ok=True)
    (WEBSITE_DIR / "property").mkdir(exist_ok=True)
    (WEBSITE_DIR / "blog").mkdir(exist_ok=True)
    (WEBSITE_DIR / "tools").mkdir(exist_ok=True)
    (WEBSITE_DIR / "markets").mkdir(exist_ok=True)

    # ── Build article-to-slug map for hub cross-links ─────────────────
    TAG_TO_SLUG = {
        "bridge loans": ("financing", "bridge-loans"),
        "permanent loans": ("financing", "permanent-loans"),
        "construction loans": ("financing", "construction-loans"),
        "construction": ("financing", "construction-loans"),
        "sba": ("financing", "sba-loans"),
        "sba 504": ("financing", "sba-loans"),
        "mezzanine": ("financing", "mezzanine"),
        "multifamily": ("property", "multifamily"),
        "apartment investing": ("property", "multifamily"),
        "industrial": ("property", "industrial"),
        "retail": ("property", "retail"),
        "office": ("property", "office"),
        "mixed-use": ("property", "mixed-use"),
        "hospitality": ("property", "hospitality"),
        "hotel": ("property", "hospitality"),
    }
    article_map = build_article_map(articles, TAG_TO_SLUG)

    # ── 1. Loan Type Hub Pages ─────────────────────────────────────────
    print("\n=== Generating Loan Type Hub Pages ===")
    tpl_financing = env.get_template("financing_page.html")
    for loan in loan_types:
        txns = filter_transactions(transactions, loan_slug=loan["slug"])
        loan_faqs = faqs_data.get("loan_types", {}).get(loan["slug"], [])
        rel_articles = article_map.get(loan["slug"], [])[:3]
        html = tpl_financing.render(
            **shared,
            loan=loan,
            seo=loan["seo"],
            canonical_path=f"financing/{loan['slug']}.html",
            depth="../",
            transactions=txns,
            faqs=loan_faqs,
            related_articles=rel_articles,
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
        rel_articles = article_map.get(prop["slug"], [])[:3]
        html = tpl_property.render(
            **shared,
            prop=prop,
            seo=prop["seo"],
            canonical_path=f"property/{prop['slug']}.html",
            depth="../",
            transactions=txns,
            faqs=prop_faqs,
            related_articles=rel_articles,
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
        print(f"  [OK] financing/{loan['slug']}-*.html  ({len(cities)} city pages)")

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
        print(f"  [OK] property/{prop['slug']}-*.html  ({len(cities)} city pages)")

    # ── 5. Blog Index Page ──────────────────────────────────────────────
    print("\n=== Generating Blog Pages ===")
    tpl_blog_index = env.get_template("blog_index.html")
    categories = sorted(set(a["category"] for a in articles))
    html = tpl_blog_index.render(
        **shared,
        articles=articles,
        categories=categories,
        seo={
            "title": "CRE Insights & Market Analysis | CLS CRE Blog",
            "meta_description": "Expert insights on commercial real estate financing, interest rates, market trends, and investment strategies from CLS CRE.",
        },
        canonical_path="blog/",
        depth="../",
    )
    (WEBSITE_DIR / "blog" / "index.html").write_text(html, encoding="utf-8")
    page_count += 1
    sitemap_urls.append({
        "loc": f"{BASE_URL}/blog/",
        "lastmod": TODAY, "changefreq": "weekly", "priority": "0.8",
    })
    print(f"  [OK] blog/index.html  ({len(articles)} articles)")

    # ── 6. Blog Article Pages ─────────────────────────────────────────
    # Featured cities for cross-links (mix of large and emerging markets)
    FEATURED_CITIES = [c for c in cities if c["slug"] in (
        "los-angeles", "new-york", "dallas", "phoenix", "atlanta",
        "miami", "chicago", "boston", "nashville", "tampa",
        "seattle", "denver", "austin", "charlotte", "riverside",
    )]

    def build_related_cities(article):
        """Build related city page links based on article tags."""
        tags = [t.lower() for t in article.get("tags", [])]
        slug_title = article["slug"].lower()
        links = []
        matched_type = None
        # Find the best matching loan/property type
        for tag in tags:
            if tag in TAG_TO_SLUG:
                matched_type = TAG_TO_SLUG[tag]
                break
        # Also check article slug for hints
        if not matched_type:
            for key, val in TAG_TO_SLUG.items():
                if key.replace(" ", "-") in slug_title:
                    matched_type = val
                    break
        # Default to permanent-loans for rate/general articles
        if not matched_type:
            matched_type = ("financing", "permanent-loans")
        section, type_slug = matched_type
        for city in FEATURED_CITIES:
            links.append({
                "label": f"{city['city']}, {city['state']}",
                "url": f"{section}/{type_slug}-{city['slug']}.html",
            })
        return links

    tpl_blog_article = env.get_template("blog_article.html")
    for article in articles:
        # Find related articles (same category, excluding self)
        related = [a for a in articles if a["category"] == article["category"] and a["slug"] != article["slug"]][:3]
        if len(related) < 2:
            # Fill with other recent articles
            related = [a for a in articles if a["slug"] != article["slug"]][:3]
        related_cities = build_related_cities(article)
        html = tpl_blog_article.render(
            **shared,
            article=article,
            faqs=article.get("faqs", []),
            related_articles=related,
            related_cities=related_cities,
            seo={
                "title": f"{article['title']} | CLS CRE",
                "meta_description": article["excerpt"],
            },
            canonical_path=f"blog/{article['slug']}.html",
            depth="../",
        )
        out_path = WEBSITE_DIR / "blog" / f"{article['slug']}.html"
        out_path.write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/blog/{article['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.8",
        })
    print(f"  [OK] blog/*.html  ({len(articles)} article pages)")

    # ── 7. Locations Page ──────────────────────────────────────────────
    print("\n=== Generating Locations Page ===")
    tpl_locations = env.get_template("locations.html")
    # Unique states, sorted
    states_sorted = sorted(set(c["state"] for c in cities))
    total_city_pages = len(cities) * (len(loan_types) + len(property_types))
    html = tpl_locations.render(
        **shared,
        cities=cities,
        states_sorted=states_sorted,
        total_pages=total_city_pages,
        seo={
            "title": "Commercial Real Estate Financing Locations | CLS CRE",
            "meta_description": f"CLS CRE provides commercial mortgage brokerage in {len(cities)} major U.S. metros. Browse financing programs and property types by city.",
        },
        canonical_path="locations.html",
        depth="",
    )
    (WEBSITE_DIR / "locations.html").write_text(html, encoding="utf-8")
    page_count += 1
    sitemap_urls.append({
        "loc": f"{BASE_URL}/locations.html",
        "lastmod": TODAY, "changefreq": "weekly", "priority": "0.9",
    })
    print(f"  [OK] locations.html  ({len(cities)} cities)")

    # ── 8. Submarket / Neighborhood Pages ───────────────────────────────
    print("\n=== Generating Submarket / Neighborhood Pages ===")
    tpl_submarket = env.get_template("submarket_page.html")
    tpl_market_index = env.get_template("market_city_index.html")
    submarket_count = 0
    for city in cities:
        neighborhoods = city.get("neighborhoods", [])
        if not neighborhoods:
            continue
        # Build neighborhood slug list for cross-linking
        neighborhood_list = []
        for n in neighborhoods:
            neighborhood_list.append({
                "name": n,
                "slug": slugify_neighborhood(n),
            })
        # Create city market directory
        city_market_dir = WEBSITE_DIR / "markets" / city["slug"]
        city_market_dir.mkdir(parents=True, exist_ok=True)
        # Get city data for FAQ enrichment
        city_data = article_city_data.get(city["slug"], {})
        # Get transactions for the state
        txns = filter_transactions(transactions, state=city["state"])
        if not txns:
            txns = transactions[:3]
        # Generate each neighborhood page
        for n_info in neighborhood_list:
            n_name = n_info["name"]
            n_slug = n_info["slug"]
            # Other neighborhoods for cross-links (exclude current)
            other_neighborhoods = [nb for nb in neighborhood_list if nb["slug"] != n_slug]
            faqs = build_neighborhood_faqs(city, n_name, city_data)
            seo = {
                "title": f"{n_name} Commercial Loans | CLS CRE",
                "meta_description": f"Commercial real estate financing in {n_name}, {city['city']}, {city['state']}. Bridge, permanent, construction, and SBA loans from 1,000+ lenders. Get a free quote.",
            }
            canonical = f"markets/{city['slug']}/{n_slug}.html"
            html = tpl_submarket.render(
                **shared,
                city=city,
                neighborhood=n_name,
                neighborhood_slug=n_slug,
                other_neighborhoods=other_neighborhoods,
                seo=seo,
                canonical_path=canonical,
                depth="../../",
                transactions=txns,
                faqs=faqs,
            )
            out_path = city_market_dir / f"{n_slug}.html"
            out_path.write_text(html, encoding="utf-8")
            page_count += 1
            submarket_count += 1
            sitemap_urls.append({
                "loc": f"{BASE_URL}/{canonical}",
                "lastmod": TODAY, "changefreq": "monthly", "priority": "0.6",
            })
        # Generate city market index page
        seo_index = {
            "title": f"Commercial Real Estate Financing in {city['city']}, {city['state']} | CLS CRE",
            "meta_description": f"Explore commercial lending options by neighborhood in {city['city']}, {city['state']}. Browse {len(neighborhoods)} submarkets with financing for every property type.",
        }
        html = tpl_market_index.render(
            **shared,
            city=city,
            neighborhoods=neighborhood_list,
            seo=seo_index,
            canonical_path=f"markets/{city['slug']}/",
            depth="../../",
        )
        (city_market_dir / "index.html").write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/markets/{city['slug']}/",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
        })
    print(f"  [OK] markets/*/*.html  ({submarket_count} neighborhood pages + {len(cities)} city index pages)")

    # ── 9. Calculator / Tool Pages ──────────────────────────────────────
    print("\n=== Generating Calculator Pages ===")
    tool_pages = [
        ("tool_index.html", "tools/index.html", "tools/", "Calculators & Tools | CLS CRE",
         "Free commercial real estate calculators for DSCR, cap rate, and loan payments.", "0.8"),
        ("tool_dscr.html", "tools/dscr-calculator.html", "tools/dscr-calculator.html", "DSCR Calculator | CLS CRE",
         "Free Debt Service Coverage Ratio calculator for commercial real estate.", "0.8"),
        ("tool_caprate.html", "tools/cap-rate-calculator.html", "tools/cap-rate-calculator.html", "Cap Rate Calculator | CLS CRE",
         "Free capitalization rate calculator for commercial real estate.", "0.8"),
        ("tool_loan.html", "tools/loan-calculator.html", "tools/loan-calculator.html", "Commercial Loan Payment Calculator | CLS CRE",
         "Free commercial mortgage payment calculator with I/O periods and amortization.", "0.8"),
        ("tool_ltv.html", "tools/ltv-calculator.html", "tools/ltv-calculator.html", "LTV Calculator | CLS CRE",
         "Free Loan-to-Value calculator for commercial real estate. See typical LTV limits by lender type.", "0.8"),
        ("tool_cashoncash.html", "tools/cashoncash-calculator.html", "tools/cashoncash-calculator.html", "Cash-on-Cash Return Calculator | CLS CRE",
         "Free cash-on-cash return calculator for commercial real estate investments.", "0.8"),
        ("tool_noi.html", "tools/noi-calculator.html", "tools/noi-calculator.html", "NOI Calculator | CLS CRE",
         "Free Net Operating Income calculator for commercial real estate. Calculate NOI from income and expenses.", "0.8"),
    ]
    for tpl_name, out_rel, canonical, title, desc, priority in tool_pages:
        tpl_tool = env.get_template(tpl_name)
        html = tpl_tool.render(
            **shared,
            seo={"title": title, "meta_description": desc},
            canonical_path=canonical,
            depth="../",
        )
        out_path = WEBSITE_DIR / out_rel
        out_path.write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/{canonical}",
            "lastmod": TODAY, "changefreq": "monthly", "priority": priority,
        })
        print(f"  [OK] {out_rel}")

    # ── 10. CSS Minification ─────────────────────────────────────────
    print("\n=== Minifying CSS ===")
    css_dir = WEBSITE_DIR / "css"
    for css_file in ["global.css", "pages.css"]:
        src = css_dir / css_file
        dst = css_dir / css_file.replace(".css", ".min.css")
        minify_css(src, dst)

    # ── 11. Sitemap.xml ─────────────────────────────────────────────────
    print("\n=== Generating sitemap.xml ===")
    tpl_sitemap = env.get_template("sitemap.xml.j2")
    sitemap_xml = tpl_sitemap.render(urls=sitemap_urls)
    (WEBSITE_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    print(f"  [OK] sitemap.xml  ({len(sitemap_urls)} URLs)")

    # ── 12. Robots.txt ─────────────────────────────────────────────────
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
