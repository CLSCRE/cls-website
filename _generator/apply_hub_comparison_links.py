#!/usr/bin/env python3
"""Add a "Compare your options" block to existing financing hub pages.

Idempotent (marker <!-- cls-hub-compare -->). Mirrors templates/_hub_compare.html
so a later full generate.py run produces the same block. Needed because
render_financing_hubs.py does not reproduce the live pages (post-passes), so
re-rendering hubs just to add links would drift the rest of each page.

Data: data/hub_comparison_links.json  {financing slug: [{slug, title}, ...]}
Usage: python apply_hub_comparison_links.py [--dry-run]
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEBSITE = HERE.parent
MARK = "<!-- cls-hub-compare -->"

# Insert before the first of these anchors that exists in the page.
ANCHORS = [
    '<section class="pf-section pf-paper" id="markets">',   # conversion hubs
    '<section class="pf-section">\n    <div class="pf-wrap pf-faq-layout">',  # life company hub
]


def block(rows, depth="../"):
    cards = "\n".join(
        f'      <a href="{depth}comparisons/{r["slug"]}.html" class="cross-link-card reveal">'
        f'<div class="cl-title">{html.escape(r["title"], quote=False)}</div>'
        f'<div class="cl-sub">Side-by-side guide</div></a>'
        for r in rows
    )
    return (
        f"{MARK}\n"
        '<section class="pf-section" id="compare">\n'
        '  <div class="pf-wrap">\n'
        '    <div class="pf-deal-heading">\n'
        "      <div>\n"
        '        <div class="pf-kicker">Compare your options</div>\n'
        "        <h2>Side by side: how to choose between structures.</h2>\n"
        "      </div>\n"
        f'      <a class="pf-text-link" href="{depth}comparisons/index.html">All comparisons &rarr;</a>\n'
        "    </div>\n"
        '    <div class="cross-link-grid">\n'
        f"{cards}\n"
        "    </div>\n"
        "  </div>\n"
        "</section>\n"
        "<!-- /cls-hub-compare -->\n\n"
    )


def main():
    dry = "--dry-run" in sys.argv
    data = json.loads((HERE / "data" / "hub_comparison_links.json").read_text(encoding="utf-8"))
    for slug, rows in data.items():
        path = WEBSITE / "financing" / f"{slug}.html"
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        crlf = "\r\n" in text
        t = text.replace("\r\n", "\n")
        if MARK in t:
            print(f"skip (already has block): {slug}")
            continue
        for a in ANCHORS:
            if t.count(a) == 1:
                t = t.replace(a, block(rows) + a)
                break
        else:
            print(f"NO ANCHOR: {slug}")
            continue
        if crlf:
            t = t.replace("\n", "\r\n")
        if not dry:
            path.write_bytes(t.encode("utf-8"))
        print(f"{'would add' if dry else 'added'}: {slug} ({len(rows)} links)")


if __name__ == "__main__":
    main()
