#!/usr/bin/env python3
"""
CLS CRE — Programmatic Blog Article Generator

Generates 51 market-specific blog articles from templates + city data:
  - 15 City Market Reports (Type A)
  - 18 City × Loan Type Guides (Type B)
  - 18 City × Property Type Guides (Type C)

Merges with existing hand-written articles in articles.json.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
CONTENT_TEMPLATE_DIR = SCRIPT_DIR / "content_templates"

# ── Article definitions ────────────────────────────────────────────────

# Type A: 15 City Market Reports
MARKET_REPORT_CITIES = [
    "los-angeles", "new-york", "dallas", "phoenix", "houston",
    "miami", "atlanta", "chicago", "denver", "seattle",
    "austin", "nashville", "tampa", "charlotte", "boston",
]

# Type B: 18 City × Loan Type Guides (3 loan types × 6 cities each)
LOAN_GUIDE_COMBOS = [
    # Bridge Loans × 6 cities
    ("bridge-loans", "bridge", "los-angeles"),
    ("bridge-loans", "bridge", "dallas"),
    ("bridge-loans", "bridge", "phoenix"),
    ("bridge-loans", "bridge", "miami"),
    ("bridge-loans", "bridge", "atlanta"),
    ("bridge-loans", "bridge", "nashville"),
    # Permanent Loans × 6 cities
    ("permanent-loans", "permanent", "new-york"),
    ("permanent-loans", "permanent", "chicago"),
    ("permanent-loans", "permanent", "boston"),
    ("permanent-loans", "permanent", "seattle"),
    ("permanent-loans", "permanent", "houston"),
    ("permanent-loans", "permanent", "charlotte"),
    # Construction Loans × 6 cities
    ("construction-loans", "construction", "austin"),
    ("construction-loans", "construction", "denver"),
    ("construction-loans", "construction", "tampa"),
    ("construction-loans", "construction", "miami"),
    ("construction-loans", "construction", "dallas"),
    ("construction-loans", "construction", "phoenix"),
]

# Type C: 18 City × Property Type Guides (3 property types × 6 cities each)
PROPERTY_GUIDE_COMBOS = [
    # Multifamily × 6 cities
    ("multifamily", "los-angeles"),
    ("multifamily", "new-york"),
    ("multifamily", "dallas"),
    ("multifamily", "phoenix"),
    ("multifamily", "austin"),
    ("multifamily", "boston"),
    # Industrial × 6 cities
    ("industrial", "chicago"),
    ("industrial", "houston"),
    ("industrial", "atlanta"),
    ("industrial", "seattle"),
    ("industrial", "miami"),
    ("industrial", "tampa"),
    # Retail × 6 cities
    ("retail", "nashville"),
    ("retail", "charlotte"),
    ("retail", "denver"),
    ("retail", "phoenix"),
    ("retail", "dallas"),
    ("retail", "miami"),
]


def load_json(name: str):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def stagger_dates(start_date_str, count, interval_days):
    """Generate a list of ISO date strings starting from start_date, spaced interval_days apart."""
    start = date.fromisoformat(start_date_str)
    return [(start + timedelta(days=i * interval_days)).isoformat() for i in range(count)]


def build_market_report_faqs(city, data):
    """Generate FAQs for a city market report."""
    return [
        {
            "q": f"What is the commercial real estate market like in {city['city']} in 2026?",
            "a": f"The {city['city']} CRE market in 2026 features multifamily vacancy at {data['stats']['multifamily_vacancy']}, industrial vacancy at {data['stats']['industrial_vacancy']}, rent growth of {data['stats']['rent_growth']}, and job growth of {data['stats']['job_growth']}. Key economic drivers include {data['stats']['major_employers']}."
        },
        {
            "q": f"What are cap rates in {city['city']} for commercial real estate?",
            "a": f"As of 2026, {city['city']} cap rates range from {data['stats']['multifamily_cap_rate']} for multifamily to {data['stats']['industrial_cap_rate']} for industrial, {data['stats']['office_cap_rate']} for office, and {data['stats']['retail_cap_rate']} for retail properties."
        },
        {
            "q": f"What are the best submarkets for CRE investment in {city['city']}?",
            "a": f"Top investment submarkets in {city['city']} include {data['stats']['top_submarkets']}. Each submarket offers distinct opportunities based on property type, tenant demand, and growth trajectory."
        },
        {
            "q": f"How is the multifamily market performing in {city['city']}?",
            "a": f"The {city['city']} multifamily market has vacancy at {data['stats']['multifamily_vacancy']} with {data['stats']['rent_growth']} rent growth and median asking rents of {data['stats']['median_asking_rent']}. Cap rates range from {data['stats']['multifamily_cap_rate']}."
        },
        {
            "q": f"Is {city['city']} a good market for commercial real estate investment?",
            "a": f"{city['city']} offers compelling CRE investment opportunities with {data['stats']['job_growth']} job growth, {data['stats']['population_growth']} population growth, and diverse demand from {data['stats']['major_employers']}. The market features competitive financing availability and institutional-quality assets across all property types."
        },
    ]


def build_loan_guide_faqs(city, loan, data, loan_key):
    """Generate FAQs for a city × loan type guide."""
    leverage = loan["key_features"].get("ltv") or loan["key_features"].get("ltc", "varies")
    leverage_label = "LTC" if "ltc" in loan["key_features"] else "LTV"
    return [
        {
            "q": f"What are {loan['name'].lower()} rates in {city['city']} in 2026?",
            "a": f"{loan['name']} in {city['city']} are currently pricing at {loan['key_features']['rates']} with terms of {loan['key_features']['term']} and maximum {leverage_label} of {leverage}. Rates vary based on property type, leverage, and borrower experience."
        },
        {
            "q": f"How do I qualify for a {loan['short_name'].lower()} loan in {city['city']}?",
            "a": f"Qualifying for {loan['name'].lower()} in {city['city']} requires borrower experience with similar assets, net worth generally equal to the loan amount, liquid reserves of 6-12 months debt service, and a property that meets lender criteria for the {city['city']} market."
        },
        {
            "q": f"Which lenders offer {loan['name'].lower()} in {city['city']}?",
            "a": f"Capital sources for {loan['name'].lower()} in {city['city']} include {', '.join(loan['lender_sources'][:4])}. Working with a commercial mortgage broker ensures access to the broadest range of competitive options."
        },
        {
            "q": f"How long does it take to close a {loan['short_name'].lower()} loan in {city['city']}?",
            "a": f"{'Bridge loans can close in as little as 2-4 weeks' if loan_key == 'bridge' else 'Permanent loans typically close in 60-90 days' if loan_key == 'permanent' else 'Construction loans typically close in 45-90 days'} in the {city['city']} market, depending on deal complexity, lender requirements, and property condition."
        },
    ]


def build_property_guide_faqs(city, prop, data, prop_key):
    """Generate FAQs for a city × property type guide."""
    vacancy_key = f"{prop_key}_vacancy"
    cap_key = f"{prop_key}_cap_rate"
    cap_low = float(data["stats"][cap_key].split("-")[0].replace("%", "").strip())
    cap_desc = "the market's premium fundamentals" if cap_low < 5.5 else "attractive yields relative to coastal gateway markets"
    return [
        {
            "q": f"What are {prop['name'].lower()} cap rates in {city['city']}?",
            "a": f"{prop['name']} cap rates in {city['city']} range from {data['stats'][cap_key]} as of 2026, reflecting {cap_desc}."
        },
        {
            "q": f"How do I finance a {prop['name'].lower()} property in {city['city']}?",
            "a": f"{prop['name']} properties in {city['city']} can be financed through {', '.join(prop['financing_options'][:4])}. The optimal structure depends on your business plan, property condition, and target hold period."
        },
        {
            "q": f"What is the {prop['name'].lower()} vacancy rate in {city['city']}?",
            "a": f"The {city['city']} {prop['name'].lower()} vacancy rate is {data['stats'][vacancy_key]} as of 2026, with {data['stats']['rent_growth']} rent growth across the metro. The market's {data['stats']['job_growth']} job growth supports continued demand."
        },
        {
            "q": f"What are the best {prop['name'].lower()} submarkets in {city['city']}?",
            "a": f"Top {prop['name'].lower()} investment submarkets in {city['city']} include {data['stats']['top_submarkets']}. Each offers distinct opportunities based on tenant mix, supply dynamics, and growth trajectory."
        },
        {
            "q": f"Is {city['city']} a good market for {prop['name'].lower()} investment?",
            "a": f"{city['city']} offers compelling {prop['name'].lower()} investment opportunities with {data['stats'][vacancy_key]} vacancy, {data['stats'][cap_key]} cap rates, and demand driven by {data['stats']['major_employers']}."
        },
    ]


def main():
    print("\n=== Generating Programmatic Blog Articles ===")

    # ── Load data ──────────────────────────────────────────────────────
    cities_list = load_json("cities.json")
    loan_types = load_json("loan_types.json")
    property_types = load_json("property_types.json")
    city_data = load_json("article_city_data.json")

    # Build lookup dicts
    city_by_slug = {c["slug"]: c for c in cities_list}
    loan_by_slug = {l["slug"]: l for l in loan_types}
    prop_by_slug = {p["slug"]: p for p in property_types}

    # ── Load existing articles ─────────────────────────────────────────
    articles_path = DATA_DIR / "articles.json"
    with open(articles_path, "r", encoding="utf-8") as f:
        existing_articles = json.load(f)

    # Separate hand-written from previously generated
    hand_written = [a for a in existing_articles if not a.get("_generated")]
    print(f"  Found {len(hand_written)} hand-written articles (preserved)")

    # ── Setup Jinja2 for content templates ────────────────────────────
    env = Environment(
        loader=FileSystemLoader(str(CONTENT_TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    generated_articles = []

    # ── Type A: City Market Reports (15) ─────────────────────────────
    print("\n  --- Type A: City Market Reports ---")
    type_a_dates = stagger_dates("2025-10-01", 15, 4)

    for i, city_slug in enumerate(MARKET_REPORT_CITIES):
        city = city_by_slug[city_slug]
        data = city_data[city_slug]

        tpl = env.get_template("city_market_report.j2")
        content = tpl.render(city=city, data=data)

        article = {
            "slug": f"cre-market-report-{city_slug}-2026",
            "title": f"Commercial Real Estate Market Report: {city['city']} 2026",
            "category": "Market Insights",
            "author": "Trevor Damyan",
            "date": type_a_dates[i],
            "excerpt": f"A comprehensive analysis of the {city['city']} commercial real estate market in 2026, covering multifamily, industrial, office, and retail sectors with key metrics, financing trends, and investment outlook.",
            "tags": [
                "market report",
                city["city"].lower(),
                "CRE market",
                "commercial real estate",
                "investment",
            ],
            "image": f"market-report-{city_slug}.jpg",
            "content": content,
            "faqs": build_market_report_faqs(city, data),
            "_generated": True,
        }
        generated_articles.append(article)
        print(f"    [OK] {article['slug']}")

    # ── Type B: City × Loan Type Guides (18) ─────────────────────────
    print("\n  --- Type B: City × Loan Type Guides ---")
    type_b_dates = stagger_dates("2025-12-05", 18, 3)

    for i, (loan_slug, loan_key, city_slug) in enumerate(LOAN_GUIDE_COMBOS):
        city = city_by_slug[city_slug]
        loan = loan_by_slug[loan_slug]
        data = city_data[city_slug]

        tpl = env.get_template("city_loan_guide.j2")
        content = tpl.render(city=city, loan=loan, data=data, loan_key=loan_key)

        article = {
            "slug": f"{loan_slug}-{city_slug}-guide",
            "title": f"{loan['name']} in {city['city']}: What Borrowers Need to Know",
            "category": "Educational",
            "author": "Trevor Damyan",
            "date": type_b_dates[i],
            "excerpt": f"Everything you need to know about {loan['name'].lower()} in {city['city']}, including current rates, qualification requirements, capital sources, and market-specific strategies for commercial real estate borrowers.",
            "tags": [
                loan["name"].lower(),
                city["city"].lower(),
                "CRE financing",
                "commercial loans",
            ],
            "image": f"{loan_key}-loans-{city_slug}.jpg",
            "content": content,
            "faqs": build_loan_guide_faqs(city, loan, data, loan_key),
            "_generated": True,
        }
        generated_articles.append(article)
        print(f"    [OK] {article['slug']}")

    # ── Type C: City × Property Type Guides (18) ─────────────────────
    print("\n  --- Type C: City × Property Type Guides ---")
    type_c_dates = stagger_dates("2025-11-01", 18, 3)

    for i, (prop_slug, city_slug) in enumerate(PROPERTY_GUIDE_COMBOS):
        city = city_by_slug[city_slug]
        prop = prop_by_slug[prop_slug]
        data = city_data[city_slug]

        tpl = env.get_template("city_property_guide.j2")
        content = tpl.render(city=city, prop=prop, data=data, prop_key=prop_slug)

        article = {
            "slug": f"{prop_slug}-investing-{city_slug}-guide",
            "title": f"{prop['name']} Investing in {city['city']}: A Complete Guide",
            "category": "Market Insights",
            "author": "Trevor Damyan",
            "date": type_c_dates[i],
            "excerpt": f"A comprehensive guide to {prop['name'].lower()} investing in {city['city']}, covering market metrics, property subtypes, financing options, top submarkets, and the investment thesis for 2026.",
            "tags": [
                prop["name"].lower(),
                city["city"].lower(),
                "CRE investment",
                "commercial real estate",
            ],
            "image": f"{prop_slug}-{city_slug}.jpg",
            "content": content,
            "faqs": build_property_guide_faqs(city, prop, data, prop_slug),
            "_generated": True,
        }
        generated_articles.append(article)
        print(f"    [OK] {article['slug']}")

    # ── Merge and write ──────────────────────────────────────────────
    all_articles = hand_written + generated_articles
    print(f"\n  Total articles: {len(all_articles)} ({len(hand_written)} hand-written + {len(generated_articles)} generated)")

    with open(articles_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Written to {articles_path}")
    print("=== Article Generation Complete ===\n")

    return len(generated_articles)


if __name__ == "__main__":
    main()
