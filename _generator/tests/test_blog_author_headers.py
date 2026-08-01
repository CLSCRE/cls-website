from pathlib import Path
import sys

from bs4 import BeautifulSoup

GENERATOR_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = GENERATOR_DIR.parent
sys.path.insert(0, str(GENERATOR_DIR))

from migrate_blog_author_headers import migrate_html  # noqa: E402


LEGACY_HEADER = """<!doctype html><html><head>
<meta property="article:author" content="Trevor Damyan">
</head><body><article class="blog-article"><div class="article-header">
<div class="blog-card-category">Case Study</div>
<h1>A Long Case Study Title</h1>
<div class="page-byline"><span>Deal arranged and written by</span> <a href="../about/trevor-damyan.html">Trevor Damyan</a><span>, Commercial Mortgage Broker</span></div>
<div class="article-meta"><span>By Trevor Damyan</span><span>&middot;</span><time datetime="2026-04-03">April 03, 2026</time><span>&middot;</span><span>Construction Loan</span></div>
</div><div class="author-bio-box">old duplicate author box</div></article></body></html>"""


def test_migration_replaces_repeated_byline_with_one_complete_author_profile():
    migrated, changed = migrate_html(LEGACY_HEADER)
    soup = BeautifulSoup(migrated, "html.parser")
    header = soup.select_one(".article-header")

    assert changed
    assert len(header.select(".article-author-profile")) == 1
    assert header.select_one('.article-author-profile img[src="../images/trevor-damyan.webp"]')
    assert header.select_one('a[rel="author"][href="../about/trevor-damyan.html"]')
    assert "Founder & Principal Broker" in header.get_text(" ", strip=True)
    assert "CA DRE #02244836" in header.get_text(" ", strip=True)
    assert "CBRE" in header.get_text(" ", strip=True)
    assert "$1B+" in header.get_text(" ", strip=True)
    assert header.get_text(" ", strip=True).count("Trevor Damyan") == 1
    assert not header.select(".page-byline")
    assert not soup.select(".author-bio-box")


def test_migration_preserves_article_date_and_category_metadata():
    migrated, _ = migrate_html(LEGACY_HEADER)
    soup = BeautifulSoup(migrated, "html.parser")
    meta = soup.select_one(".article-header .article-meta")

    assert meta.select_one('time[datetime="2026-04-03"]')
    assert "Construction Loan" in meta.get_text(" ", strip=True)
    assert "Trevor Damyan" not in meta.get_text(" ", strip=True)
    assert not meta.get_text(" ", strip=True).startswith("·")


def test_migration_is_idempotent():
    first, changed = migrate_html(LEGACY_HEADER)
    second, changed_again = migrate_html(first)

    assert changed
    assert not changed_again
    assert second == first


def test_migration_cache_busts_the_shared_author_profile_styles():
    legacy = LEGACY_HEADER.replace(
        "</head>",
        '<link rel="stylesheet" href="../css/pages.min.css?v=old-version"></head>',
    )

    migrated, _ = migrate_html(legacy)

    assert "pages.min.css?v=2524254017" in migrated
    assert "old-version" not in migrated


def test_all_standard_trevor_blog_headers_use_the_author_profile():
    failures = []
    checked = 0
    for path in sorted((REPO_ROOT / "blog").glob("*.html")):
        html = path.read_text(encoding="utf-8", errors="ignore")
        if "Trevor Damyan" not in html or "article:author" not in html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        header = h1.find_parent(class_="article-header") if h1 else None
        if not header:
            continue
        checked += 1
        profiles = header.select(".article-author-profile")
        profile_text = " ".join(profile.get_text(" ", strip=True) for profile in profiles)
        if (
            len(profiles) != 1
            or profile_text.count("Trevor Damyan") != 1
            or "CA DRE #02244836" not in profile_text
            or header.select_one(".page-byline")
            or "Trevor Damyan" in " ".join(x.get_text(" ", strip=True) for x in header.select(".article-meta"))
        ):
            failures.append(path.name)

    assert checked >= 5_000
    assert not failures, f"Nonconforming author headers ({len(failures)}): {failures[:20]}"


def test_generator_template_uses_header_profile_without_footer_duplicate():
    template = (GENERATOR_DIR / "templates" / "blog_article.html").read_text(encoding="utf-8")

    assert template.count('class="article-author-profile"') == 1
    assert 'class="author-bio-box' not in template
    assert "CA DRE #02244836" in template
