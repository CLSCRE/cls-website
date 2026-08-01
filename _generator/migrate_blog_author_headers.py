"""Normalize Trevor Damyan author headers across static blog articles.

The migration intentionally performs narrow string edits so thousands of generated
HTML files do not receive unrelated parser/reformatting churn.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


AUTHOR_PROFILE = """
<div class="article-author-profile">
  <a class="article-author-photo" href="../about/trevor-damyan.html" rel="author" aria-label="View Trevor Damyan's profile">
    <img src="../images/trevor-damyan.webp" alt="Trevor Damyan, Founder and Principal Broker at Commercial Lending Solutions" width="72" height="72" loading="eager" decoding="async">
  </a>
  <div class="article-author-details">
    <div class="article-author-identity">
      <a class="article-author-name" href="../about/trevor-damyan.html" rel="author">Trevor Damyan</a>
      <span class="article-author-role">Founder &amp; Principal Broker</span>
    </div>
    <div class="article-author-license">CA DRE #02244836</div>
    <p class="article-author-summary">Former CBRE and Marcus &amp; Millichap Capital Corporation. $1B+ in closed commercial real estate financing across bridge, construction, permanent, and structured debt.</p>
  </div>
</div>""".strip()

PAGES_CSS_VERSION = "2524254017"

_TAG_RE_TEMPLATE = r"<{tag}\b[^>]*>|</{tag}\s*>"


def _class_pattern(class_name: str) -> re.Pattern[str]:
    return re.compile(
        rf'<(?P<tag>[a-zA-Z][\w:-]*)\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'])[^>]*>',
        re.IGNORECASE,
    )


def _remove_balanced_element(html: str, class_name: str) -> tuple[str, bool]:
    """Remove every element carrying class_name without reserializing the page."""
    changed = False
    search_from = 0
    opener_re = _class_pattern(class_name)
    while True:
        opener = opener_re.search(html, search_from)
        if not opener:
            break
        tag = opener.group("tag")
        tag_re = re.compile(_TAG_RE_TEMPLATE.format(tag=re.escape(tag)), re.IGNORECASE)
        depth = 0
        end = None
        for match in tag_re.finditer(html, opener.start()):
            if match.group(0).lstrip().startswith("</"):
                depth -= 1
                if depth == 0:
                    end = match.end()
                    break
            elif not match.group(0).rstrip().endswith("/>"):
                depth += 1
        if end is None:
            search_from = opener.end()
            continue
        while end < len(html) and html[end] in " \t":
            end += 1
        if end < len(html) and html[end] == "\r":
            end += 1
        if end < len(html) and html[end] == "\n":
            end += 1
        html = html[: opener.start()] + html[end:]
        changed = True
        search_from = opener.start()
    return html, changed


def _remove_legacy_author_from_meta(html: str) -> tuple[str, bool]:
    before = html
    # Generated pages: <span class="article-author">By <a ...>Trevor...</a></span>
    # Legacy case studies: <span>By Trevor Damyan</span>
    author_span = re.compile(
        r'<span\b[^>]*>\s*By\s*(?:<a\b[^>]*>\s*)?Trevor\s+Damyan\s*(?:</a>\s*)?</span>'
        r'\s*(?:<span\b[^>]*>\s*(?:&middot;|&#183;|·|•)\s*</span>\s*)?',
        re.IGNORECASE,
    )
    html = author_span.sub("", html)
    return html, html != before


def migrate_html(html: str) -> tuple[str, bool]:
    """Return (normalized_html, changed) for one static blog article."""
    if "Trevor Damyan" not in html or "article:author" not in html:
        return html, False
    header = _class_pattern("article-header").search(html)
    if not header:
        return html, False

    changed = False
    html, removed = _remove_balanced_element(html, "page-byline")
    changed |= removed
    html, removed = _remove_balanced_element(html, "author-bio-box")
    changed |= removed
    html, removed = _remove_legacy_author_from_meta(html)
    changed |= removed

    if "article-author-profile" not in html:
        # Re-find after removals because source offsets changed. Insert after the
        # article header's H1, never after an unrelated page heading.
        header = _class_pattern("article-header").search(html)
        h1 = re.search(r"<h1\b[^>]*>.*?</h1>", html[header.end() :], re.IGNORECASE | re.DOTALL)
        if not h1:
            return html, changed
        insert_at = header.end() + h1.end()
        html = html[:insert_at] + "\n" + AUTHOR_PROFILE + html[insert_at:]
        changed = True

    versioned_html, substitutions = re.subn(
        r"pages\.min\.css(?:\?v=[^\"']*)?",
        f"pages.min.css?v={PAGES_CSS_VERSION}",
        html,
    )
    if substitutions and versioned_html != html:
        html = versioned_html
        changed = True

    return html, changed


def migrate_directory(blog_dir: Path, *, check: bool = False) -> tuple[int, list[Path]]:
    changed_paths: list[Path] = []
    checked = 0
    for path in sorted(blog_dir.glob("*.html")):
        original = path.read_text(encoding="utf-8", errors="ignore")
        migrated, changed = migrate_html(original)
        if not changed:
            continue
        checked += 1
        changed_paths.append(path)
        if not check:
            path.write_text(migrated, encoding="utf-8", newline="")
    return checked, changed_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blog_dir", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "blog")
    parser.add_argument("--check", action="store_true", help="Report files that still require migration without writing them")
    args = parser.parse_args()
    count, paths = migrate_directory(args.blog_dir, check=args.check)
    verb = "need migration" if args.check else "migrated"
    print(f"{count} blog files {verb}")
    for path in paths[:20]:
        print(path)
    if len(paths) > 20:
        print(f"... and {len(paths) - 20} more")
    return 1 if args.check and paths else 0


if __name__ == "__main__":
    raise SystemExit(main())
