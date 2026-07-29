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

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import time as _time
_orig_write_text = Path.write_text
def _write_text_with_retry(self, *args, **kwargs):
    # OneDrive's cloud filter driver intermittently locks files mid-sync during
    # high-volume writes, raising OSError(22) on an otherwise-valid path/handle.
    for attempt in range(6):
        try:
            return _orig_write_text(self, *args, **kwargs)
        except OSError as e:
            if e.errno == 22 and attempt < 5:
                _time.sleep(0.5 * (attempt + 1))
                continue
            raise
Path.write_text = _write_text_with_retry

from generate_articles import main as generate_articles_main, pacific_today
import la_vertical
import la_industrial
import la_retail
import la_construction
import la_affordable
import la_personas as la_personas_mod


# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
TEMPLATE_DIR = SCRIPT_DIR / "templates"
WEBSITE_DIR = SCRIPT_DIR.parent  # website/

BASE_URL = "https://clscre.com"
# Pacific, not host-local: the UTC content bot would otherwise stamp
# tomorrow's date on every run after 5pm PT (see pacific_today docstring).
TODAY = pacific_today().isoformat()
TODAY_HUMAN = pacific_today().strftime("%B %Y")  # e.g., "May 2026" — for visible bylines


def load_json(name: str):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Asset cache-busting ────────────────────────────────────────────────
# 2026-07-11: a fix to js/antispam.js shipped but Cloudflare edge + browser
# caches (Cache-Control: max-age=14400) kept serving the stale file for up
# to 4 hours, leaving pages blank for visitors after the fix was live.
# Fix: every local js/css reference in every HTML page carries a
# ?v=<content-hash> query string derived from the referenced file's bytes.
# When the asset changes, the hash changes, the URL changes, and Cloudflare/
# browsers treat it as a brand-new cache key — no purge needed. GitHub Pages
# ignores the query string, so nothing else has to change.
#
# Implemented as a post-generation stamping pass over EVERY *.html on disk
# (not just template edits) because large parts of the site are written by
# one-off scripts outside this generator (life-company/, data-centers/,
# expert-witness/, root pages like index.html, ...). The pass is idempotent:
# an existing ?v=... is replaced with the current hash, so repeated bot runs
# only rewrite files whose stamped version actually changed.
# Standalone run: python generate.py --stamp-assets-only

def compute_asset_versions():
    """Map 'js/<name>' / 'css/<name>' / 'tools/<name>' -> 10-hex content
    hash for every .js/.css file under website/js, website/css, and
    website/tools (calculator scripts live next to their pages).

    Windows may check an asset out with different line endings than its Git
    blob. Honor the line-ending form recorded in the index so generated URLs
    match the exact bytes GitHub and Cloudflare deploy.
    """
    index_eols = {}
    try:
        result = subprocess.run(
            ["git", "ls-files", "--eol", "--", "js", "css", "tools"],
            cwd=WEBSITE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            match = re.match(r"i/(lf|crlf)\s+\S+\s+\S+\s+(.+)$", line)
            if match:
                index_eols[match.group(2)] = match.group(1)
    except (OSError, subprocess.CalledProcessError):
        pass

    versions = {}
    for sub in ("js", "css", "tools"):
        d = WEBSITE_DIR / sub
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix in (".js", ".css"):
                content = f.read_bytes().replace(bytes((13, 10)), b"\n")
                rel = f"{sub}/{f.name}"
                if index_eols.get(rel) == "crlf":
                    content = content.replace(b"\n", bytes((13, 10)))
                versions[rel] = hashlib.md5(content).hexdigest()[:10]
    return versions


def stamp_html_asset_versions(html, versions=None):
    """Return HTML with local JS/CSS references stamped by content hash."""
    versions = versions or compute_asset_versions()
    if not versions:
        return html
    alt = "|".join(re.escape(k) for k in sorted(versions, key=len, reverse=True))
    pattern = re.compile(
        r'((?:src|href)=")([^"]*?)(' + alt + r')(\?v=[0-9a-f]{4,32})?(")'
    )

    def _sub(m):
        prefix = m.group(2)
        # Local refs only: "", "/", "../", "../../", ... Never external CDNs
        # ("https://x/js/foo.js") and never partial-name matches ("mycss/...").
        if "//" in prefix or (prefix and not prefix.endswith("/")):
            return m.group(0)
        return f'{m.group(1)}{prefix}{m.group(3)}?v={versions[m.group(3)]}{m.group(5)}'

    return pattern.sub(_sub, html)


def stamp_asset_versions():
    """Rewrite local JS/CSS references in every generated HTML file."""
    print("\n=== Stamping asset versions (cache-busting) ===")
    versions = compute_asset_versions()
    if not versions:
        print("  [skip] no js/css assets found")
        return

    stamped = scanned = 0
    for html_path in WEBSITE_DIR.rglob("*.html"):
        rel = html_path.relative_to(WEBSITE_DIR).as_posix()
        if rel.startswith(("_generator/", ".git/")):
            continue
        scanned += 1
        try:
            html = html_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new_html = stamp_html_asset_versions(html, versions)
        if new_html != html:
            html_path.write_text(new_html, encoding="utf-8")
            stamped += 1
    print(f"  [OK] {stamped} of {scanned} HTML files updated "
          f"({len(versions)} assets: " +
          ", ".join(f"{k}={v}" for k, v in sorted(versions.items())) + ")")


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


def _loan_hub_link_html(loan, depth="../"):
    """Inline anchor to a loan type's national hub page, used inside FAQ answers.
    Uses single-quoted HTML attributes so it can sit inside a double-quoted
    JSON-LD string without breaking the schema block."""
    if not loan:
        return ""
    name = loan["name"]
    slug = loan["slug"]
    if slug == "life-company-loans":
        return (
            f"<a href='{depth}financing/life-company-loans.html'>{name} national overview</a> "
            f"(see also <a href='{depth}financing/life-company-loan-rates.html'>current rates</a> "
            f"and <a href='{depth}financing/how-to-qualify-for-life-company-loans.html'>how to qualify</a>)"
        )
    return f"<a href='{depth}financing/{slug}.html'>our national {name} guide</a>"


def _loan_type_question(name):
    """Natural 'What is/are {name}?' question, avoiding awkward plurals like
    'What are Mezzanine & Preferred Equity?' or 'What are Specialty Financing?'.
    Loan names ending in the plural noun 'Loans' read naturally with 'are';
    everything else (Financing, Preferred Equity, Mezzanine & Preferred Equity,
    etc.) reads naturally with 'is'."""
    verb = "are" if name.endswith("Loans") else "is"
    return f"What {verb} {name}?"


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
            "{loan_type_cap}": loan["name"] if loan else "",
            "{loan_hub_link}": _loan_hub_link_html(loan) if loan else "",
            "{property_type}": prop["name"].lower() if prop else "",
            "{rate_low}": _loan_rate_range(loan)[0],
            "{rate_high}": _loan_rate_range(loan)[1],
            "{context_snippet}": (city.get("context", "")[:120] + "...") if city else "",
        }
        # The "What are {loan_type}?" template needs proper is/are grammar
        # per loan type name (fixes "What are Mezzanine?" / "What are
        # Specialty?" reading wrong), swap it before the generic substitution.
        if loan and q == "What are {loan_type}?":
            q = _loan_type_question(loan["name"])
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
            "q": f"How do I get financing for a commercial property in {neighborhood}?",
            "a": f"Contact Commercial Lending Solutions for a free, no-obligation quote on commercial financing for your {neighborhood} property. Our team will analyze your property, business plan, and financial profile to identify the best lender match from our network of 1,000+ capital sources. Most borrowers receive term sheets within 48-72 hours of submitting a complete loan request. For lender options across all of {city_name}, {state}, see our full {city_name} commercial mortgage guide.",
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
    "AK": "West Coast",
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
    "Mountain West": "High-growth Rocky Mountain and Intermountain markets with sustained in-migration and yield premiums.",
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


