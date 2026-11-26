"""The single rate table for clscre.com (added 2026-11-26, GEO fix tracker item "Rate pages").

One file, _generator/data/rate_table.json, holds every headline rate range the site
publishes. scripts/cmr_rate_sync.py (the 2-hourly rate bot) is the only writer. Every
generator module and every hand-built rate page reads it, so no page can fall back to
a stale hard-coded range.

File shape:
    {
      "as_of": "2026-11-24",         # market data date the ranges were computed from
      "changed_on": "2026-11-24",    # the day the ranges last actually changed (drives
                                     #   rate-page "Updated" dates and dateModified)
      "ranges": {"life": ["6.10", "6.70"], "cmbs": [...], "agency": [...], "hud": [...],
                 "bank": [...], "permanent": [...],  # permanent = widest permanent span
                 "bridge": [...], "construction": [...], "dscr": [...], "sba504": [...],
                 "all": [...]}      # all programs: permanent low to bridge/construction high
    }

Data files (loan_types.json, faqs.json, articles.json, templates) carry tokens instead of
numbers:  {rt:permanent} -> "5.91% to 8.16%",  {rt:permanent|dash} -> "5.91% - 8.16%",
{rt:permanent.low} -> "5.91%", {rt:permanent.high} -> "8.16%". resolve() expands them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TABLE_PATH = Path(__file__).resolve().parent / "data" / "rate_table.json"

TOKEN = re.compile(r"\{rt:([a-z0-9]+)(?:\.(low|high))?(?:\|(dash))?\}")

# loan_types.json slug -> table key. Slugs not listed keep their own range from
# loan_types.json (products the table does not price: mezzanine, preferred equity,
# hard money, fix and flip, stated income, CPACE, net lease).
SLUG_KEY = {
    "permanent-loans": "permanent",
    "commercial-mortgage-loans": "all",
    "multifamily-loans": "permanent",
    "construction-loans": "construction",
    "bridge-loans": "bridge",
    "sba-loans": "sba504",
    "specialty": "all",
    "agency-loans": "agency",
    "hud-fha-loans": "hud",
    "cmbs-loans": "cmbs",
    "life-company-loans": "life",
    "dscr-loans": "dscr",
    "portfolio-loans": "bank",
    "bridge-to-perm-loans": "bridge",
    "acquisition-bridge-loans": "bridge",
    "value-add-bridge-loans": "bridge",
    "1031-exchange-bridge-loans": "bridge",
    "multifamily-bridge-loans": "bridge",
    "industrial-bridge-loans": "bridge",
    "office-bridge-loans": "bridge",
    "retail-bridge-loans": "bridge",
    "mixed-use-bridge-loans": "bridge",
    "office-conversion-loans": "bridge",
    "multifamily-construction-loans": "construction",
    "build-to-rent-loans": "construction",
    "construction-to-perm-loans": "construction",
    "industrial-construction-loans": "construction",
    "land-loans": "bridge",
    "self-storage-financing": "permanent",
    "hotel-motel-financing": "all",
    "student-housing-loans": "permanent",
    "senior-housing-financing": "permanent",
    "medical-office-financing": "permanent",
    "sale-leaseback-financing": "permanent",
    "owner-occupied-commercial": "permanent",
}

_cache = None


def load(path: Path | None = None) -> dict:
    global _cache
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if _cache is None:
        _cache = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    return _cache


def reset_cache():
    global _cache
    _cache = None


def _two(x) -> str:
    return f"{float(x):.2f}"


def span(key: str) -> tuple[str, str]:
    """(low, high) as '5.91' strings for a table key."""
    lo, hi = load()["ranges"][key]
    return _two(lo), _two(hi)


def pct_span(key: str) -> tuple[str, str]:
    lo, hi = span(key)
    return f"{lo}%", f"{hi}%"


def text(key: str, sep: str = "to") -> str:
    lo, hi = pct_span(key)
    return f"{lo} {sep} {hi}"


def for_slug(slug: str):
    """(low, high) with percent signs for a loan_types slug, or None if the table
    does not price that product."""
    key = SLUG_KEY.get(slug)
    return pct_span(key) if key else None


def all_programs() -> tuple[str, str]:
    return pct_span("all")


def changed_on() -> str:
    return load()["changed_on"]


def as_of() -> str:
    return load()["as_of"]


def _sub(m: re.Match) -> str:
    key, part, dash = m.group(1), m.group(2), m.group(3)
    lo, hi = pct_span(key)
    if part == "low":
        return lo
    if part == "high":
        return hi
    return f"{lo} - {hi}" if dash else f"{lo} to {hi}"


def resolve_text(s: str) -> str:
    return TOKEN.sub(_sub, s) if "{rt:" in s else s


def resolve(obj):
    """Expand rate tokens in every string of a loaded JSON structure (in place for
    lists and dicts, returns the structure)."""
    if isinstance(obj, str):
        return resolve_text(obj)
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            obj[i] = resolve(v)
        return obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = resolve(v)
        return obj
    return obj


def apply_to_loan_types(loans: list) -> list:
    """Overlay table ranges on loan_types entries: rate_low/rate_high and the first
    range in key_features.rates (separator style kept)."""
    rx = re.compile(r"(\d+(?:\.\d+)?%)(\s*(?:-|to)\s*)(\d+(?:\.\d+)?%)")
    for lt in loans:
        got = for_slug(lt.get("slug", ""))
        if not got:
            continue
        lo, hi = got
        lt["rate_low"], lt["rate_high"] = lo, hi
        kf = lt.get("key_features")
        if isinstance(kf, dict) and isinstance(kf.get("rates"), str):
            # Spread-based strings ("SOFR + 225 to 600 bps") carry no percent range and stay.
            if rx.search(kf["rates"]):
                kf["rates"] = rx.sub(lambda m: f"{lo}{m.group(2)}{hi}", kf["rates"], count=1)
    return loans


def resolve_data(name: str, data):
    """What every generator loader runs on a data file after json.load: expand rate tokens,
    and for loan_types.json overlay the table's ranges."""
    resolve(data)
    if name == "loan_types.json":
        apply_to_loan_types(data)
    return data


# tools/rates-data.json feeds rates.html (server-rendered rows and the page's JS table).
RATES_DATA_MAP = {"Bridge": "bridge", "Permanent": "permanent", "Construction": "construction",
                  "SBA 504": "sba504", "CMBS": "cmbs", "Agency (Fannie/Freddie)": "agency",
                  "HUD/FHA 223(f)": "hud", "Life Company": "life"}


def sync_rates_data(path: Path, table: dict | None = None, write: bool = True) -> bool:
    """Set rateMin/rateMax on every table-priced product in rates-data.json, editing only the
    numbers (the file is hand formatted with CRLF line ends). True if it changed."""
    table = table or load()
    old = Path(path).read_bytes().decode("utf-8")
    new = old
    for product, key in RATES_DATA_MAP.items():
        lo, hi = (float(x) for x in table["ranges"][key])
        pat = re.compile(r'("product":\s*"' + re.escape(product) + r'"[^{}]*?"rateMin":\s*)[\d.]+([^{}]*?"rateMax":\s*)[\d.]+')
        new, n = pat.subn(lambda m: f"{m.group(1)}{lo:.2f}{m.group(2)}{hi:.2f}", new, count=1)
        if n != 1:
            raise ValueError(f"rates-data.json: product not found: {product}")
    if new == old:
        return False
    if write:
        Path(path).write_bytes(new.encode("utf-8"))
    return True
