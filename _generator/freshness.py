"""Honest page dates: a page's visible "Updated" date and its JSON-LD dateModified /
lastReviewed say when the page's CONTENT last changed, not when the generator last ran
(2026-11-26 GEO fix tracker, "Replace fake freshness dates").

Source of truth: the per-page sidecar _generator/data/sitemap_lastmod.json (see
lastmod_sidecar.py). Each sitemap URL stores {"hash": normalized-content hash,
"lastmod": date}. The date advances only when the hash changes; normalization drops nav,
footer, scripts, styles, comments and every date, so a site-wide nav edit or a regen does
not move it. The sidecar was seeded from git history (seed_page_dates_from_git.py), so each
date is the day the page's text last really changed.

Rate pages (the pages fed by the rate table) show the later of that date and the rate
table's own changed_on date. Their hash masks rate figures, so a rate-only move shows up
through changed_on, not as a content edit.

This is the one place page dates get written, as a pass AFTER every page is on disk (so it
does not matter which writer made the page, or in what order):

    python freshness.py            # report pages whose dates disagree with the sidecar
    python freshness.py --write    # fix them (generate.py runs this after the sitemap pass)

Rewrite rules live in page_dates.py (JSON-LD dateModified and lastReviewed, Updated
bylines, Last updated text). datePublished, "As of <month>" market sentences and
"Published:" lines are never touched. dateModified is never earlier than datePublished
and never later than today.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import lastmod_sidecar as _sc
import rate_table
from page_dates import rewrite_dates

ROOT = _sc.ROOT
BASE = _sc.BASE
SIDECAR = _sc.SIDECAR

# Pages whose headline figures come from the rate table (cmr_rate_sync.py writes them).
RATE_PAGES = {
    "financing/commercial-mortgage-rates.html",
    "financing/permanent-loans-los-angeles.html",
    "financing/agency-loan-rates.html",
    "financing/cmbs-loan-rates.html",
    "financing/hud-fha-loan-rates.html",
    "financing/life-company-loan-rates.html",
    "financing/bridge-loan-rates.html",
    "financing/construction-loan-rates.html",
    "rates.html",
}

_RATE_FIG = re.compile(r"\b\d{1,2}\.\d{2}\s?%")


def rel_of(loc: str) -> str:
    path = loc.replace(BASE, "").lstrip("/")
    if path == "" or path.endswith("/"):
        path += "index.html"
    return path


def page_hash(rel: str, html: str) -> str:
    """Content hash used by the sidecar. Rate pages mask percent figures so a rate-only
    move is not counted as a content edit (their date follows the rate table)."""
    norm = _sc.normalize(html)
    if rel in RATE_PAGES:
        norm = _RATE_FIG.sub("R", norm)
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def effective_date(rel: str, sidecar_lastmod: str) -> str:
    """The date a page should show: the sidecar content date, or for rate pages the later
    of that and the rate table's changed_on."""
    if rel in RATE_PAGES:
        try:
            return max(sidecar_lastmod, rate_table.changed_on())
        except Exception:
            return sidecar_lastmod
    return sidecar_lastmod


def load_sidecar() -> dict:
    return json.loads(SIDECAR.read_text(encoding="utf-8")) if SIDECAR.exists() else {}


def apply(today: str, write: bool = True, verbose: bool = False) -> dict:
    """Stamp every sitemap page with its sidecar date. Returns counts."""
    side = load_sidecar()
    stats = {"pages": 0, "rewritten": 0, "unchanged": 0, "no_date": 0, "missing": 0}
    for loc, rec in side.items():
        rel = rel_of(loc)
        p = ROOT / rel
        if not p.exists():
            stats["missing"] += 1
            continue
        if not rec.get("lastmod"):
            stats["no_date"] += 1
            continue
        stats["pages"] += 1
        iso = effective_date(rel, rec["lastmod"])
        raw = p.read_bytes().decode("utf-8", "replace")
        new = rewrite_dates(raw, iso, today=today)
        if new != raw:
            stats["rewritten"] += 1
            if write:
                p.write_bytes(new.encode("utf-8"))
        else:
            stats["unchanged"] += 1
    if verbose:
        print(stats)
    return stats


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    print(apply(date.today().isoformat(), write=a.write))