def property_financing_slug(label: str) -> str:
    """Map a property-page financing label to its closest program hub."""
    normalized = label.lower()
    rules = (
        ("agency", "agency-loans"),
        ("hud", "hud-fha-loans"),
        ("life insurance", "life-company-loans"),
        ("life company", "life-company-loans"),
        ("cmbs", "cmbs-loans"),
        ("sba", "sba-loans"),
        ("mezzanine", "mezzanine"),
        ("preferred equity", "preferred-equity"),
        ("c-pace", "cpace-financing"),
        ("value-add", "value-add-bridge-loans"),
        ("bridge", "bridge-loans"),
        ("construction-to-perm", "construction-to-perm-loans"),
        ("construction", "construction-loans"),
        ("bank permanent", "permanent-loans"),
        ("specialty", "specialty"),
        ("infrastructure", "specialty"),
    )
    return next(
        (slug for needle, slug in rules if needle in normalized),
        "commercial-mortgage-loans",
    )


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


RATE_BADGE_CLASS = {
    "Bridge": "badge-bridge", "Permanent": "badge-permanent",
    "Construction": "badge-construction", "SBA 7(a)": "badge-sba",
    "SBA 504": "badge-sba", "CMBS": "badge-cmbs",
    "Agency (Fannie/Freddie)": "badge-agency", "HUD/FHA 223(f)": "badge-hud",
    "Life Company": "badge-life", "Net Lease": "badge-net-lease",
    "Hard Money": "badge-hard-money", "Mezzanine": "badge-mezzanine",
}


