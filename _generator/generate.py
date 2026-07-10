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
TODAY_HUMAN = date.today().strftime("%B %Y")  # e.g., "May 2026" — for visible bylines


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


# ── Per-loan-type FAQ rate ranges ────────────────────────────────────────
# Fix (2026-07-08): city and neighborhood FAQs previously hardcoded the
# permanent range (5.34% to 8.25%) for every loan type. Ranges now come
# from loan_types.json key_features.rates, the single source of truth.
_RATE_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?%)\s*(?:-|to)\s*(\d+(?:\.\d+)?%)")

# Display strings that are not simple ranges. If rate_low / rate_high
# fields are ever added to loan_types.json entries, those win instead.
_RATE_OVERRIDES = {
    "net-lease-financing": ("5.00%", "6.75%"),
    "bridge-to-perm-loans": ("6.50%", "10.00%"),
}

_LOAN_RATES_CACHE = None


def _loan_rates_by_slug():
    """slug -> (rate_low, rate_high) from loan_types.json."""
    global _LOAN_RATES_CACHE
    if _LOAN_RATES_CACHE is None:
        table = {}
        for lt in load_json("loan_types.json"):
            slug = lt.get("slug", "")
            if lt.get("rate_low") and lt.get("rate_high"):
                table[slug] = (lt["rate_low"], lt["rate_high"])
                continue
            if slug in _RATE_OVERRIDES:
                table[slug] = _RATE_OVERRIDES[slug]
                continue
            rates_str = (lt.get("key_features") or {}).get("rates", "")
            m = _RATE_RANGE_RE.search(rates_str)
            if m:
                table[slug] = (m.group(1), m.group(2))
        _LOAN_RATES_CACHE = table
    return _LOAN_RATES_CACHE


def _loan_rate_range(loan):
    """(rate_low, rate_high) for a loan dict; all-programs span fallback."""
    default = ("5.34%", "13.04%")
    if not loan:
        return default
    return _loan_rates_by_slug().get(loan.get("slug", ""), default)


def _slug_rate_text(slug):
    low, high = _loan_rates_by_slug().get(slug, ("5.34%", "13.04%"))
    return f"{low} to {high}"


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
            "{rate_low}": _loan_rate_range(loan)[0],
            "{rate_high}": _loan_rate_range(loan)[1],
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
            "a": f"Commercial Lending Solutions provides a full range of commercial loan products for {neighborhood}, {city_name} properties, including permanent loans, bridge loans, construction financing, SBA 504/7(a) loans, mezzanine debt, and specialty financing. We source from 1,000+ lenders to find the most competitive terms for your specific property and business plan.{rate_info}",
        },
        {
            "q": f"What types of commercial properties are in {neighborhood}?",
            "a": f"{neighborhood} features a diverse mix of commercial real estate, including multifamily apartments, industrial and warehouse space, retail centers, office buildings, mixed-use developments, and hospitality properties. Commercial Lending Solutions finances all major property types in {neighborhood} and the broader {city_name} market.{vacancy_info}",
        },
        {
            "q": f"How do I get a commercial mortgage in {neighborhood}, {city_name}?",
            "a": f"Contact Commercial Lending Solutions for a free, no-obligation quote on commercial financing in {neighborhood}, {city_name}, {state}. Our team will analyze your property, business plan, and financial profile to identify the best lender match from our network of 1,000+ capital sources. Most borrowers receive term sheets within 48-72 hours of submitting a complete loan request.",
        },
        {
            "q": f"What are commercial real estate rates in {neighborhood}?",
            "a": f"Commercial real estate rates in {neighborhood} and the {city_name} metro vary by loan type, property type, leverage, and borrower profile. Permanent loan rates typically range from {_slug_rate_text('permanent-loans')}, bridge loans from {_slug_rate_text('bridge-loans')}, and construction loans from {_slug_rate_text('construction-loans')}. Commercial Lending Solutions leverages lender competition to secure the most aggressive pricing available for your deal.",
        },
    ]
    return faqs


# ── Regional grouping (used for cross-market cross-linking) ─────────────
STATE_TO_REGION = {
    # West Coast
    "CA": "West Coast", "OR": "West Coast", "WA": "West Coast", "HI": "West Coast",
    # Mountain West
    "CO": "Mountain West", "UT": "Mountain West", "NV": "Mountain West",
    "ID": "Mountain West", "AZ": "Mountain West", "NM": "Mountain West",
    "MT": "Mountain West", "WY": "Mountain West",
    # Texas & Southwest
    "TX": "Texas & Southwest", "OK": "Texas & Southwest",
    # Midwest & Plains
    "IL": "Midwest", "MI": "Midwest", "OH": "Midwest", "IN": "Midwest",
    "WI": "Midwest", "MN": "Midwest", "IA": "Midwest", "MO": "Midwest",
    "KS": "Midwest", "NE": "Midwest", "SD": "Midwest", "ND": "Midwest",
    # Southeast
    "FL": "Southeast", "GA": "Southeast", "NC": "Southeast", "SC": "Southeast",
    "TN": "Southeast", "AL": "Southeast", "MS": "Southeast", "LA": "Southeast",
    "AR": "Southeast", "KY": "Southeast",
    # Mid-Atlantic
    "VA": "Mid-Atlantic", "DC": "Mid-Atlantic", "MD": "Mid-Atlantic",
    "PA": "Mid-Atlantic", "WV": "Mid-Atlantic", "DE": "Mid-Atlantic", "NJ": "Mid-Atlantic",
    # Northeast
    "NY": "Northeast", "MA": "Northeast", "CT": "Northeast", "RI": "Northeast",
    "VT": "Northeast", "NH": "Northeast", "ME": "Northeast",
}

