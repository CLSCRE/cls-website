"""Give every indexable blog post at least one real link from /blog/ (2026-11-26 audit).

The chronological index paginates 4,700 mostly retired articles, and its pages 2 to 98
no longer exist, so the only way to reach most of the 215 sitemap posts was a deep link
from some other page (77 had none at all). This adds an "All guides and analysis"
section to blog/index.html listing every post in sitemap-blog.xml, alphabetically.

Idempotent: the block lives between ALL-GUIDES markers and is replaced on every run.
generate.py calls inject() right after it writes the blog index; run by hand with:

    python blog_all_guides.py            # report
    python blog_all_guides.py --write
"""
import argparse
import html as _html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = "<!-- ALL-GUIDES:START -->"
END = "<!-- ALL-GUIDES:END -->"
SUFFIXES = (" | Commercial Lending Solutions", " | CLS CRE")


def _guides():
    sm = (ROOT / "sitemap-blog.xml").read_text(encoding="utf-8")
    out = []
    for loc in re.findall(r"<loc>https://clscre\.com/(blog/[^<]+\.html)</loc>", sm):
        if loc == "blog/index.html" or loc.startswith("blog/page/") or loc.startswith("blog/category/"):
            continue
        p = ROOT / loc
        if not p.exists():
            continue
        m = re.search(r"<title>(.*?)</title>", p.read_bytes().decode("utf-8", "replace"), re.S)
        if not m:
            continue
        t = _html.unescape(m.group(1)).strip()
        for s in SUFFIXES:
            if t.endswith(s):
                t = t[: -len(s)]
        out.append((t, loc))
    out.sort(key=lambda x: x[0].lower())
    return out


def block():
    items = "\n".join(
        f'    <li><a href="../{loc}">{_html.escape(t)}</a></li>' for t, loc in _guides()
    )
    return (
        f"{START}\n"
        '<section class="content-section" id="all-guides">\n'
        '<div class="section-inner">\n'
        "  <h2>All guides and analysis</h2>\n"
        '  <p class="blog-count">Every guide, case study and market analysis from Commercial Lending Solutions, A to Z.</p>\n'
        '  <ul class="all-guides-list" style="columns:2 320px;column-gap:32px;list-style:none;padding:0;margin:0;line-height:1.5">\n'
        f"{items}\n"
        "  </ul>\n"
        "</div>\n"
        "</section>\n"
        f"{END}\n"
    )


def inject(write=True):
    p = ROOT / "blog" / "index.html"
    s = p.read_bytes().decode("utf-8")
    b = block()
    if START in s and END in s:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\r?\n?", lambda _m: b, s, count=1, flags=re.S)
    else:
        anchor = "<!-- CTA -->"
        i = s.find(anchor, s.find("<!-- PAGINATION -->"))
        if i < 0:
            raise RuntimeError("blog/index.html: CTA anchor not found")
        new = s[:i] + b + "\n" + s[i:]
    n = b.count("<li>")
    if write and new != s:
        p.write_bytes(new.encode("utf-8"))
    return n, new != s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    print(inject(write=a.write))