def render_rates_table():
    """Bake rate rows from tools/rates-data.json into rates.html's tbody.

    Mirrors the row markup produced by rates.html's renderTable() JS so
    non-JS crawlers see identical content to what JS-rendering visitors get.
    """
    from urllib.parse import quote

    print("\n=== Server-rendering rates.html table ===")
    rates_html_path = WEBSITE_DIR / "rates.html"
    rates_data_path = WEBSITE_DIR / "tools" / "rates-data.json"
    if not rates_html_path.exists() or not rates_data_path.exists():
        print("  [SKIP] rates.html or rates-data.json not found")
        return

    def fmt_mo(mo):
        if mo % 12 == 0:
            return f"{mo // 12} Yr"
        return f"{mo} mo"

    def fmt_loan(n):
        if n >= 1_000_000:
            v = n / 1_000_000
            return f"${v:.0f}M" if n % 1_000_000 == 0 else f"${v:.1f}M"
        if n >= 1000:
            return f"${n // 1000}K"
        return f"${n}"

    data = json.loads(rates_data_path.read_text(encoding="utf-8"))
    rows = []
    for r in data:
        badge = RATE_BADGE_CLASS.get(r["product"], "badge-permanent")
        rate_str = f"{r['rateMin']:.2f}%, {r['rateMax']:.2f}%"
        subject = quote(f"Rate Inquiry: {r['product']}, {r['rateMin']:.2f}%-{r['rateMax']:.2f}%")
        rows.append(
            "<tr>"
            f"<td><span class=\"rate-badge {badge}\">{r['product']}</span></td>"
            f"<td class=\"rate-col\">{rate_str}</td>"
            f"<td>{fmt_mo(r['termMonths'])}</td>"
            f"<td>{r['ltvMax']}%</td>"
            f"<td>{r['amort']}</td>"
            f"<td>{fmt_loan(r['minLoan'])}</td>"
            f"<td style=\"font-size:13px\">{r['prepay']}</td>"
            f"<td class=\"notes-col\">{r['notes']}</td>"
            f"<td class=\"cta-col\"><a href=\"mailto:loans@clscre.com?subject={subject}\" class=\"rate-cta-btn\" "
            f"data-product=\"{r['product']}\" data-rate=\"{r['rateMin']}-{r['rateMax']}\">Get This Rate &rarr;</a></td>"
            "</tr>"
        )

    tbody = "<tbody id=\"rateTableBody\">\n        " + "\n        ".join(rows) + "\n      </tbody>"
    html = rates_html_path.read_text(encoding="utf-8")
    new_html, n = re.subn(
        r'<tbody id="rateTableBody">.*?</tbody>', tbody, html, count=1, flags=re.DOTALL
    )
    if n == 0:
        print("  [WARN] rateTableBody tbody not found in rates.html; skipped")
        return
    rates_html_path.write_text(new_html, encoding="utf-8")
    print(f"  [OK] rates.html  ({len(rows)} rate rows baked into static HTML)")


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
    # Hand-curated title/meta overrides for specific city x loan-type pages
    # (e.g. bridge-loans-<city>), keyed by slug. Same durable-override pattern
    # as article seo_title/seo_description -- checked every run, never wiped.
    city_financing_seo_overrides = load_json("city_financing_seo_overrides.json")
    # LA pilot (2026-07-17): loan-type-specific expert prose for city.slug ==
    # 'los-angeles', rendered by city_financing.html's existing LA-only block.
    # Keyed by loan slug; missing entries render nothing (template checks
    # `and la_deepdive`). Extend this file to deepen more LA loan pages --
    # never hand-edit the rendered financing/*.html output, it is regenerated
    # every run from this data.
    la_financing_deepdive = load_json("la_financing_deepdive.json")

    # LA pilot (2026-07-17): same pattern as la_financing_deepdive, for the
    # City x Property Type loop's city_property.html LA-only block. Keyed by
    # property slug; missing entries render nothing.
    la_property_deepdive = load_json("la_property_deepdive.json")

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
        "albany-ny": "albany",
        # 2026-07-13: columbia-sc-2 was a mis-slugged duplicate of columbia-sc
        # (its hub context describes Columbia SC while its neighborhoods are the
        # Rock Hill / York County metro). Zero organic impressions across all
        # 67 pages. Excluded here; static files deleted; 301s staged at Cloudflare.
        # If Rock Hill warrants its own market it should be added as a proper
        # `rock-hill` slug post-freeze, demand-gated per the 2026-07-13 URL audit.
        "columbia-sc-2": "columbia-sc",
    }
    cities = [c for c in cities if c["slug"] not in DUPLICATE_CITY_SLUGS]

    # ── Noindex set (2026-07-13 URL inventory audit) ───────────────────
    # Zero-impression programmatic permutations the audit flagged
    # Consolidate/Noindex. Emitting robots=noindex,follow (internal link
    # equity still flows) and dropping them from the sitemap concentrates
    # crawl budget + ranking authority on the ~1,600 pages that actually earn
    # organic clicks. Membership is keyed by canonical_path. This data file is
    # the single source of truth -- regenerate it from the audit pipeline,
    # never hand-edit. Missing file = empty set (fail-open: nothing noindexed).
    _noindex_file = DATA_DIR / "noindex_paths.json"
    NOINDEX_PATHS = (
        set(json.loads(_noindex_file.read_text(encoding="utf-8")))
        if _noindex_file.exists() else set()
    )
    print(f"  [noindex] {len(NOINDEX_PATHS)} paths flagged noindex + de-sitemapped")

    # ── Redirect map (2026-07-13 URL audit, T2 cannibalization fix) ─────
    # Source canonical_path -> full target URL. The audit found queries
    # split across 2+ pages, all earning 0 clicks. For the clean cases
    # (blog-guide twins, niche-variant financing pages, thin submarket
    # pages losing to their own city hub) we consolidate the loser into
    # the designated winner. Emitted as a static redirect stub (canonical +
    # meta-refresh 0 + JS replace = Google-recognized soft 301) and dropped
    # from the sitemap. True 301s are staged in cloudflare_bulk_redirects.csv
    # for the Cloudflare Bulk Redirect import. Regenerate from the audit
    # pipeline; never hand-edit. Missing file = empty (fail-open).
    _redirect_file = DATA_DIR / "redirect_map.json"
    REDIRECT_PATHS = (
        json.loads(_redirect_file.read_text(encoding="utf-8"))
        if _redirect_file.exists() else {}
    )
    print(f"  [redirect] {len(REDIRECT_PATHS)} paths emit redirect stubs")

    def write_redirect_stub(out_path, target_url):
        """Static soft-301 stub: canonical + meta-refresh + JS to target_url."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>Redirecting</title>'
            '<meta name="robots" content="noindex,follow">'
            f'<link rel="canonical" href="{target_url}">'
            f'<meta http-equiv="refresh" content="0; url={target_url}">'
            f'<script>location.replace({json.dumps(target_url)})</script>'
            '</head><body style="font-family:system-ui,sans-serif;padding:2rem">'
            f'<p>This page has moved. If you are not redirected automatically, '
            f'<a href="{target_url}">continue here</a>.</p></body></html>',
            encoding="utf-8",
        )

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
        # Footer gate: the site-wide "CRE Glossary" footer link only renders
        # once data/glossary.json exists and glossary pages actually generate
        # (otherwise every page would carry a 404 link).
        "has_glossary": (DATA_DIR / "glossary.json").exists(),
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
        # are picked up without hand-editing this list. Guarded against
        # NOINDEX_PATHS + the page's own robots meta (2026-07-18 migration
        # watch audit found mezzanine-loan-rates.html flagged noindex in the
        # audit file but never actually de-sitemapped -- this glob predates
        # the NOINDEX_PATHS check added elsewhere in this function).
        *[
            {"loc": f"{BASE_URL}/financing/{_rate_path.name}", "lastmod": TODAY, "changefreq": "monthly", "priority": "0.9"}
            for _rate_path in sorted((WEBSITE_DIR / "financing").glob("*-rates.html"))
            if f"financing/{_rate_path.name}" not in NOINDEX_PATHS
            and not re.search(r'name=["\']robots["\'][^>]*noindex', _rate_path.read_text(encoding="utf-8", errors="ignore")[:6000], re.I)
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
                # contact/index.html intentionally absent: it rel-canonicals
                # to /contact.html (already listed above), so sitemapping it
                # only produces "duplicate, not selected as canonical" noise in GSC.
                ("expert-witness/index.html", "weekly", "0.9"),
                ("developers/index.html", "monthly", "0.8"),
                ("build-to-rent/index.html", "monthly", "0.8"),
                ("senior-housing/index.html", "monthly", "0.8"),
                ("privacy.html", "yearly", "0.3"),
                ("terms.html", "yearly", "0.3"),
                ("disclaimer.html", "yearly", "0.3"),
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
                _geo_file = WEBSITE_DIR / "landing" / f"{_geo_slug}.html"
                if not _geo_file.exists():
                    continue
                # /landing/ pages are noindex,nofollow ad LPs by rule. A noindex
                # URL in the sitemap is a GSC error ("Submitted URL marked
                # noindex"); this block previously added them unconditionally,
                # which put 43 noindex LPs in the sitemap (2026-07-15 audit).
                # Filter by the page's actual robots meta, matching the landing
                # glob block below.
                _geo_head = _geo_file.read_text(encoding="utf-8", errors="ignore")[:8000]
                if re.search(r'name=["\']robots["\'][^>]*noindex', _geo_head, re.I):
                    continue
                sitemap_urls.append({
                    "loc": f"{BASE_URL}/landing/{_geo_slug}.html",
                    "lastmod": TODAY,
                    "changefreq": "weekly",
                    "priority": "0.9",
                })
        for _s in _geo.get("tier2_la_submarkets", []):
            _la_path = WEBSITE_DIR / "markets" / "la" / f"{_s['slug']}.html"
            if not _la_path.exists():
                continue
            # 2026-07-24: /markets/la/ tier2 system retired -- content migrated
            # to hand-authored markets/los-angeles/ pages on 2026-07-17. Any
            # slug in redirect_map.json gets a soft-301 stub and stays out of
            # the sitemap (same pattern as the deal-size block above).
            _la_redir = REDIRECT_PATHS.get(f"markets/la/{_s['slug']}.html")
            if _la_redir:
                write_redirect_stub(_la_path, _la_redir)
                continue
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
                    _vrel = f"{_vslug}/markets/{_slug}.html"
                    _vpath = WEBSITE_DIR / _vrel
                    _vredir = REDIRECT_PATHS.get(_vrel)
                    if _vredir:
                        write_redirect_stub(_vpath, _vredir)
                        continue
                    if _vpath.exists():
                        sitemap_urls.append({
                            "loc": f"{BASE_URL}/{_vrel}",
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
    # scripts/generate_deal_size_city_pages.py). Both generator scripts no
    # longer exist in the repo, so these are now static files; listed here
    # so full regens preserve them in the sitemap. Any path merged into
    # redirect_map.json gets its stub rewritten (in case something restores
    # real content) and is excluded from the sitemap.
    for _ds_html in sorted((WEBSITE_DIR / "financing").glob("*-million-*.html")):
        _ds_rel = f"financing/{_ds_html.name}"
        _ds_redir = REDIRECT_PATHS.get(_ds_rel)
        if _ds_redir:
            write_redirect_stub(_ds_html, _ds_redir)
            continue
        sitemap_urls.append({
            "loc": f"{BASE_URL}/{_ds_rel}",
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
    # regens preserve them in the sitemap. Guarded against NOINDEX_PATHS
    # (2026-07-18 migration watch audit: 4 of these were flagged noindex in
    # the audit file but never actually de-sitemapped -- this block predates
    # the NOINDEX_PATHS check added elsewhere in this function).
    _specialty_data = DATA_DIR / "specialty_properties.json"
    if _specialty_data.exists():
        for _sp in json.loads(_specialty_data.read_text(encoding="utf-8")):
            if f"property/{_sp['slug']}.html" in NOINDEX_PATHS:
                # 2026-07-25: these are static files no render loop touches,
                # so also patch the robots meta onto disk (same pattern as the
                # blog/ static patcher) -- a noindex_paths.json entry alone
                # never reaches their markup, leaving them de-sitemapped but
                # crawl-indexable (found by cls-sitemap-integrity).
                _sp_path = WEBSITE_DIR / "property" / f"{_sp['slug']}.html"
                if _sp_path.exists():
                    _sp_full = _sp_path.read_text(encoding="utf-8", errors="ignore")
                    if not re.search(r'name=["\']robots["\'][^>]*noindex', _sp_full[:6000], re.I):
                        _sp_patched, _sp_n = re.subn(
                            r'(<link rel="canonical")',
                            '<meta name="robots" content="noindex,follow">\n\\1',
                            _sp_full, count=1,
                        )
                        if _sp_n:
                            _sp_path.write_text(_sp_patched, encoding="utf-8")
                continue
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
    tpl_financing = env.get_template("financing_conversion_page.html")
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
    tpl_property = env.get_template("property_conversion_page.html")
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
            financing_links=[
                {"label": label, "slug": property_financing_slug(label)}
                for label in prop["financing_options"]
            ],
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
            slug = f"{loan['slug']}-{city['slug']}"
            seo = {
                "title": f"{loan['name']} {city['city']} {city['state']} | CRE Lenders | Commercial Lending Solutions",
                "meta_description": f"Commercial {loan['name'].lower()} in {city['city']} from {loan.get('min_loan_display', '$1M')}. 1,000+ lender relationships, competitive rates, fast approvals. Free quote. Commercial Lending Solutions.",
            }
            seo.update(city_financing_seo_overrides.get(slug, {}))
            featured = pick_featured_markets(city, cities, n_total=8)
            # Attach a short context teaser + cross-link URL to each pick
            featured = [{**c, "teaser": first_sentence(c.get("context", ""), 140),
                         "region": region_for_state(c["state"]),
                         "cross_link_url": f"../financing/{loan['slug']}-{c['slug']}.html"}
                        for c in featured]
            _redir = REDIRECT_PATHS.get(f"financing/{slug}.html")
            if _redir:
                write_redirect_stub(WEBSITE_DIR / "financing" / f"{slug}.html", _redir)
                page_count += 1
                continue
            _is_noindex = f"financing/{slug}.html" in NOINDEX_PATHS
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
                noindex=_is_noindex,
                la_deepdive=la_financing_deepdive.get(loan["slug"]),
            )
            out_path = WEBSITE_DIR / "financing" / f"{slug}.html"
            out_path.write_text(html, encoding="utf-8")
            page_count += 1
            if not _is_noindex:
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
                "title": f"{prop['name']} Loans {city['city']} {city['state']} | Commercial Lending Solutions",
                "meta_description": f"{prop['name']} financing in {city['city']} from $1M. Banks, life companies, bridge and construction loans. 1,000+ lenders. Free quote. Commercial Lending Solutions.",
            }
            slug = f"{prop['slug']}-{city['slug']}"
            featured = pick_featured_markets(city, cities, n_total=8)
            featured = [{**c, "teaser": first_sentence(c.get("context", ""), 140),
                         "region": region_for_state(c["state"]),
                         "cross_link_url": f"../property/{prop['slug']}-{c['slug']}.html"}
                        for c in featured]
            _redir = REDIRECT_PATHS.get(f"property/{slug}.html")
            if _redir:
                write_redirect_stub(WEBSITE_DIR / "property" / f"{slug}.html", _redir)
                page_count += 1
                continue
            _is_noindex = f"property/{slug}.html" in NOINDEX_PATHS
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
                noindex=_is_noindex,
                la_deepdive=la_property_deepdive.get(prop["slug"]),
            )
            out_path = WEBSITE_DIR / "property" / f"{slug}.html"
            out_path.write_text(html, encoding="utf-8")
            page_count += 1
            if not _is_noindex:
                sitemap_urls.append({
                    "loc": f"{BASE_URL}/property/{slug}.html",
                    "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
                })
        print(f"  [OK] property/{prop['slug']}-*.html  ({len(cities)} city pages)")

    # ── 5. Blog Index Pages (paginated) ────────────────────────────────
    # The blog index used to render ALL articles on one page. At 4,451
    # articles that was 3.2MB of HTML — bad for UX, page speed, and crawl
    # efficiency. Now paginated: blog/index.html is page 1, then
    # blog/page/2.html ... blog/page/N.html. The old client-side category
    # filter is replaced by real category hub pages (also paginated) at
    # blog/category/{slug}.html + blog/category/{slug}-{n}.html, so every
    # article stays reachable by crawlers through two link paths.
    # Every listing page is self-canonical (page 1 canonicalizes to /blog/
    # as before); rel prev/next links are emitted via the extra_meta block.
    print("\n=== Generating Blog Pages ===")
    tpl_blog_index = env.get_template("blog_index.html")
    categories = sorted(set(a["category"] for a in articles))

    BLOG_PAGE_SIZE = 48

    def _cat_slug(cat):
        return re.sub(r"[^a-z0-9]+", "-", cat.lower()).strip("-")

    category_links = [
        {"name": c, "slug": _cat_slug(c), "href": f"blog/category/{_cat_slug(c)}.html"}
        for c in categories
    ]

    def _page_number_items(cur, total, href_for):
        """Windowed page-number list: 1 2 ... cur-1 cur cur+1 ... N-1 N."""
        nums = sorted(n for n in {1, 2, cur - 1, cur, cur + 1, total - 1, total}
                      if 1 <= n <= total)
        items, prev = [], 0
        for n in nums:
            if n - prev > 1:
                items.append({"ellipsis": True})
            items.append({"num": n, "current": n == cur, "href": href_for(n)})
            prev = n
        return items

    _blog_listing_written = set()

    def _render_blog_listing(listing_articles, *, href_for, out_path_for,
                             canonical_for, depth_for, seo_for, hero_for,
                             active_category, active_category_slug,
                             priority_for):
        """Render one paginated listing series (main index or one category)."""
        nonlocal page_count
        total_pages = max(1, -(-len(listing_articles) // BLOG_PAGE_SIZE))
        for n in range(1, total_pages + 1):
            chunk = listing_articles[(n - 1) * BLOG_PAGE_SIZE : n * BLOG_PAGE_SIZE]
            hero = hero_for(n, total_pages)
            _is_noindex = canonical_for(n) in NOINDEX_PATHS
            html = tpl_blog_index.render(
                **shared,
                articles=chunk,
                category_links=category_links,
                active_category=active_category,
                active_category_slug=active_category_slug,
                is_blog_root=(active_category is None and n == 1),
                pagination={
                    "current": n,
                    "total": total_pages,
                    "prev": href_for(n - 1) if n > 1 else None,
                    "next": href_for(n + 1) if n < total_pages else None,
                    # key is "pages", not "items": pagination.items in Jinja
                    # resolves to dict.items (the method), not the key
                    "pages": _page_number_items(n, total_pages, href_for),
                },
                page_num=n,
                total_articles=len(listing_articles),
                page_start=(n - 1) * BLOG_PAGE_SIZE + 1,
                page_end=(n - 1) * BLOG_PAGE_SIZE + len(chunk),
                rel_prev=f"{BASE_URL}/{canonical_for(n - 1)}" if n > 1 else None,
                rel_next=f"{BASE_URL}/{canonical_for(n + 1)}" if n < total_pages else None,
                hero_title=hero["title"],
                hero_intro=hero["intro"],
                seo=seo_for(n, total_pages),
                canonical_path=canonical_for(n),
                depth=depth_for(n),
                noindex=_is_noindex,
            )
            out_path = out_path_for(n)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html, encoding="utf-8")
            _blog_listing_written.add(out_path)
            page_count += 1
            if not _is_noindex:
                sitemap_urls.append({
                    "loc": f"{BASE_URL}/{canonical_for(n)}",
                    "lastmod": TODAY,
                    "changefreq": "weekly" if n == 1 else "monthly",
                    "priority": priority_for(n),
                })
        return total_pages

    # Main chronological index: blog/ + blog/page/N.html
    def _main_href(n):
        return "blog/index.html" if n == 1 else f"blog/page/{n}.html"

    def _main_seo(n, total):
        if n == 1:
            return {
                "title": "CRE Insights & Market Analysis | Commercial Lending Solutions",
                "meta_description": "Expert insights on commercial real estate financing, interest rates, market trends, and investment strategies from Commercial Lending Solutions.",
            }
        return {
            "title": f"CRE Insights & Market Analysis | Page {n} of {total} | Commercial Lending Solutions",
            "meta_description": f"Commercial real estate financing insights from Commercial Lending Solutions. Page {n} of {total}, newest articles first.",
        }

    def _main_hero(n, total):
        intro = ("Expert analysis on CRE financing, market trends, investment "
                 "strategies, and industry news from the CLS CRE team.")
        if n > 1:
            intro += f" Page {n} of {total}."
        return {"title": "Commercial Real Estate Insights", "intro": intro}

    _main_pages = _render_blog_listing(
        articles,
        href_for=_main_href,
        out_path_for=lambda n: WEBSITE_DIR / "blog" / ("index.html" if n == 1 else f"page/{n}.html"),
        canonical_for=lambda n: "blog/" if n == 1 else f"blog/page/{n}.html",
        depth_for=lambda n: "../" if n == 1 else "../../",
        seo_for=_main_seo,
        hero_for=_main_hero,
        active_category=None,
        active_category_slug=None,
        priority_for=lambda n: "0.8" if n == 1 else "0.3",
    )
    print(f"  [OK] blog/index.html + blog/page/*.html  ({len(articles)} articles across {_main_pages} pages)")

    # Category hub pages: blog/category/{slug}.html + blog/category/{slug}-N.html
    _cat_pages_total = 0
    for _cl in category_links:
        _cat_name, _slug = _cl["name"], _cl["slug"]
        _cat_articles = [a for a in articles if a["category"] == _cat_name]
        _cat_count = len(_cat_articles)
        # Multiword categories read as a phrase ("Rate Commentary"); single
        # words ("Educational") need a noun for the H1.
        _cat_h1 = _cat_name if " " in _cat_name else f"{_cat_name} Articles"

        def _cat_href(n, s=_slug):
            return f"blog/category/{s}.html" if n == 1 else f"blog/category/{s}-{n}.html"

        def _cat_seo(n, total, cat=_cat_name, count=_cat_count):
            if n == 1:
                return {
                    "title": f"{cat} | CRE Insights | Commercial Lending Solutions",
                    "meta_description": f"All {count} {cat} articles from Commercial Lending Solutions. Commercial real estate financing analysis, newest first.",
                }
            return {
                "title": f"{cat} | Page {n} of {total} | Commercial Lending Solutions",
                "meta_description": f"{cat} articles from Commercial Lending Solutions. Page {n} of {total}, newest articles first.",
            }

        def _cat_hero(n, total, h1=_cat_h1, cat=_cat_name, count=_cat_count):
            intro = (f"All {count} {cat} articles from the CLS CRE team, "
                     "newest first.")
            if n > 1:
                intro += f" Page {n} of {total}."
            return {"title": h1, "intro": intro}

        _cat_pages_total += _render_blog_listing(
            _cat_articles,
            href_for=_cat_href,
            out_path_for=lambda n, s=_slug: WEBSITE_DIR / "blog" / "category" / (f"{s}.html" if n == 1 else f"{s}-{n}.html"),
            canonical_for=_cat_href,
            depth_for=lambda n: "../../",
            seo_for=_cat_seo,
            hero_for=_cat_hero,
            active_category=_cat_name,
            active_category_slug=_slug,
            priority_for=lambda n: "0.4" if n == 1 else "0.3",
        )
    print(f"  [OK] blog/category/*.html  ({len(category_links)} categories across {_cat_pages_total} pages)")

    # Remove stale listing pages (e.g. after the article count shrinks or a
    # category disappears) so old paginated URLs never linger as orphans.
    for _dir in (WEBSITE_DIR / "blog" / "page", WEBSITE_DIR / "blog" / "category"):
        if _dir.exists():
            for _old in _dir.glob("*.html"):
                if _old not in _blog_listing_written:
                    _old.unlink()
                    print(f"  [cleanup] Removed stale blog listing {_old.name}")

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
        _redir = REDIRECT_PATHS.get(f"blog/{article['slug']}.html")
        if _redir:
            write_redirect_stub(WEBSITE_DIR / "blog" / f"{article['slug']}.html", _redir)
            page_count += 1
            continue
        _is_noindex = f"blog/{article['slug']}.html" in NOINDEX_PATHS
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
            noindex=_is_noindex,
        )
        out_path = WEBSITE_DIR / "blog" / f"{article['slug']}.html"
        out_path.write_text(html, encoding="utf-8")
        page_count += 1
        if not _is_noindex:
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
    _orphan_noindex_patched = 0
    for _blog_html in sorted((WEBSITE_DIR / "blog").glob("*.html")):
        if _blog_html.name == "index.html":
            continue
        _rel = f"blog/{_blog_html.name}"
        _blog_url = f"{BASE_URL}/{_rel}"
        try:
            _blog_full = _blog_html.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        _blog_head = _blog_full[:6000]
        _has_noindex_tag = bool(re.search(r'name=["\']robots["\'][^>]*content=["\'][^"\']*noindex', _blog_head, re.I))
        # These files never pass through tpl_blog_article.render(), so a
        # noindex_paths.json entry alone never reaches their markup -- patch
        # the robots meta tag directly onto disk so the flag actually takes
        # effect (2026-07-17: found via a URL audit follow-up).
        if _rel in NOINDEX_PATHS and not _has_noindex_tag:
            _patched, _n = re.subn(
                r'(<link rel="canonical")',
                '<meta name="robots" content="noindex,follow">\n\\1',
                _blog_full, count=1,
            )
            if _n:
                _blog_html.write_text(_patched, encoding="utf-8")
                _has_noindex_tag = True
                _orphan_noindex_patched += 1
        if _blog_url not in _blog_in_sitemap:
            # Skip noindexed internal docs (marketing playbooks, journalist
            # profiles, etc.) that live in blog/ but must stay out of the
            # sitemap (2026-07-09 sitemap-integrity audit found 4 listed).
            if _has_noindex_tag:
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
    if _orphan_noindex_patched:
        print(f"  [noindex] patched robots meta tag onto {_orphan_noindex_patched} orphaned blog page(s)")

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
    # Hand-authored LA neighborhood pages (2026-07-17 tier2 migration): these
    # 15 slugs under markets/los-angeles/ carry real submarket-specific prose
    # migrated from the retired /markets/la/ tier2 system, not the generic
    # name-swapped submarket_page.html template. Skip regenerating them so a
    # full regen doesn't stomp the content back to boilerplate -- still add
    # to sitemap_urls below since they're live and indexable. To edit these,
    # hand-edit website/markets/los-angeles/{slug}.html directly.
    LA_HAND_AUTHORED_NEIGHBORHOODS = {
        "downtown-la", "hollywood", "koreatown", "santa-monica", "beverly-hills",
        "long-beach", "pasadena", "glendale", "west-la", "el-segundo",
        "arts-district", "mid-wilshire", "playa-vista", "culver-city", "silver-lake",
        # 2026-07-17 second pass: brentwood revived as-is; burbank + sherman-oaks
        # added as new neighborhoods.json entries (previously only existed as
        # /markets/la/ tier2 pages with no canonical 1:1 slug -- each carries
        # genuinely distinct content, so they get their own pages rather than
        # collapsing into the generic "San Fernando Valley" region entry).
        "brentwood", "burbank", "sherman-oaks",
    }
    # 2026-07-20 Chicago pilot: same hand-authored pattern as LA, generalized to
    # a per-city dict so future metro pilots just add a new key here instead of
    # duplicating the LA-only branch below. Naperville/oak-brook/river-north/
    # schaumburg were noindexed generic submarket_page.html boilerplate; revived
    # with real submarket-specific content. Lincoln Park and The Loop stay on
    # the generic template for now (already indexed, lower priority to deepen).
    HAND_AUTHORED_NEIGHBORHOODS = {
        "los-angeles": LA_HAND_AUTHORED_NEIGHBORHOODS,
        "chicago": {"naperville", "oak-brook", "river-north", "schaumburg"},
    }
    # LA pilot (2026-07-18): guide directory + persona router for the
    # markets/los-angeles/index.html LA-only block, folded in as part of
    # retiring the separate los-angeles/index.html hub (Phase 5 merge).
    # Computed once here (not per-city) since these are pure/static builds;
    # the template only uses them under {% if city.slug == 'los-angeles' %}.
    _la_hub_guides = la_vertical.build_guides() + la_construction.build_guides() + la_affordable.build_guides()
    _la_hub_guide_groups = [{"category": c, "guides": [g for g in _la_hub_guides if g["category"] == c]}
                            for c in dict.fromkeys(g["category"] for g in _la_hub_guides)]
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
            _redir = REDIRECT_PATHS.get(canonical)
            if _redir:
                write_redirect_stub(city_market_dir / f"{n_slug}.html", _redir)
                page_count += 1
                submarket_count += 1
                continue
            if n_slug in HAND_AUTHORED_NEIGHBORHOODS.get(city["slug"], ()):
                # Hand-authored, do not overwrite -- see HAND_AUTHORED_NEIGHBORHOODS above.
                page_count += 1
                submarket_count += 1
                sitemap_urls.append({
                    "loc": f"{BASE_URL}/{canonical}",
                    "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
                })
                continue
            _is_noindex = canonical in NOINDEX_PATHS
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
                noindex=_is_noindex,
            )
            out_path = city_market_dir / f"{n_slug}.html"
            out_path.write_text(html, encoding="utf-8")
            page_count += 1
            submarket_count += 1
            if not _is_noindex:
                sitemap_urls.append({
                    "loc": f"{BASE_URL}/{canonical}",
                    "lastmod": TODAY, "changefreq": "monthly", "priority": "0.6",
                })
        # Generate city market index page.
        # This hub page OWNS the generic "[city] commercial real estate loans" /
        # "[city] commercial mortgage" head queries; the /financing/ and /property/
        # spokes target their product-specific queries and link back here.
        seo_index = {
            "title": f"{city['city']}, {city['state']} Commercial Real Estate Loans & Mortgages | Commercial Lending Solutions",
            "meta_description": f"Commercial real estate loans in {city['city']}, {city['state']}: bridge, permanent, construction, SBA and every major program from 1,000+ lenders. Free quote from a commercial mortgage broker.",
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
            la_hub_guide_groups=_la_hub_guide_groups,
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
        ("tool_qualifier.html", "tools/loan-qualifier.html", "tools/loan-qualifier.html", "What Commercial Loan Do I Qualify For? | Free CRE Tool",
         "Answer six questions about your deal and see which commercial loan programs fit, with typical rates, terms, and leverage. Free qualifier from CLS CRE.", "0.9"),
        ("tool_dscr.html", "tools/dscr-calculator.html", "tools/dscr-calculator.html", "DSCR Calculator: See Your Ratio vs the 1.25x Lender Minimum",
         "Calculate your commercial property's debt service coverage ratio instantly. Enter NOI and annual debt service to see your DSCR and whether it clears the 1.20x to 1.25x most CRE lenders require.", "0.8"),
        ("tool_caprate.html", "tools/cap-rate-calculator.html", "tools/cap-rate-calculator.html", "Cap Rate Calculator: NOI / Price + What Counts as a Good Cap Rate",
         "Free cap rate calculator for commercial real estate. Enter NOI and purchase price to get your cap rate instantly, plus benchmark ranges by property type.", "0.8"),
        ("tool_loan.html", "tools/loan-calculator.html", "tools/loan-calculator.html", "Commercial Loan Payment Calculator | Commercial Lending Solutions",
         "Free commercial mortgage payment calculator with I/O periods and amortization.", "0.8"),
        ("tool_ltv.html", "tools/ltv-calculator.html", "tools/ltv-calculator.html", "LTV Calculator | Commercial Lending Solutions",
         "Free Loan-to-Value calculator for commercial real estate. See typical LTV limits by lender type.", "0.8"),
        ("tool_cashoncash.html", "tools/cashoncash-calculator.html", "tools/cashoncash-calculator.html", "Cash-on-Cash Return Calculator: Formula + What's Good",
         "Free cash-on-cash return calculator for commercial real estate. Enter cash invested and annual cash flow to see your return in seconds, plus what counts as a good number.", "0.8"),
        ("tool_noi.html", "tools/noi-calculator.html", "tools/noi-calculator.html", "NOI Calculator: Net Operating Income in Seconds | Free",
         "Calculate net operating income for any commercial property. Enter gross income, vacancy, and operating expenses to get the NOI every CRE lender underwrites to.", "0.8"),
        ("tool_debtyield.html", "tools/debt-yield-calculator.html", "tools/debt-yield-calculator.html", "Debt Yield Calculator | Commercial Lending Solutions",
         "Free debt yield calculator for commercial real estate. NOI divided by loan amount, plus typical lender minimums and the max loan each floor supports.", "0.8"),
        ("tool_la_rentcontrol.html", "tools/la-rent-control-checker.html", "tools/la-rent-control-checker.html", "LA Rent Control Checker | Commercial Lending Solutions",
         "Free tool: enter jurisdiction, year built, and unit count to see whether an LA-area apartment building falls under RSO, a municipal rent ordinance, or AB 1482, and what it means for financing.", "0.8"),
        ("tool_welfare.html", "tools/welfare-exemption-calculator.html", "tools/welfare-exemption-calculator.html", "Welfare Exemption Equity Reduction Calculator | Commercial Lending Solutions",
         "Free tool for LA affordable developers: estimate the property tax savings, NOI lift, value lift, and reduced equity the California Welfare Exemption creates on your deal.", "0.8"),
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

    # ── 9a. Los Angeles Neighborhood Financing Vertical ─────────────────
    # Round 1 (2026-07-10/11): hub + 6 regulatory guides + neighborhood-by-
    # neighborhood apartment financing index (la_vertical.py). Curated
    # ~30-submarket set, not a mail-merged canonical LA neighborhood list --
    # see la_vertical.py module docstring for the scope rationale.
    # Round 2 (2026-07-11): + 9 industrial submarkets (la_industrial.py),
    # 9 retail corridors (la_retail.py), 4 more construction guides folded
    # into la_vertical.py's guide list, and 3 persona hub pages (investors/
    # developers/owner-users, la_personas.py) rendered through the same
    # la_guide.html template at /los-angeles/{slug}.html.
    print("\n=== Generating Los Angeles Vertical ===")
    la_hoods = la_vertical.build_hoods()
    la_hood_groups = la_vertical.build_hood_groups(la_hoods)
    la_guides = la_vertical.build_guides() + la_construction.build_guides() + la_affordable.build_guides()
    la_hood_count = len(la_hoods)

    la_industrial_hoods = la_industrial.build_hoods()
    la_industrial_groups = la_industrial.build_hood_groups(la_industrial_hoods)
    la_industrial_count = len(la_industrial_hoods)

    la_retail_hoods = la_retail.build_hoods()
    la_retail_groups = la_retail.build_hood_groups(la_retail_hoods)
    la_retail_count = len(la_retail_hoods)

    la_personas = la_personas_mod.build_personas()

    # Everything rendered at /los-angeles/{slug}.html shares one URL space
    # and one related-articles pool, regardless of whether it's a
    # regulatory guide or a persona hub page.
    la_articles = la_guides + la_personas

    la_dir = WEBSITE_DIR / "los-angeles"
    la_dir.mkdir(exist_ok=True)
    mf_la_dir = WEBSITE_DIR / "multifamily" / "la"
    mf_la_dir.mkdir(parents=True, exist_ok=True)
    ind_la_dir = WEBSITE_DIR / "industrial" / "la"
    ind_la_dir.mkdir(parents=True, exist_ok=True)
    ret_la_dir = WEBSITE_DIR / "retail" / "la"
    ret_la_dir.mkdir(parents=True, exist_ok=True)

    # Group guides (not personas -- those get their own hero cards) by
    # category for the hub page, in first-seen order.
    _la_guide_cats = []
    for g in la_guides:
        if g["category"] not in _la_guide_cats:
            _la_guide_cats.append(g["category"])
    la_guide_groups = [{"category": c, "guides": [g for g in la_guides if g["category"] == c]}
                        for c in _la_guide_cats]

    # LA submarket directory (Tier 2 /markets/la/*): link every submarket
    # page that exists on disk from the hub, grouped by region. Source of
    # truth is geo_landing.json's tier2_la_submarkets (same list generate.py
    # already uses to sitemap them). Rendering this natively in the template
    # keeps the 20 submarket pages from re-orphaning on a full regen -- a
    # prior hand-edit to the rendered hub was silently wiped by the next run.
    _geo_la = json.loads((DATA_DIR / "geo_landing.json").read_text(encoding="utf-8"))
    la_submarkets = [s for s in _geo_la.get("tier2_la_submarkets", [])
                     if (WEBSITE_DIR / "markets" / "la" / f"{s['slug']}.html").exists()
                     # 2026-07-24: retired /markets/la/ pages that now soft-301
                     # to markets/los-angeles/ twins must not be hub-linked.
                     and f"markets/la/{s['slug']}.html" not in REDIRECT_PATHS]

    # Hub: /los-angeles/index.html -- RETIRED 2026-07-18 (Phase 5 merge). This
    # was a third overlapping LA hub competing with the canonical
    # markets/los-angeles/ city index. Its two genuinely useful sections (the
    # persona picker + the guide-by-category directory) were folded directly
    # into market_city_index.html's LA-only block (see _la_hub_guide_groups
    # above); every internal link that used to point here now points at
    # markets/los-angeles/ instead (city_financing.html, city_property.html,
    # la_guide.html, la_apartment_page.html, la_industrial_page.html,
    # la_retail_page.html, la_apartments_index.html, la_industrial_index.html,
    # la_retail_index.html, tool_la_rentcontrol.html, _footer.html). This
    # write_redirect_stub call is a safety net only -- REDIRECT_PATHS also
    # covers this path -- so the page still soft-redirects even if the
    # skip-guard below were ever removed accidentally.
    write_redirect_stub(la_dir / "index.html", "https://clscre.com/markets/los-angeles/")

    # Guides + personas: /los-angeles/{slug}.html
    tpl_la_guide = env.get_template("la_guide.html")
    _la_by_slug = {a["slug"]: a for a in la_articles}
    for article in la_articles:
        # Prefer per-guide related_slugs (ED1 money URL, etc.); else first 3 peers.
        related = []
        for s in article.get("related_slugs") or []:
            if s in _la_by_slug and s != article["slug"]:
                related.append(_la_by_slug[s])
        if not related:
            related = [a for a in la_articles if a["slug"] != article["slug"]][:3]
        else:
            related = related[:6]
        html = tpl_la_guide.render(
            **shared,
            guide=article,
            related_guides=related,
            hood_count=la_hood_count,
            seo=article["seo"],
            canonical_path=f"los-angeles/{article['slug']}.html",
            depth="../",
        )
        (la_dir / f"{article['slug']}.html").write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/los-angeles/{article['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.8",
        })
    print(f"  [OK] los-angeles/*.html  ({len(la_guides)} guides + {len(la_personas)} persona pages)")

    # Apartments index: /multifamily/la/index.html
    tpl_la_apt_index = env.get_template("la_apartments_index.html")
    html = tpl_la_apt_index.render(
        **shared,
        hood_groups=la_hood_groups,
        hood_count=la_hood_count,
        seo={
            "title": "LA Apartment Loans by Neighborhood | Commercial Lending Solutions",
            "meta_description": (
                f"Apartment financing across {la_hood_count} Los Angeles neighborhoods: rent "
                "regulation, building vintage, and financing playbook for each submarket. Bridge, "
                "agency, bank, and construction loans."
            ),
        },
        canonical_path="multifamily/la/index.html",
        depth="../../",
    )
    (mf_la_dir / "index.html").write_text(html, encoding="utf-8")
    page_count += 1
    sitemap_urls.append({
        "loc": f"{BASE_URL}/multifamily/la/index.html",
        "lastmod": TODAY, "changefreq": "weekly", "priority": "0.9",
    })
    print("  [OK] multifamily/la/index.html")

    # Per-neighborhood pages: /multifamily/la/{slug}.html
    tpl_la_hood = env.get_template("la_apartment_page.html")
    for hood in la_hoods:
        nearby = la_vertical.nearby_hoods(la_hoods, hood["slug"], hood["region"])
        html = tpl_la_hood.render(
            **shared,
            hood=hood,
            nearby=nearby,
            seo=hood["seo"],
            canonical_path=f"multifamily/la/{hood['slug']}.html",
            depth="../../",
        )
        (mf_la_dir / f"{hood['slug']}.html").write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/multifamily/la/{hood['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
        })
    print(f"  [OK] multifamily/la/*.html  ({la_hood_count} neighborhood pages)")

    # Industrial index + per-submarket pages: /industrial/la/*.html
    tpl_la_ind_index = env.get_template("la_industrial_index.html")
    html = tpl_la_ind_index.render(
        **shared,
        hood_groups=la_industrial_groups,
        hood_count=la_industrial_count,
        seo={
            "title": "LA Industrial Loans by Submarket | Commercial Lending Solutions",
            "meta_description": (
                f"Industrial financing across {la_industrial_count} Los Angeles submarkets: South "
                "Bay logistics, Vernon manufacturing, port-adjacent distribution. Bank, bridge, "
                "SBA, and construction loans."
            ),
        },
        canonical_path="industrial/la/index.html",
        depth="../../",
    )
    (ind_la_dir / "index.html").write_text(html, encoding="utf-8")
    page_count += 1
    sitemap_urls.append({
        "loc": f"{BASE_URL}/industrial/la/index.html",
        "lastmod": TODAY, "changefreq": "weekly", "priority": "0.9",
    })
    tpl_la_ind_hood = env.get_template("la_industrial_page.html")
    for hood in la_industrial_hoods:
        nearby = la_industrial.nearby_hoods(la_industrial_hoods, hood["slug"], hood["region"])
        html = tpl_la_ind_hood.render(
            **shared,
            hood=hood,
            nearby=nearby,
            seo=hood["seo"],
            canonical_path=f"industrial/la/{hood['slug']}.html",
            depth="../../",
        )
        (ind_la_dir / f"{hood['slug']}.html").write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/industrial/la/{hood['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
        })
    print(f"  [OK] industrial/la/*.html  ({la_industrial_count} submarket pages + 1 index)")

    # Retail index + per-corridor pages: /retail/la/*.html
    tpl_la_ret_index = env.get_template("la_retail_index.html")
    html = tpl_la_ret_index.render(
        **shared,
        hood_groups=la_retail_groups,
        hood_count=la_retail_count,
        seo={
            "title": "LA Retail Loans by Corridor | Commercial Lending Solutions",
            "meta_description": (
                f"Retail financing across {la_retail_count} Los Angeles corridors: Melrose, "
                "Abbot Kinney, Ventura Blvd, and more. Net-lease, bridge, SBA, and construction loans."
            ),
        },
        canonical_path="retail/la/index.html",
        depth="../../",
    )
    (ret_la_dir / "index.html").write_text(html, encoding="utf-8")
    page_count += 1
    sitemap_urls.append({
        "loc": f"{BASE_URL}/retail/la/index.html",
        "lastmod": TODAY, "changefreq": "weekly", "priority": "0.9",
    })
    tpl_la_ret_hood = env.get_template("la_retail_page.html")
    for hood in la_retail_hoods:
        nearby = la_retail.nearby_hoods(la_retail_hoods, hood["slug"], hood["region"])
        html = tpl_la_ret_hood.render(
            **shared,
            hood=hood,
            nearby=nearby,
            seo=hood["seo"],
            canonical_path=f"retail/la/{hood['slug']}.html",
            depth="../../",
        )
        (ret_la_dir / f"{hood['slug']}.html").write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/retail/la/{hood['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
        })
    print(f"  [OK] retail/la/*.html  ({la_retail_count} corridor pages + 1 index)")

    # ── 9b. State Hub Pages ─────────────────────────────────────────
    # /states/{slug}.html: one deep hub per state (all 50 + DC), the top
    # layer of the hub-and-spoke structure. Data: data/states.json.
    # Cities are derived from cities.json (state field), so newly added
    # cities appear on their state page automatically on the next regen.
    print("\n=== Generating State Pages ===")
    states = load_json("states.json")
    # Hand-curated internal-link boost: link each listed state's hub page to
    # its most important city's bridge-loans financing page (not just the
    # national hub), part of the 2026-07-13 bridge loan MSA internal-linking
    # pass. Only states with a real, verified gap are listed -- no guessing
    # a "top city" for the other 48 without a real signal to key off.
    state_featured_bridge_city = load_json("state_featured_bridge_city.json")
    tpl_state = env.get_template("state_page.html")
    states_dir = WEBSITE_DIR / "states"
    states_dir.mkdir(exist_ok=True)

    cities_by_state = {}
    for c in cities:
        cities_by_state.setdefault(c["state"], []).append(c)
    for _lst in cities_by_state.values():
        _lst.sort(key=lambda x: x["city"])

    states_by_region = {}
    for st in states:
        states_by_region.setdefault(region_for_state(st["abbr"]), []).append(st)

    for st in states:
        region = region_for_state(st["abbr"])
        st_cities = cities_by_state.get(st["abbr"], [])
        related = [s for s in states_by_region.get(region, [])
                   if s["slug"] != st["slug"]][:7]
        txns = filter_transactions(transactions, state=st["abbr"])
        html = tpl_state.render(
            **shared,
            state=st,
            state_cities=st_cities,
            related_states=related,
            transactions=txns,
            seo=st["seo"],
            canonical_path=f"states/{st['slug']}.html",
            depth="../",
            current_region=region,
            featured_bridge_city=state_featured_bridge_city.get(st["slug"]),
        )
        (states_dir / f"{st['slug']}.html").write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/states/{st['slug']}.html",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.8",
        })

    tpl_states_index = env.get_template("states_index.html")
    state_groups = []
    for r in REGION_ORDER:
        _sts = sorted(states_by_region.get(r, []), key=lambda s: s["name"])
        if not _sts:
            continue
        state_groups.append({
            "region": r,
            "blurb": REGION_DESCRIPTIONS.get(r, ""),
            "states": [{**s, "city_count": len(cities_by_state.get(s["abbr"], []))}
                       for s in _sts],
        })
    html = tpl_states_index.render(
        **shared,
        state_groups=state_groups,
        seo={"title": "Commercial Real Estate Loans by State | Commercial Lending Solutions",
             "meta_description": "Commercial real estate loans in all 50 states from $1M to $100M+. State-by-state foreclosure law, recording taxes, and lender coverage. Free quote from Commercial Lending Solutions."},
        canonical_path="states/",
        depth="../",
    )
    (states_dir / "index.html").write_text(html, encoding="utf-8")
    page_count += 1
    sitemap_urls.append({
        "loc": f"{BASE_URL}/states/",
        "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
    })
    print(f"  [OK] states/*.html  ({len(states)} state pages + 1 index)")

    # ── 9c. Glossary Pages ──────────────────────────────────────────
    # /glossary/{slug}.html: deep term pages (definition, formula, worked
    # example, lender-type usage, FAQs) + /glossary/ index grouped by
    # category. Data: data/glossary.json. DefinedTerm/DefinedTermSet schema.
    # GUARDED: data/glossary.json does not exist yet (glossary content is
    # work-in-progress). Without this guard, the content bot's scheduled
    # generate.py run crashes on load_json() and the whole regen (pages,
    # sitemaps, robots.txt) silently stops shipping. The footer link to
    # /glossary/ is gated on the same condition via shared["has_glossary"].
    if (DATA_DIR / "glossary.json").exists():
        print("\n=== Generating Glossary Pages ===")
        glossary = load_json("glossary.json")
        tpl_gterm = env.get_template("glossary_term.html")
        glossary_dir = WEBSITE_DIR / "glossary"
        glossary_dir.mkdir(exist_ok=True)

        _terms_by_slug = {t["slug"]: t for t in glossary}
        for t in glossary:
            related_entries = [_terms_by_slug[s] for s in t.get("related_terms", [])
                               if s in _terms_by_slug]
            html = tpl_gterm.render(
                **shared,
                term=t,
                related_term_entries=related_entries,
                seo=t["seo"],
                canonical_path=f"glossary/{t['slug']}.html",
                depth="../",
            )
            (glossary_dir / f"{t['slug']}.html").write_text(html, encoding="utf-8")
            page_count += 1
            sitemap_urls.append({
                "loc": f"{BASE_URL}/glossary/{t['slug']}.html",
                "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
            })

        tpl_gindex = env.get_template("glossary_index.html")
        _gcat_order = []
        for t in glossary:
            if t["category"] not in _gcat_order:
                _gcat_order.append(t["category"])
        term_groups = [{"category": c,
                        "terms": [t for t in glossary if t["category"] == c]}
                       for c in _gcat_order]
        html = tpl_gindex.render(
            **shared,
            all_terms=glossary,
            term_groups=term_groups,
            seo={"title": "Commercial Real Estate Finance Glossary | Commercial Lending Solutions",
                 "meta_description": "Every CRE finance term that changes your loan, explained by a working broker: definitions, formulas, worked examples, and what lenders actually require."},
            canonical_path="glossary/",
            depth="../",
        )
        (glossary_dir / "index.html").write_text(html, encoding="utf-8")
        page_count += 1
        sitemap_urls.append({
            "loc": f"{BASE_URL}/glossary/",
            "lastmod": TODAY, "changefreq": "monthly", "priority": "0.7",
        })
        print(f"  [OK] glossary/*.html  ({len(glossary)} term pages + 1 index)")
    else:
        print("\n=== Glossary Pages: SKIPPED (data/glossary.json not found — WIP) ===")

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
        "senior-living", "los-angeles", "retail",
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
        if path.startswith("states/"):
            return "states"
        if path.startswith("glossary/"):
            return "glossary"
        if path.startswith("los-angeles/"):
            return "los-angeles"
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
    # Only advertise sitemap-index.xml to crawlers. sitemap.xml (the flat
    # backwards-compat file above, kept only for internal IndexNow scripts)
    # used to be dual-registered here too, which had Google tracking it as
    # its own submission -- GSC flagged 6 persistent errors on the flat file
    # while the identical-content sitemap-index.xml showed 0 (2026-07-18
    # migration watch investigation). Dropping it from robots.txt stops new
    # discovery of it as a Google-facing sitemap; the file still exists on
    # disk for IndexNow.
    print("\n=== Generating robots.txt ===")
    robots = f"""User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap-index.xml