REGION_ORDER = [
    "West Coast", "Mountain West", "Texas & Southwest", "Midwest",
    "Southeast", "Mid-Atlantic", "Northeast",
]

REGION_DESCRIPTIONS = {
    "West Coast": "Pacific gateway markets driving tech, logistics, and entertainment capital flows.",
    "Mountain West": "Sun Belt growth corridors with sustained in-migration and yield premiums.",
    "Texas & Southwest": "America's fastest-growing metros, anchored by energy, tech, and population gains.",
    "Midwest": "Industrial Belt and Plains markets with deep manufacturing and logistics demand.",
    "Southeast": "High-growth Southeast and Sun Belt markets with strong fundamentals across asset classes.",
    "Mid-Atlantic": "Federal, financial, and industrial corridors connecting DC, Philadelphia, and the Northeast.",
    "Northeast": "Established gateway markets with institutional capital depth and long-cycle stability.",
}

NATIONAL_ANCHORS = [
    "los-angeles", "new-york", "dallas", "miami", "atlanta",
    "chicago", "houston", "phoenix", "washington-dc",
]


def region_for_state(state: str) -> str:
    return STATE_TO_REGION.get(state, "Other Markets")


def first_sentence(text: str, max_chars: int = 160) -> str:
    """Return the first sentence of text, capped at max_chars."""
    if not text:
        return ""
    # Find sentence boundary
    for end in (". ", "! ", "? "):
        idx = text.find(end)
        if 0 < idx <= max_chars:
            return text[:idx + 1].strip()
    return text[:max_chars].rstrip() + ("..." if len(text) > max_chars else "")


def build_regional_groups(cities):
    """Group cities by region, ordered per REGION_ORDER. Returns list of
    {region, blurb, cities: [city...]} dicts, only for regions with cities."""
    by_region = {r: [] for r in REGION_ORDER}
    for c in cities:
        r = region_for_state(c["state"])
        by_region.setdefault(r, []).append(c)
    # Sort cities alphabetically within each region for clean presentation
    out = []
    for r in REGION_ORDER:
        items = by_region.get(r, [])
        if not items:
            continue
        items_sorted = sorted(items, key=lambda x: x["city"])
        out.append({
            "region": r,
            "blurb": REGION_DESCRIPTIONS.get(r, ""),
            "cities": items_sorted,
        })
    return out


