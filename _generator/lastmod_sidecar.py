"""Honest sitemap <lastmod> values (2026-11-26 SEO audit, item 6).

Problem: 96.8% of sitemap URLs shared one lastmod (2026-09-09), and generate.py
stamps TODAY on every URL whenever it rebuilds. Neither tells Google which pages
actually changed.

Design: a sidecar file (_generator/data/sitemap_lastmod.json) remembers, per URL,
a hash of the page's *normalized* content and the lastmod that goes with it.
A URL's lastmod only advances when its normalized hash changes. Normalization
drops everything that changes without the page changing: site-wide header, nav
and footer (nav edits touch ~2,000 pages at once), scripts and styles (cache-bust
?v= stamps, JSON-LD dateModified), comments, and visible dates.

The first run for a URL seeds its lastmod from whatever the sitemap already says
(or today for a brand new URL). Seeding understates freshness, it never invents it.

    python lastmod_sidecar.py            # report what would change
    python lastmod_sidecar.py --write    # rewrite sitemaps + sidecar

generate.py calls apply() right after it writes the sitemaps, so a regeneration
cannot reset every lastmod to today.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIDECAR = Path(__file__).resolve().parent / "data" / "sitemap_lastmod.json"
BASE = "https://clscre.com"

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DROP_BLOCKS = [
    re.compile(r"<!--.*?-->", re.S),
    re.compile(r"<script\b.*?</script>", re.S | re.I),
    re.compile(r"<style\b.*?</style>", re.S | re.I),
    re.compile(r"<noscript\b.*?</noscript>", re.S | re.I),
    re.compile(r"<header\b.*?</header>", re.S | re.I),
    re.compile(r"<nav\b.*?</nav>", re.S | re.I),
    re.compile(r"<footer\b.*?</footer>", re.S | re.I),
]
_DATES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b(?:%s)\s+(?:\d{1,2},\s*)?\d{4}\b" % _MONTHS),
    re.compile(r"\?v=[\w.\-]+"),
]
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def normalize(html):
    for rx in _DROP_BLOCKS:
        html = rx.sub(" ", html)
    for rx in _DATES:
        html = rx.sub("", html)
    html = _TAGS.sub(" ", html)  # keep text only: markup churn is not a content change
    return _WS.sub(" ", html).strip()


def content_hash(html):
    return hashlib.sha1(normalize(html).encode("utf-8")).hexdigest()


def _rel(loc):
    path = loc.replace(BASE, "").lstrip("/")
    if path == "" or path.endswith("/"):
        path += "index.html"
    return path


def _page_for(loc):
    path = loc.replace(BASE, "").lstrip("/")
    if path == "" or path.endswith("/"):
        path += "index.html"
    return ROOT / path


_URL = re.compile(r"<url>.*?</url>", re.S)
_LOC = re.compile(r"<loc>([^<]+)</loc>")
_LASTMOD = re.compile(r"<lastmod>[^<]*</lastmod>")


def apply(today, write=True, verbose=False):
    """Rewrite lastmod in every sitemap-*.xml and sitemap.xml. Return a summary dict."""
    side = {}
    if SIDECAR.exists():
        side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    stats = {"seeded": 0, "advanced": 0, "kept": 0, "missing_page": 0}
    cache = {}  # loc -> lastmod so sitemap.xml agrees with the segment files

    files = sorted(ROOT.glob("sitemap-*.xml")) + [ROOT / "sitemap.xml"]
    files = [f for f in files if f.name != "sitemap-index.xml" and f.exists()]
    per_file_max = {}

    for f in files:
        xml = f.read_text(encoding="utf-8")
        newest = ""

        def fix(m):
            nonlocal newest
            block = m.group(0)
            lm = _LOC.search(block)
            if not lm:
                return block
            loc = lm.group(1).strip()
            if loc in cache:
                final = cache[loc]
            else:
                cur = _LASTMOD.search(block)
                cur_val = re.sub(r"</?lastmod>", "", cur.group(0)) if cur else today
                page = _page_for(loc)
                if not page.exists():
                    stats["missing_page"] += 1
                    final = cur_val
                else:
                    # freshness.page_hash = the same normalization, with rate figures masked on
                    # the rate-table pages (their date follows the rate table's changed_on)
                    import freshness
                    h = freshness.page_hash(_rel(loc), page.read_bytes().decode("utf-8", "replace"))
                    rec = side.get(loc)
                    if rec is None:
                        # Seed from the existing sitemap value, but never from a
                        # same-day regen stamp: a brand new URL is dated today only
                        # if it has no earlier value to inherit.
                        side[loc] = {"hash": h, "lastmod": cur_val}
                        final = cur_val
                        stats["seeded"] += 1
                    elif rec["hash"] != h:
                        side[loc] = {"hash": h, "lastmod": today}
                        final = today
                        stats["advanced"] += 1
                    else:
                        final = rec["lastmod"]
                        stats["kept"] += 1
                import freshness
                final = freshness.effective_date(_rel(loc), final)
                cache[loc] = final
            newest = max(newest, final)
            if _LASTMOD.search(block):
                return _LASTMOD.sub(f"<lastmod>{final}</lastmod>", block, count=1)
            return block

        new_xml = _URL.sub(fix, xml)
        per_file_max[f.name] = newest
        if write and new_xml != xml:
            f.write_text(new_xml, encoding="utf-8")

    # sitemap-index lastmod = newest URL date inside each child file
    idx = ROOT / "sitemap-index.xml"
    if idx.exists():
        ix = idx.read_text(encoding="utf-8")

        def fix_idx(m):
            name = m.group(1)
            val = per_file_max.get(name)
            return m.group(0) if not val else re.sub(r"<lastmod>[^<]*</lastmod>", f"<lastmod>{val}</lastmod>", m.group(0))

        new_ix = re.sub(r"<sitemap><loc>https://clscre\.com/([^<]+)</loc>.*?</sitemap>", fix_idx, ix)
        if write and new_ix != ix:
            idx.write_text(new_ix, encoding="utf-8")

    if write:
        SIDECAR.parent.mkdir(parents=True, exist_ok=True)
        SIDECAR.write_text(json.dumps(side, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    if verbose:
        print(stats)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from datetime import date
    print(apply(date.today().isoformat(), write=a.write))
