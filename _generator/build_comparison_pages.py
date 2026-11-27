"""Build or refresh specific comparison pages without touching any other page.

Added 2026-11-26 (Peec gap, comparison slice). The original comparison page script is gone and the
live pages carry site-wide post-passes (nav, cache stamps, consent) that a fresh template render
does not, so this builder renders ONLY the page content from comparison_page.html and splices it
into the live page (or, for a new slug, into a sibling live page used as the skeleton).

Data: _generator/data/comparisons.json (original 60 entries, never edited here) plus
_generator/data/comparisons_extra.json. An entry in the extra file with an existing slug OVERRIDES
that entry; a new slug adds a page. The related-comparison cards list only pages that exist on disk,
so the pruned SBA and DSCR entries in comparisons.json never reappear.

Spliced: <title>, meta description, canonical, og:/twitter: tags, the Article/FAQPage/BreadcrumbList/
WebPage JSON-LD, and everything between <main id="main-content"> and </main>.

    python _generator/build_comparison_pages.py slug-one slug-two
    python _generator/build_comparison_pages.py --all-extra
Idempotent. Run from the website folder.
"""
from __future__ import annotations

import html as _html
import json
import re
import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

GEN = Path(__file__).resolve().parent
WEB = GEN.parent
CMP_DIR = WEB / "comparisons"
SKELETON_FALLBACK = "cmbs-vs-life-company-office-retail"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def load_entries():
    base = json.loads((GEN / "data" / "comparisons.json").read_text(encoding="utf-8"))
    extra_path = GEN / "data" / "comparisons_extra.json"
    extra = json.loads(extra_path.read_text(encoding="utf-8")) if extra_path.exists() else []
    merged = {e["slug"]: e for e in base}
    for e in extra:
        merged[e["slug"]] = e
    return list(merged.values()), [e["slug"] for e in extra]


def exists(slug):
    return (CMP_DIR / f"{slug}.html").exists()


def render(entries, cmp, today, building):
    env = Environment(loader=FileSystemLoader(str(GEN / "templates")), autoescape=False)
    cmp = dict(cmp)
    # Drop related cards that point at files that do not exist (pruned pages).
    cmp["related_links"] = [l for l in cmp.get("related_links", [])
                            if (WEB / l["href"].split("#")[0]).exists()]
    live = [e for e in entries if exists(e["slug"]) or e["slug"] in building]
    d = date.fromisoformat(today)
    return env.get_template("comparison_page.html").render(
        cmp=cmp, all_comparisons=live, depth="../", seo=cmp["seo"],
        canonical_path=f"comparisons/{cmp['slug']}.html",
        current_date_human=f"{MONTHS[d.month - 1]} {d.year}", today=today, body_class="")


def esc(s):
    return _html.escape(s, quote=True)


def splice(skeleton, rendered, cmp):
    out = skeleton
    url = f"https://clscre.com/comparisons/{cmp['slug']}.html"
    title, desc = esc(cmp["seo"]["title"]), esc(cmp["seo"]["meta_description"])
    subs = [
        (r"<title>.*?</title>", f"<title>{title}</title>"),
        (r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{desc}">'),
        (r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{url}">'),
        (r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{title}">'),
        (r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{desc}">'),
        (r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{url}">'),
        (r'<meta name="twitter:title" content="[^"]*">', f'<meta name="twitter:title" content="{title}">'),
        (r'<meta name="twitter:description" content="[^"]*">', f'<meta name="twitter:description" content="{desc}">'),
    ]
    for pat, rep in subs:
        out, n = re.subn(pat, lambda m, r=rep: r, out, count=1, flags=re.S)
        assert n == 1, pat
    # JSON-LD: replace the Article, FAQPage, BreadcrumbList and WebPage scripts, keep Organization/WebSite.
    ld = re.compile(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', re.S)
    new_ld = {}
    for m in ld.finditer(rendered):
        t = re.search(r'"@type":"(\w+)"', m.group(1)).group(1)
        new_ld[t] = m.group(0)

    def swap(m):
        t = re.search(r'"@type":"(\w+)"', m.group(1)).group(1)
        return new_ld.get(t, m.group(0))
    out = ld.sub(swap, out)
    # main content
    mi, mj = out.index('<main id="main-content">'), out.index("</main>")
    ri, rj = rendered.index('<main id="main-content">'), rendered.index("</main>")
    out = out[:mi] + rendered[ri:rj] + out[mj:]
    return out


def main(argv):
    entries, extra_slugs = load_entries()
    slugs = extra_slugs if "--all-extra" in argv else [a for a in argv if not a.startswith("--")]
    if not slugs:
        print(__doc__)
        return 1
    today = date.today().isoformat()
    by_slug = {e["slug"]: e for e in entries}
    for slug in slugs:
        cmp = by_slug[slug]
        rendered = render(entries, cmp, today, set(slugs))
        skel_path = CMP_DIR / f"{slug if exists(slug) else SKELETON_FALLBACK}.html"
        raw = skel_path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        skeleton = raw.decode("utf-8-sig")
        page = splice(skeleton, rendered, cmp)
        (CMP_DIR / f"{slug}.html").write_bytes((b"\xef\xbb\xbf" if bom else b"") + page.encode("utf-8"))
        print("built", slug)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