def pick_featured_markets(current_city, cities, n_total=8):
    """Pick a curated set of ~8 markets to feature: regional peers + national anchors.
    Returns list of city dicts (excludes current_city)."""
    current_slug = current_city["slug"]
    current_region = region_for_state(current_city["state"])
    picks = []
    seen = {current_slug}

    # Pool 1: top metros in same region (up to 4)
    region_peers = [c for c in cities
                    if region_for_state(c["state"]) == current_region
                    and c["slug"] not in seen]
    # Prioritize peers that are also national anchors, then by metro name
    region_peers.sort(key=lambda c: (
        0 if c["slug"] in NATIONAL_ANCHORS else 1,
        c["city"],
    ))
    for c in region_peers[:4]:
        picks.append(c)
        seen.add(c["slug"])

    # Pool 2: national anchors not already picked (fill to n_total)
    anchor_lookup = {c["slug"]: c for c in cities}
    for slug in NATIONAL_ANCHORS:
        if len(picks) >= n_total:
            break
        if slug in seen:
            continue
        if slug in anchor_lookup:
            picks.append(anchor_lookup[slug])
            seen.add(slug)

    # Pool 3: if still short (e.g., small region + many anchors taken), pad
    # from the largest national metros not yet picked.
    if len(picks) < n_total:
        for c in cities:
            if len(picks) >= n_total:
                break
            if c["slug"] not in seen:
                picks.append(c)
                seen.add(c["slug"])

    return picks


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

    # Duplicate city merge (2026-07-03): these 5 slugs are the same real-world
    # city as another entry already in cities.json (added twice across
    # different metro-naming batches), so their hub/financing/property/
    # neighborhood pages were pure duplicate content competing against the
    # surviving slug for the same queries -- root cause of a chunk of the
    # GSC "crawled, not indexed" cannibalization backlog. Excluded here from
    # page generation, the sitemap, and cross-link picks (pick_featured_markets
    # draws from this filtered `cities` list). The cities.json entries
    # themselves are left in place because generate_articles.py loads its own
    # copy independently and existing blog articles / affordable-housing
    # vertical pages reference these slugs directly and are NOT duplicated.
    # Old URLs 301-redirect at Cloudflare to the winning slug's equivalent page.
    DUPLICATE_CITY_SLUGS = {
        "greenville": "greenville-sc",
        "rockford": "rockford-il",
        "oxnard": "oxnard-ventura",
        "bridgeport": "bridgeport-stamford",
        "albany-ny": "albany",
    }
    cities = [c for c in cities if c["slug"] not in DUPLICATE_CITY_SLUGS]

    # ── Setup Jinja2 ───────────────────────────────────────────────────
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Shared context for nav/footer
    regional_groups = build_regional_groups(cities)
    shared = {
        "all_loan_types": loan_types,
        "all_property_types": property_types,
        "all_cities": cities,
        "regional_groups": regional_groups,
        "total_market_count": len(cities),
        "current_date": TODAY,            # ISO date for schema (dateModified, lastReviewed)
        "current_date_human": TODAY_HUMAN, # e.g., "May 2026" — for visible bylines
    }

    # Track all generated URLs for sitemap
    sitemap_urls = [
        {"loc": f"{BASE_URL}/", "lastmod": TODAY, "changefreq": "weekly", "priority": "1.0"},
        {"loc": f"{BASE_URL}/market-data.html", "lastmod": TODAY, "changefreq": "daily", "priority": "0.8"},
        {"loc": f"{BASE_URL}/about.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{BASE_URL}/about/trevor-damyan.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7"},
        # Rate pages — high-value standalone pages updated monthly.
        # Auto-discovered via glob so newly-added rate pages from
        # scripts/generate_rate_pages.py and scripts/add_rate_pages.py
        # are picked up without hand-editing this list.
        *[
            {"loc": f"{BASE_URL}/financing/{_rate_path.name}", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.9"}
            for _rate_path in sorted((WEBSITE_DIR / "financing").glob("*-rates.html"))
        ],
        # How-to-qualify guides — mid-funnel qualification pages.
        # Auto-discovered via glob (scripts/generate_how_to_qualify_pages.py).
        *[
            {"loc": f"{BASE_URL}/financing/{_q_path.name}", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.8"}
            for _q_path in sorted((WEBSITE_DIR / "financing").glob("how-to-qualify-for-*.html"))
        ],
        # Organic metro hub pages (e.g. commercial-mortgage-broker-los-angeles.html)
        # — hand-built, not part of the loan_types x cities cross-product, so
        # they need their own glob or a full regen silently drops them from the
        # sitemap (this exact page was found orphaned 2026-07-09 after a
        # recover-from-stash commit added the file back without a sitemap entry).
        *[
            {"loc": f"{BASE_URL}/financing/{_broker_path.name}", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.9"}
            for _broker_path in sorted((WEBSITE_DIR / "financing").glob("commercial-mortgage-broker-*.html"))
        ],
        {"loc": f"{BASE_URL}/contact.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{BASE_URL}/submit-deal.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7"},
        {"loc": f"{BASE_URL}/tools/edi-eligibility-check.html", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.9"},
        # Root utility + standalone section pages that live outside the
        # programmatic cross-products (found missing in the 2026-07-09
        # sitemap-integrity audit) — guarded so a deleted page drops out.
        *[
            {"loc": f"{BASE_URL}/{_pg}", "lastmod": TODAY, "changefreq": _freq, "priority": _pr}
            for _pg, _freq, _pr in [
                ("apply.html", "monthly", "0.8"),
                ("track-record.html", "monthly", "0.8"),
                ("rates.html", "weekly", "0.8"),
                ("refinance.html", "monthly", "0.8"),
                ("partners.html", "monthly", "0.7"),
                ("broker-portal.html", "monthly", "0.6"),
                # contact/index.html intentionally absent: it rel-canonicals
                # to /contact.html (already listed above), so sitemapping it
                # only produces "duplicate, not selected as canonical" noise in GSC.
                ("expert-witness/index.html", "weekly", "0.9"),
                ("developers/index.html", "monthly", "0.8"),
                ("build-to-rent/index.html", "monthly", "0.8"),
                ("senior-housing/index.html", "monthly", "0.8"),
                ("privacy.html", "yearly", "0.3"),
                ("terms.html", "yearly", "0.3"),
                ("accessibility.html", "yearly", "0.3"),
            ]
            if (WEBSITE_DIR / _pg).exists()
        ],
    ]

    # Geo landing pages (Tier 1) + LA submarket pages (Tier 2) — generated
    # via scripts/generate_geo_landing_pages.py; listed here so full regens
    # preserve them in the sitemap.
    geo_data_path = DATA_DIR / "geo_landing.json"
    if geo_data_path.exists():
        _geo = json.loads(geo_data_path.read_text(encoding="utf-8"))
        for _m in _geo.get("tier1_metros", []):
            for _l in _geo.get("tier1_loan_types", []):
                _geo_slug = f"{_m['slug']}-{_l['slug']}"
                if (WEBSITE_DIR / "landing" / f"{_geo_slug}.html").exists():
                    sitemap_urls.append({
                        "loc": f"{BASE_URL}/landing/{_geo_slug}.html",
                        "lastmod": TODAY,
                        "changefreq": "weekly",
                        "priority": "0.9",
                    })
        for _s in _geo.get("tier2_la_submarkets", []):
            if (WEBSITE_DIR / "markets" / "la" / f"{_s['slug']}.html").exists():
                sitemap_urls.append({
                    "loc": f"{BASE_URL}/markets/la/{_s['slug']}.html",
                    "lastmod": TODAY,
                    "changefreq": "monthly",
                    "priority": "0.8",
                })

    # Vertical hubs + city x program programmatic pages (generated via
    # scripts/generate_city_{vertical}_pages.py; listed here so full regens
    # preserve them in the sitemap).
    _vertical_hubs = [
        ("affordable-housing", "affordable_programs.json", "0.9"),
        ("industrial", "industrial_programs.json", "0.9"),
        ("multifamily", "multifamily_programs.json", "0.9"),
        ("commercial", "commercial_programs.json", "0.9"),
    ]
    for _vslug, _vfile, _vpriority in _vertical_hubs:
        # Hub page
        sitemap_urls.append({
            "loc": f"{BASE_URL}/{_vslug}/index.html",
            "lastmod": TODAY,
            "changefreq": "weekly",
            "priority": _vpriority,
        })
        # City x program pages
        _vdata_path = DATA_DIR / _vfile
        if _vdata_path.exists():
            _vdata = json.loads(_vdata_path.read_text(encoding="utf-8"))
            for _c in _vdata.get("cities", []):
                for _p in _vdata.get("programs", []):
                    _slug = f"{_c['slug']}-{_p['slug']}"
                    if (WEBSITE_DIR / _vslug / "markets" / f"{_slug}.html").exists():
                        sitemap_urls.append({
                            "loc": f"{BASE_URL}/{_vslug}/markets/{_slug}.html",
                            "lastmod": TODAY,
                            "changefreq": "monthly",
                            "priority": "0.8",
                        })

    # Standalone vertical sections (life-company, data-centers, medical-office,
    # self-storage, senior-living) — generated by their own scripts with the
    # index.html + markets/*.html shape. Glob-based (never a data cross-product)
    # so only pages that actually exist get listed. Added 2026-07-09 after the
    # sitemap-integrity audit found all five verticals absent from every sitemap.
    _standalone_verticals = ["life-company", "data-centers", "medical-office",
                             "self-storage", "senior-living"]
    for _vslug in _standalone_verticals:
        _vdir = WEBSITE_DIR / _vslug
        if not _vdir.exists():
            continue
        if (_vdir / "index.html").exists():
            sitemap_urls.append({
                "loc": f"{BASE_URL}/{_vslug}/index.html",
                "lastmod": TODAY,
                "changefreq": "weekly",
                "priority": "0.9",
            })
        _vmarkets = _vdir / "markets"
        if _vmarkets.exists():
            for _vhtml in sorted(_vmarkets.glob("*.html")):
                sitemap_urls.append({
                    "loc": f"{BASE_URL}/{_vslug}/markets/{_vhtml.name}",
                    "lastmod": TODAY,
                    "changefreq": "monthly",
                    "priority": "0.8",
                })

    # Professional-referral hubs, insights/newsletter archive, and resource
    # guides — hand-built sections outside the programmatic cross-products.
    # Glob-based so only real files get listed (2026-07-09 integrity audit).
    _prof_dir = WEBSITE_DIR / "professionals"
    if _prof_dir.exists():
        for _ph in sorted(_prof_dir.rglob("index.html")):
            _rel = _ph.relative_to(WEBSITE_DIR).as_posix()
            sitemap_urls.append({
                "loc": f"{BASE_URL}/{_rel}",
                "lastmod": TODAY,
                "changefreq": "monthly",
                "priority": "0.9",
            })
    _ins_dir = WEBSITE_DIR / "insights"
    if _ins_dir.exists():
        for _ih in sorted(_ins_dir.rglob("index.html")):
            _rel = _ih.relative_to(WEBSITE_DIR).as_posix()
            _is_hub = _rel in ("insights/index.html", "insights/capital-markets-report/index.html")
            sitemap_urls.append({
                "loc": f"{BASE_URL}/{_rel}",
                "lastmod": TODAY,
                "changefreq": "weekly" if _is_hub else "monthly",
                "priority": "0.8" if _is_hub else "0.6",
            })
    _res_dir = WEBSITE_DIR / "resources"
    if _res_dir.exists():
        for _rh in sorted(_res_dir.glob("*.html")):  # top level only; email-templates/ stays out
            sitemap_urls.append({
                "loc": f"{BASE_URL}/resources/{_rh.name}",
                "lastmod": TODAY,
                "changefreq": "monthly",
                "priority": "0.7",
            })

    # Deal-size pages (generated by scripts/generate_deal_size_pages.py)
    # and deal-size city+property variants (generated by
    # scripts/generate_deal_size_city_pages.py). Listed here so full
    # regens preserve them in the sitemap.
    for _ds_html in sorted((WEBSITE_DIR / "financing").glob("*-million-*.html")):
        sitemap_urls.append({
            "loc": f"{BASE_URL}/financing/{_ds_html.name}",
            "lastmod": TODAY,
            "changefreq": "monthly",
            "priority": "0.7",
        })

    # Comparison pages (generated by scripts/generate_comparison_pages.py).
    # Listed here so full regens preserve them in the sitemap.
    _cmp_dir = WEBSITE_DIR / "comparisons"
    if _cmp_dir.exists():
        for _cmp_html in sorted(_cmp_dir.glob("*.html")):
            sitemap_urls.append({
                "loc": f"{BASE_URL}/comparisons/{_cmp_html.name}",
                "lastmod": TODAY,
                "changefreq": "monthly",
                "priority": "0.85" if _cmp_html.name == "index.html" else "0.8",
            })

    # Specialty / niche property pages (generated by
    # scripts/generate_specialty_property_pages.py). Listed here so full
    # regens preserve them in the sitemap.
    _specialty_data = DATA_DIR / "specialty_properties.json"
    if _specialty_data.exists():
        for _sp in json.loads(_specialty_data.read_text(encoding="utf-8")):
            sitemap_urls.append({
                "loc": f"{BASE_URL}/property/{_sp['slug']}.html",
                "lastmod": TODAY,
                "changefreq": "monthly",
                "priority": "0.85",
            })

    # Loan size landing pages (generated by
    # scripts/generate_loan_size_pages.py). Listed here so full regens
    # preserve them in the sitemap.
    _loan_size_dir = WEBSITE_DIR / "loan-size"
    if _loan_size_dir.exists():
        for _ls_html in sorted(_loan_size_dir.glob("*.html")):
            sitemap_urls.append({
                "loc": f"{BASE_URL}/loan-size/{_ls_html.name}",
                "lastmod": TODAY,
                "changefreq": "monthly",
                "priority": "0.85" if _ls_html.name == "index.html" else "0.8",
            })

    # Research / original data publishing pages (generated by
    # scripts/generate_research_pages.py). Listed here so full regens
    # preserve them in the sitemap. High priority for citation magnets.
    _research_dir = WEBSITE_DIR / "research"
    if _research_dir.exists():
        for _rp_html in sorted(_research_dir.glob("*.html")):
            sitemap_urls.append({
                "loc": f"{BASE_URL}/research/{_rp_html.name}",
                "lastmod": TODAY,
                "changefreq": "quarterly",
                "priority": "0.9",
            })

    # Landing pages (generated by scripts/generate_new_landing_pages.py
    # and others). Included so full regens preserve them. Filter by the
    # page's actual robots meta, not by filename pattern: the old
    # name-pattern filter kept 10 noindexed *-commercial-mortgage LPs in
    # the sitemap (GSC noise) while the intent was only to list the
    # indexable geo/bridge LPs (found in the 2026-07-09 sitemap-integrity
    # audit).
    for _lp_html in sorted((WEBSITE_DIR / "landing").glob("*.html")):
        try:
            _lp_head = _lp_html.read_text(encoding="utf-8", errors="ignore")[:6000]
        except OSError:
            continue
        if re.search(r'name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', _lp_head, re.I):
            continue
        sitemap_urls.append({
            "loc": f"{BASE_URL}/landing/{_lp_html.name}",
            "lastmod": TODAY,
            "changefreq": "monthly",
            "priority": "0.8",
        })

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
        "agency loans": ("financing", "agency-loans"),
        "agency": ("financing", "agency-loans"),
        "fannie mae": ("financing", "agency-loans"),
        "freddie mac": ("financing", "agency-loans"),
        "hud loans": ("financing", "hud-fha-loans"),
        "fha loans": ("financing", "hud-fha-loans"),
        "hud/fha": ("financing", "hud-fha-loans"),
        "hud": ("financing", "hud-fha-loans"),
        "fha": ("financing", "hud-fha-loans"),
        "cmbs": ("financing", "cmbs-loans"),
        "cmbs loans": ("financing", "cmbs-loans"),
        "life company": ("financing", "life-company-loans"),
        "life companies": ("financing", "life-company-loans"),
        "life insurance company": ("financing", "life-company-loans"),
        "dscr": ("financing", "dscr-loans"),
        "dscr loans": ("financing", "dscr-loans"),
        "dscr loan": ("financing", "dscr-loans"),
        "hard money": ("financing", "hard-money-loans"),
        "hard money loans": ("financing", "hard-money-loans"),
        "hard money loan": ("financing", "hard-money-loans"),
        "portfolio loan": ("financing", "portfolio-loans"),
        "portfolio loans": ("financing", "portfolio-loans"),
        "blanket loan": ("financing", "portfolio-loans"),
        "blanket loans": ("financing", "portfolio-loans"),
        "fix and flip": ("financing", "fix-and-flip-loans"),
        "fix-and-flip": ("financing", "fix-and-flip-loans"),
        "fix and flip loans": ("financing", "fix-and-flip-loans"),
        "stated income": ("financing", "stated-income-loans"),
        "stated income loans": ("financing", "stated-income-loans"),
        "no doc": ("financing", "stated-income-loans"),
        "no-doc": ("financing", "stated-income-loans"),
        "bridge to perm": ("financing", "bridge-to-perm-loans"),
        "bridge-to-perm": ("financing", "bridge-to-perm-loans"),
        "bridge to permanent": ("financing", "bridge-to-perm-loans"),
        "construction to perm": ("financing", "bridge-to-perm-loans"),
        "construction-to-perm": ("financing", "bridge-to-perm-loans"),
        "forward commitment": ("financing", "bridge-to-perm-loans"),
        "multifamily": ("property", "multifamily"),
        "manufactured housing": ("property", "manufactured-housing"),
        "mobile home park": ("property", "manufactured-housing"),
        "mobile home parks": ("property", "manufactured-housing"),
        "mhc": ("property", "manufactured-housing"),
        "manufactured home community": ("property", "manufactured-housing"),
        "parking": ("property", "parking"),
        "parking garage": ("property", "parking"),
        "parking lot": ("property", "parking"),
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
                "title": f"{loan['name']} {city['city']} {city['state']} | CRE Lenders | CLS CRE",
                "meta_description": f"Commercial {loan['name'].lower()} in {city['city']} from {loan.get('min_loan_display', '$1M')}. 1,000+ lender relationships, competitive rates, fast approvals. Free quote. CLS CRE.",
            }
            slug = f"{loan['slug']}-{city['slug']}"
            featured = pick_featured_markets(city, cities, n_total=8)
            # Attach a short context teaser + cross-link URL to each pick
            featured = [{**c, "teaser": first_sentence(c.get("context", ""), 140),
                         "region": region_for_state(c["state"]),
                         "cross_link_url": f"../financing/{loan['slug']}-{c['slug']}.html"}
                        for c in featured]
            html = tpl_city_fin.render(
                **shared,
                loan=loan,
                city=city,
                seo=seo,
                canonical_path=f"financing/{slug}.html",
                depth="../",
                transactions=txns,
                faqs=city_faqs,
                featured_markets=featured,
                current_region=region_for_state(city["state"]),
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
                "title": f"{prop['name']} Loans {city['city']} {city['state']} | CLS CRE",
                "meta_description": f"{prop['name']} financing in {city['city']} from $1M. Banks, life companies, bridge and construction loans. 1,000+ lenders. Free quote. CLS CRE.",
            }
            slug = f"{prop['slug']}-{city['slug']}"
            featured = pick_featured_markets(city, cities, n_total=8)
            featured = [{**c, "teaser": first_sentence(c.get("context", ""), 140),
                         "region": region_for_state(c["state"]),
                         "cross_link_url": f"../property/{prop['slug']}-{c['slug']}.html"}
                        for c in featured]
            html = tpl_city_prop.render(
                **shared,
                prop=prop,
                city=city,
                seo=seo,
                canonical_path=f"property/{slug}.html",
                depth="../",
                transactions=txns,
                faqs=city_faqs,
                featured_markets=featured,
                current_region=region_for_state(city["state"]),
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
            "title": "CRE Insights & Market Analysis | Commercial Lending Solutions",
            "meta_description": "Expert insights on commercial real estate financing, interest rates, market trends, and investment strategies from Commercial Lending Solutions.",
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
                "title": article.get("seo_title") or f"{article['title']} | Commercial Lending Solutions",
                "meta_description": article.get("seo_description") or article["excerpt"],
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

    # ── 6b. Blog articles generated outside articles.json ─────────────
    # Scripts like generate_weekly_rates.py, generate_weekly_affordable.py,
    # and NNN/case-study batch scripts write HTML directly to website/blog/
    # without updating articles.json. Scan the directory and add any files
    # not already in the sitemap so they are never orphaned.
    _blog_in_sitemap = {u["loc"] for u in sitemap_urls if "/blog/" in u["loc"]}
    _extra_blog = 0
    for _blog_html in sorted((WEBSITE_DIR / "blog").glob("*.html")):
        if _blog_html.name == "index.html":
            continue
        _blog_url = f"{BASE_URL}/blog/{_blog_html.name}"
        if _blog_url not in _blog_in_sitemap:
            # Skip noindexed internal docs (marketing playbooks, journalist
            # profiles, etc.) that live in blog/ but must stay out of the
            # sitemap (2026-07-09 sitemap-integrity audit found 4 listed).
            try:
                _blog_head = _blog_html.read_text(encoding="utf-8", errors="ignore")[:6000]
            except OSError:
                continue
            if re.search(r'name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', _blog_head, re.I):
                continue
            sitemap_urls.append({
                "loc": _blog_url,
                "lastmod": TODAY,
                "changefreq": "monthly",
                "priority": "0.7",
            })
            _blog_in_sitemap.add(_blog_url)
            _extra_blog += 1
    if _extra_blog:
        print(f"  [OK] blog/*.html  (+{_extra_blog} extra articles found on disk, added to sitemap)")

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
            "title": "Commercial Real Estate Financing Locations | Commercial Lending Solutions",
            "meta_description": f"Commercial Lending Solutions provides commercial mortgage brokerage in {len(cities)} major U.S. metros. Browse financing programs and property types by city.",
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
                "title": f"{n_name} Commercial Loans | Commercial Lending Solutions",
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
            "title": f"Commercial Real Estate Financing in {city['city']}, {city['state']} | Commercial Lending Solutions",
            "meta_description": f"Explore commercial lending options by neighborhood in {city['city']}, {city['state']}. Browse {len(neighborhoods)} submarkets with financing for every property type.",
        }
        featured = pick_featured_markets(city, cities, n_total=8)
        featured = [{**c, "teaser": first_sentence(c.get("context", ""), 140),
                     "region": region_for_state(c["state"]),
                     "cross_link_url": f"../../markets/{c['slug']}/"}
                    for c in featured]
        html = tpl_market_index.render(
            **shared,
            city=city,
            neighborhoods=neighborhood_list,
            seo=seo_index,
            canonical_path=f"markets/{city['slug']}/",
            depth="../../",
            featured_markets=featured,
            current_region=region_for_state(city["state"]),
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
        ("tool_index.html", "tools/index.html", "tools/", "Calculators & Tools | Commercial Lending Solutions",
         "Free commercial real estate calculators for DSCR, cap rate, and loan payments.", "0.8"),
        ("tool_dscr.html", "tools/dscr-calculator.html", "tools/dscr-calculator.html", "DSCR Calculator | Commercial Lending Solutions",
         "Free Debt Service Coverage Ratio calculator for commercial real estate.", "0.8"),
        ("tool_caprate.html", "tools/cap-rate-calculator.html", "tools/cap-rate-calculator.html", "Cap Rate Calculator | Commercial Lending Solutions",
         "Free capitalization rate calculator for commercial real estate.", "0.8"),
        ("tool_loan.html", "tools/loan-calculator.html", "tools/loan-calculator.html", "Commercial Loan Payment Calculator | Commercial Lending Solutions",
         "Free commercial mortgage payment calculator with I/O periods and amortization.", "0.8"),
        ("tool_ltv.html", "tools/ltv-calculator.html", "tools/ltv-calculator.html", "LTV Calculator | Commercial Lending Solutions",
         "Free Loan-to-Value calculator for commercial real estate. See typical LTV limits by lender type.", "0.8"),
        ("tool_cashoncash.html", "tools/cashoncash-calculator.html", "tools/cashoncash-calculator.html", "Cash-on-Cash Return Calculator | Free CRE Tool",
         "Free cash-on-cash return calculator for commercial real estate. Enter cash invested and annual cash flow to see your return and what counts as good.", "0.8"),
        ("tool_noi.html", "tools/noi-calculator.html", "tools/noi-calculator.html", "NOI Calculator | Commercial Lending Solutions",
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

    # ── 10b. Financing pages generated outside this script ────────────
    # The content-expansion bot writes city pages for loan types that are
    # NOT rendered from loan_types.json (btr-construction, ground-lease,
    # manufactured-housing, agency-lending, ...) directly into
    # website/financing/. Scan the directory and add any indexable file not
    # already collected, so a full regen never drops them from the sitemap
    # again (2026-07-10: a bot regen silently erased 1,445 of them, redoing
    # the exact gap that morning's sitemap-integrity --fix had patched).
    _fin_in_sitemap = {u["loc"] for u in sitemap_urls if "/financing/" in u["loc"]}
    _extra_fin = 0
    for _fin_html in sorted((WEBSITE_DIR / "financing").glob("*.html")):
        _fin_url = f"{BASE_URL}/financing/{_fin_html.name}"
        if _fin_url in _fin_in_sitemap:
            continue
        try:
            _fin_head = _fin_html.read_text(encoding="utf-8", errors="ignore")[:6000]
        except OSError:
            continue
        if re.search(r'name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', _fin_head, re.I):
            continue
        sitemap_urls.append({
            "loc": _fin_url,
            "lastmod": TODAY,
            "changefreq": "monthly",
            "priority": "0.7",
        })
        _fin_in_sitemap.add(_fin_url)
        _extra_fin += 1
    if _extra_fin:
        print(f"  [OK] financing/*.html  (+{_extra_fin} extra pages found on disk, added to sitemap)")

    # ── 11. Sitemap.xml + segmented sitemaps ──────────────────────────
    print("\n=== Generating sitemaps (segmented) ===")
    tpl_sitemap = env.get_template("sitemap.xml.j2")

    # Deduplicate sitemap URLs. The geo_landing.json block and the landing/
    # filesystem scan can both emit the same URL (e.g. los-angeles-bridge-loans).
    # Preserve first-seen order so high-priority entries win.
    _seen_locs = set()
    _deduped = []
    _dup_count = 0
    for _u in sitemap_urls:
        if _u["loc"] not in _seen_locs:
            _seen_locs.add(_u["loc"])
            _deduped.append(_u)
        else:
            _dup_count += 1
    if _dup_count:
        print(f"  [dedup] Removed {_dup_count} duplicate sitemap entries")
    sitemap_urls = _deduped

    # Categorize each URL into a segmented sitemap. Categorization is
    # path-based: the first path segment after the domain determines bucket.
    # Each vertical section gets its OWN sitemap-<vertical>.xml (split from
    # the former shared sitemap-vertical.xml on 2026-07-09) so GSC reports
    # index coverage per vertical instead of one opaque blob.
    _VERTICAL_SECTIONS = {
        "affordable-housing", "industrial", "multifamily", "commercial",
        "life-company", "data-centers", "medical-office", "self-storage",
        "senior-living",
    }

    def _categorize(url):
        path = url["loc"].replace(BASE_URL, "").lstrip("/")
        if path.startswith("financing/"):
            return "financing"
        if path.startswith("property/"):
            return "property"
        if path.startswith("markets/"):
            return "markets"
        if path.startswith("blog/"):
            return "blog"
        if path.startswith("comparisons/"):
            return "comparisons"
        if path.startswith("loan-size/"):
            return "loan-size"
        if path.startswith("research/"):
            return "research"
        if path.startswith("landing/"):
            return "landing"
        _first = path.split("/")[0]
        if _first in _VERTICAL_SECTIONS:
            return _first  # -> sitemap-life-company.xml, sitemap-multifamily.xml, ...
        # Anything else (homepage, about, apply, tools, locations,
        # insights/, professionals/, resources/, root utility pages)
        return "pages"

    segmented = {}
    for url in sitemap_urls:
        segmented.setdefault(_categorize(url), []).append(url)

    # Write each category sitemap
    category_files = []
    for category, urls in sorted(segmented.items()):
        filename = f"sitemap-{category}.xml"
        xml = tpl_sitemap.render(urls=urls)
        (WEBSITE_DIR / filename).write_text(xml, encoding="utf-8")
        category_files.append((filename, len(urls)))
        print(f"  [OK] {filename}  ({len(urls)} URLs)")

    # Remove stale segmented sitemaps from renamed/retired buckets (e.g. the
    # pre-2026-07-09 shared sitemap-vertical.xml). A stale file would keep
    # serving old URLs and mask orphans in the integrity check.
    _current = {fname for fname, _ in category_files} | {"sitemap.xml", "sitemap-index.xml"}
    for _old in sorted(WEBSITE_DIR.glob("sitemap-*.xml")):
        if _old.name not in _current:
            _old.unlink()
            print(f"  [cleanup] Removed stale {_old.name}")

    # Build sitemap-index.xml
    index_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                   '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for filename, _ in category_files:
        index_lines.append(f'  <sitemap><loc>{BASE_URL}/{filename}</loc><lastmod>{TODAY}</lastmod></sitemap>')
    index_lines.append('</sitemapindex>')
    (WEBSITE_DIR / "sitemap-index.xml").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"  [OK] sitemap-index.xml  ({len(category_files)} category sitemaps)")

    # Keep monolithic sitemap.xml for backwards compatibility (existing IndexNow scripts read it)
    sitemap_xml = tpl_sitemap.render(urls=sitemap_urls)
    (WEBSITE_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    print(f"  [OK] sitemap.xml  ({len(sitemap_urls)} URLs, backwards-compat)")

    # ── 12. Robots.txt ─────────────────────────────────────────────────
    print("\n=== Generating robots.txt ===")
    robots = f"""User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap-index.xml
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