"""
    (WEBSITE_DIR / "robots.txt").write_text(robots, encoding="utf-8")
    print("  [OK] robots.txt")

    # ── 12b. Server-render rates.html table rows (AEO) ────────────────
    # Non-JS crawlers (GPTBot, PerplexityBot) never see the rate table
    # because it's populated client-side from tools/rates-data.json; this
    # bakes the same rows into the static tbody. The page JS re-renders
    # over them once loaded, so the interactive filters are unaffected.
    render_rates_table()

    # ── 13. Asset version stamping (cache-busting) ────────────────────
    # Runs LAST so every page written above (and every page written by
    # scripts outside this generator) leaves with ?v=<hash> js/css URLs.
    stamp_asset_versions()

    # ── 14. Dash scrub (self-healing no-dash guardrail) ───────────────
    # Trevor's strict no-em/en-dash rule. Sources (templates + data) are
    # kept dash-free, but this final pass guarantees no em/en dash ever
    # ships in generated OUTPUT even if a new source string slips one in
    # (the reason the June 2026 scrub silently regressed). Idempotent;
    # runs on every content-bot regen. See dash_scrub.py.
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from dash_scrub import scrub_tree as _scrub_dashes
    _df, _dd = _scrub_dashes(WEBSITE_DIR)
    print(f"  [dash-scrub] {_df} files cleaned, {_dd} dashes removed")

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  TOTAL PAGES GENERATED: {page_count}")
    print(f"  Sitemap URLs: {len(sitemap_urls)}")
    print(f"  Output: {WEBSITE_DIR}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    if "--stamp-assets-only" in sys.argv:
        # Cache-bust pass only: re-stamp ?v=<hash> on js/css references in
        # all on-disk HTML without regenerating any pages or sitemaps.
        stamp_asset_versions()
    else:
        main()
