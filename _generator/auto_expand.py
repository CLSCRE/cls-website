#!/usr/bin/env python3
"""
CLS CRE — Autonomous Content Expansion Engine

Runs on every GitHub Actions trigger (every 8 hours). Each run:
  1. Pops BATCH_SIZE cities from expansion_queue.json into cities.json
  2. If any new city is tier1, adds it to MARKET_REPORT_CITIES in
     generate_articles.py and inserts a stub into article_city_data.json
  3. Regenerates all pages (generate.py which calls generate_articles.py)
  4. Submits new URLs to IndexNow
  5. On Mondays: runs generate_weekly_rates.py via Anthropic API
  6. Updates generation_progress.json

Run location: website/ directory (script is in website/_generator/)
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import os
import re
import subprocess
import datetime
import requests
from pathlib import Path

# ── Paths (relative to website/ where GitHub Actions runs from) ──────────
SCRIPT_DIR = Path(__file__).resolve().parent          # website/_generator/
WEBSITE_DIR = SCRIPT_DIR.parent                       # website/
DATA_DIR = SCRIPT_DIR / "data"

CITIES_FILE       = DATA_DIR / "cities.json"
QUEUE_FILE        = DATA_DIR / "expansion_queue.json"
PROGRESS_FILE     = DATA_DIR / "generation_progress.json"
ARTICLE_DATA_FILE = DATA_DIR / "article_city_data.json"
GENERATE_PY       = SCRIPT_DIR / "generate.py"
GENERATE_ARTICLES = SCRIPT_DIR / "generate_articles.py"
WEEKLY_RATES_PY   = WEBSITE_DIR.parent / "scripts" / "generate_weekly_rates.py"
SITEMAP_FILE      = WEBSITE_DIR / "sitemap.xml"

INDEXNOW_KEY  = "a1494521ad404bb6af8988ffd5a6dd71"
INDEXNOW_HOST = "clscre.com"
BASE_URL      = "https://clscre.com"


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict | list, indent: int = 2) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    print(f"  saved {path.name}")


def run(cmd: list[str], cwd: Path = SCRIPT_DIR) -> int:
    """Run a subprocess, stream output, return returncode."""
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=False)
    return result.returncode


# ────────────────────────────────────────────────────────────────────────────
# Step 1 — Pop cities from queue into cities.json
# ────────────────────────────────────────────────────────────────────────────

def pop_cities_from_queue(batch_size: int) -> list[dict]:
    """Pop up to batch_size cities from the pending queue, append to cities.json."""
    queue = load_json(QUEUE_FILE)
    cities = load_json(CITIES_FILE)

    existing_slugs = {c["slug"] for c in cities}
    pending = queue.get("cities_pending", [])

    if not pending:
        print("Queue exhausted — no new cities to add this run.")
        return []

    # Pop from front of queue
    batch = []
    remaining = []
    added = 0
    for city in pending:
        if added < batch_size and city["slug"] not in existing_slugs:
            batch.append(city)
            added += 1
        else:
            remaining.append(city)

    if not batch:
        print("No new cities found in queue (all may already exist).")
        return []

    # Append to cities.json — keep only the fields generate.py expects
    for city in batch:
        entry = {
            "slug":          city["slug"],
            "city":          city["city"],
            "state":         city["state"],
            "metro":         city["metro"],
            "context":       city["context"],
            "neighborhoods": city["neighborhoods"],
        }
        cities.append(entry)
        print(f"  + {city['city']}, {city['state']}")

    save_json(CITIES_FILE, cities)

    # Update queue state
    done = queue.get("cities_done", [])
    for city in batch:
        done.append({"slug": city["slug"], "city": city["city"], "added": datetime.date.today().isoformat()})

    queue["cities_pending"]  = remaining
    queue["cities_done"]     = done
    queue["last_run"]        = datetime.datetime.utcnow().isoformat() + "Z"
    queue["total_pages_added"] = queue.get("total_pages_added", 0) + len(batch) * 12  # ~12 pages/city
    queue["runs_completed"]  = queue.get("runs_completed", 0) + 1
    save_json(QUEUE_FILE, queue)

    return batch


# ────────────────────────────────────────────────────────────────────────────
# Step 2 — Wire tier1 cities into generate_articles.py + article_city_data.json
# ────────────────────────────────────────────────────────────────────────────

def add_tier1_city_to_articles(city: dict) -> None:
    """
    For a new tier1 city:
      - Insert its slug into MARKET_REPORT_CITIES and ALL_CITIES in generate_articles.py
      - Add a stub entry to article_city_data.json
    """
    slug = city["slug"]
    city_name = city["city"]
    state = city["state"]

    # --- generate_articles.py patch ---
    src = GENERATE_ARTICLES.read_text(encoding="utf-8")

    # Find MARKET_REPORT_CITIES list and append slug if not already present
    for list_name in ("MARKET_REPORT_CITIES", "ALL_CITIES"):
        pattern = rf'({list_name}\s*=\s*\[)(.*?)(\])'
        match = re.search(pattern, src, re.DOTALL)
        if match and f'"{slug}"' not in match.group(2):
            existing_entries = match.group(2)
            # Append before closing bracket
            new_entries = existing_entries.rstrip() + f'\n    "{slug}",\n'
            src = src[:match.start(2)] + new_entries + src[match.end(2):]
            print(f"  patched {list_name} += {slug}")

    GENERATE_ARTICLES.write_text(src, encoding="utf-8")

    # --- article_city_data.json stub ---
    article_data = load_json(ARTICLE_DATA_FILE)
    if slug not in article_data:
        article_data[slug] = _build_article_city_stub(city)
        save_json(ARTICLE_DATA_FILE, article_data, indent=2)
        print(f"  article_city_data stub created for {city_name}")


def _build_article_city_stub(city: dict) -> dict:
    """Build a minimal article_city_data entry from queue city data."""
    city_name = city["city"]
    state     = city["state"]
    context   = city.get("context", "")
    neighborhoods = city.get("neighborhoods", [])

    # Derive sensible defaults from the context description
    top_subs = ", ".join(neighborhoods[:4]) if neighborhoods else f"Downtown {city_name}"

    return {
        "city":  city_name,
        "state": state,
        "stats": {
            "multifamily_vacancy":   "5.8%",
            "industrial_vacancy":    "5.2%",
            "office_vacancy":        "14.5%",
            "retail_vacancy":        "6.8%",
            "multifamily_cap_rate":  "5.50%-6.25%",
            "industrial_cap_rate":   "5.25%-6.00%",
            "office_cap_rate":       "7.00%-8.00%",
            "retail_cap_rate":       "6.25%-7.25%",
            "rent_growth":           "3.2%",
            "job_growth":            "1.6%",
            "population_growth":     "0.9%",
            "median_asking_rent":    "$1,450",
            "major_employers":       "government, healthcare, education, manufacturing, logistics",
            "top_submarkets":        top_subs,
            "mixed_use_vacancy":     "8.5%",
            "mixed_use_cap_rate":    "6.00%-7.00%",
            "hospitality_vacancy":   "24.0%",
            "hospitality_cap_rate":  "8.00%-9.50%",
        },
        "market_report": {
            "overview":     context,
            "multifamily":  (
                f"{city_name}'s multifamily market reflects the metro's growth trajectory, "
                "with demand driven by in-migration and a limited housing supply pipeline. "
                "Investors are active across value-add Class B/C product and new Class A development."
            ),
            "industrial":   (
                f"Industrial fundamentals in {city_name} are supported by regional distribution "
                "demand, proximity to major transportation corridors, and steady e-commerce growth. "
                "Vacancy has remained below the national average with rental rate increases year-over-year."
            ),
            "office_retail": (
                f"The {city_name} office market shows bifurcated performance between suburban flex "
                "product and downtown Class A towers. Retail remains resilient in dense neighborhood "
                "corridors with strong foot traffic and limited new supply."
            ),
            "financing":    (
                f"Lender appetite in {city_name} is healthy across multifamily and industrial "
                "asset classes. Agency execution is competitive for stabilized apartments, while "
                "regional banks and credit unions are active in smaller commercial transactions."
            ),
            "outlook":      (
                f"{city_name} offers a compelling risk-adjusted opportunity for commercial real "
                "estate investors in 2026. The market's diversified economic base and steady "
                "population growth provide durable demand drivers across property types."
            ),
        },
        "loan_context": {
            "bridge":       (
                f"Bridge lending in {city_name} is most active for value-add multifamily and "
                "transitional office repositioning. Debt funds and regional lenders compete for "
                "deals in the $2M-$20M range with 12-36 month terms."
            ),
            "permanent":    (
                f"Permanent financing in {city_name} benefits from strong agency execution on "
                "multifamily and competitive life company pricing on industrial. Stabilized "
                "assets with strong cash flow command spreads near the tight end of national ranges."
            ),
            "construction": (
                f"Construction lending in {city_name} is driven by multifamily ground-up and "
                "industrial build-to-suit activity. Regional banks are active for projects under "
                "$15M while national debt funds and CMBS lenders cover larger deals."
            ),
            "sba":          (
                f"SBA lending is highly active in {city_name} for owner-occupied commercial "
                "properties, particularly medical offices, manufacturing facilities, and retail "
                "buildings where the 90% LTV financing gives owner-users a significant advantage."
            ),
            "mezzanine":    (
                f"Mezzanine and preferred equity in {city_name} bridge the gap for sponsors "
                "acquiring larger value-add assets where senior debt falls short of required "
                "proceeds. The market sees regular activity in the $3M-$25M subordinate capital range."
            ),
            "specialty":    (
                f"Specialty financing in {city_name} covers the market's niche asset classes "
                "including self-storage, mobile home parks, hospitality, and mixed-use projects. "
                "Specialized lenders with local market knowledge are essential for these transactions."
            ),
        },
        "property_context": {
            "multifamily":   (
                f"Multifamily investment in {city_name} spans garden-style suburban complexes "
                "and urban infill apartment communities. Value-add operators find strong "
                "opportunity in the market's aging Class B/C stock with room for rent growth."
            ),
            "industrial":    (
                f"Industrial properties in {city_name} benefit from the market's position as "
                "a regional distribution hub. Warehouse, flex industrial, and last-mile "
                "fulfillment facilities attract strong tenant demand and investor interest."
            ),
            "office":        (
                f"The office market in {city_name} is navigating post-pandemic normalization "
                "with suburban Class B flex product outperforming downtown Class A towers. "
                "Medical office and government-leased buildings offer stable cash flow."
            ),
            "retail":        (
                f"Retail in {city_name} is led by grocery-anchored neighborhood centers and "
                "essential service corridors with high traffic and strong tenant retention. "
                "Regional malls face headwinds but power centers remain resilient."
            ),
            "mixed_use":     (
                f"Mixed-use development in {city_name} is concentrated in walkable downtown "
                "districts and transit-adjacent neighborhoods where residential demand supports "
                "ground-floor retail viability and long-term value creation."
            ),
            "hospitality":   (
                f"The hospitality market in {city_name} serves regional business travel, "
                "leisure tourism, and convention demand. Extended-stay and select-service "
                "hotels offer the most attractive risk-adjusted returns in the current cycle."
            ),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Step 3 — Run generators
# ────────────────────────────────────────────────────────────────────────────

def run_generators() -> bool:
    """Run generate.py (which internally calls generate_articles.py). Returns success."""
    rc = run([sys.executable, str(GENERATE_PY)], cwd=SCRIPT_DIR)
    if rc != 0:
        print(f"ERROR: generate.py exited with code {rc}")
        return False
    return True


# ────────────────────────────────────────────────────────────────────────────
# Step 4 — IndexNow submission
# ────────────────────────────────────────────────────────────────────────────

def submit_indexnow(new_city_slugs: list[str]) -> None:
    """Submit new city URLs to IndexNow.

    Reads loan_types.json + property_types.json so the URL list stays in sync
    when new loan programs or property types are added. URL patterns match
    what generate.py actually produces (see docs/SEO_ARCHITECTURE.md).
    """
    if not new_city_slugs:
        print("No new city URLs to submit to IndexNow.")
        return

    # Read current loan + property type slugs from the data files
    # (was previously hardcoded — drift caused new loan/property pages to
    # never be pinged to IndexNow when the schema was expanded).
    loan_type_slugs     = [lt["slug"] for lt in load_json(DATA_DIR / "loan_types.json")]
    property_type_slugs = [pt["slug"] for pt in load_json(DATA_DIR / "property_types.json")]

    urls = []
    for city_slug in new_city_slugs:
        # City × loan pages: /financing/{loan-slug}-{city-slug}.html
        for lt_slug in loan_type_slugs:
            urls.append(f"{BASE_URL}/financing/{lt_slug}-{city_slug}.html")
        # City × property pages: /property/{prop-slug}-{city-slug}.html
        for pt_slug in property_type_slugs:
            urls.append(f"{BASE_URL}/property/{pt_slug}-{city_slug}.html")
        # Market index: /markets/{city-slug}/ (directory index, not .html)
        urls.append(f"{BASE_URL}/markets/{city_slug}/")

    print(f"  Submitting {len(urls)} URLs ({len(loan_type_slugs)} loan + "
          f"{len(property_type_slugs)} property + 1 market index per city × "
          f"{len(new_city_slugs)} new cities)")

    # Batch into groups of 100
    batches = [urls[i:i+100] for i in range(0, len(urls), 100)]
    total_submitted = 0

    for i, batch in enumerate(batches):
        payload = {
            "host":    INDEXNOW_HOST,
            "key":     INDEXNOW_KEY,
            "keyLocation": f"{BASE_URL}/{INDEXNOW_KEY}.txt",
            "urlList": batch,
        }
        try:
            resp = requests.post(
                "https://api.indexnow.org/indexnow",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            print(f"  IndexNow batch {i+1}/{len(batches)}: HTTP {resp.status_code} ({len(batch)} URLs)")
            if resp.status_code in (200, 202):
                total_submitted += len(batch)
        except Exception as e:
            print(f"  IndexNow batch {i+1} failed: {e}")

    print(f"  Total submitted to IndexNow: {total_submitted}")


# ────────────────────────────────────────────────────────────────────────────
# Step 5 — Weekly rates (Mondays only)
# ────────────────────────────────────────────────────────────────────────────

def maybe_run_weekly_rates() -> bool:
    """Run generate_weekly_rates.py if today is Monday and the script exists."""
    today = datetime.date.today()
    if today.weekday() != 0:  # 0 = Monday
        print(f"Skipping weekly rates (today is {today.strftime('%A')}, not Monday).")
        return False

    if not WEEKLY_RATES_PY.exists():
        print(f"Weekly rates script not found at {WEEKLY_RATES_PY}")
        return False

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set — skipping weekly rates.")
        return False

    print("\nIt's Monday — running weekly rates generator...")
    rc = run(
        [sys.executable, str(WEEKLY_RATES_PY)],
        cwd=WEBSITE_DIR.parent,  # SEO Programmatic/ root
    )
    if rc != 0:
        print(f"WARNING: generate_weekly_rates.py exited with code {rc}")
        return False

    return True


# ────────────────────────────────────────────────────────────────────────────
# Step 6 — Update generation_progress.json
# ────────────────────────────────────────────────────────────────────────────

def update_progress(new_cities: list[dict], weekly_rates_ran: bool) -> None:
    progress = load_json(PROGRESS_FILE) if PROGRESS_FILE.exists() else {}

    # Count current cities
    cities = load_json(CITIES_FILE)
    tier1_slugs = _get_tier1_slugs()

    progress["cities_in_system"]    = len(cities)
    progress["tier1_cities"]        = sum(1 for c in cities if c["slug"] in tier1_slugs)
    progress["last_run"]            = datetime.datetime.utcnow().isoformat() + "Z"
    progress["runs_completed"]      = progress.get("runs_completed", 0) + 1
    progress["cities_added_this_run"] = len(new_cities)

    if weekly_rates_ran:
        progress["weekly_rates_generated"] = progress.get("weekly_rates_generated", 0) + 1

    # Estimate page count
    n = len(cities)
    progress["total_pages_estimated"] = (
        n * 9    # city × loan type
        + n * 6  # city × property type
        + n * 6  # submarket pages (avg 6 neighborhoods × city)
        + 27     # tier1 market reports
        + 12     # hub pages
        + 20     # hand-written blog articles
    )

    save_json(PROGRESS_FILE, progress)


def _get_tier1_slugs() -> set[str]:
    """Read MARKET_REPORT_CITIES from generate_articles.py at runtime."""
    src = GENERATE_ARTICLES.read_text(encoding="utf-8")
    match = re.search(r'MARKET_REPORT_CITIES\s*=\s*\[(.*?)\]', src, re.DOTALL)
    if not match:
        return set()
    return set(re.findall(r'"([^"]+)"', match.group(1)))


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"CLS CRE Content Expansion Engine — {datetime.datetime.utcnow().isoformat()}Z")
    print("=" * 60)

    batch_size = int(os.environ.get("BATCH_SIZE", "3"))
    print(f"\nBatch size: {batch_size}")

    # ── Step 1: Pop cities ──────────────────────────────────────────────
    print("\n[1/6] Popping cities from expansion queue...")
    new_cities = pop_cities_from_queue(batch_size)
    new_slugs  = [c["slug"] for c in new_cities]

    # ── Step 2: Wire tier1 cities into article generator ────────────────
    tier1_cities = [c for c in new_cities if c.get("tier1", False)]
    if tier1_cities:
        print(f"\n[2/6] Adding {len(tier1_cities)} tier1 cities to article system...")
        for city in tier1_cities:
            add_tier1_city_to_articles(city)
    else:
        print("\n[2/6] No tier1 cities in this batch — skipping article system update.")

    # ── Step 3: Regenerate all pages ────────────────────────────────────
    print("\n[3/6] Running page generators...")
    gen_ok = run_generators()
    if not gen_ok:
        print("ERROR: Page generation failed. Aborting.")
        sys.exit(1)

    # ── Step 4: IndexNow submission ──────────────────────────────────────
    print("\n[4/6] Submitting new URLs to IndexNow...")
    submit_indexnow(new_slugs)

    # ── Step 5: Weekly rates ─────────────────────────────────────────────
    print("\n[5/6] Checking weekly rates schedule...")
    weekly_ran = maybe_run_weekly_rates()

    # ── Step 6: Update progress tracker ─────────────────────────────────
    print("\n[6/6] Updating generation progress...")
    update_progress(new_cities, weekly_ran)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    cities_total = len(load_json(CITIES_FILE))
    print(f"Run complete.")
    print(f"  New cities added:  {len(new_cities)}")
    print(f"  Cities in system:  {cities_total}")
    print(f"  Weekly rates:      {'yes' if weekly_ran else 'no'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
