"""Blog index and category listing pages, built from the posts that are actually live.

Problem (2026-11-26 GEO audit, row R27): the listing was built from all ~2,400
articles.json entries, nearly all of which the LA/California prune retired (410, 301
or noindex). The live /blog/ showed pagination "1 ... 99" with only page 99 present,
its category links 301'd, and 169 of the 215 live posts (case studies, guides, market
reports that never lived in articles.json) were not listed at all.

Rules now:
  * A post is listed only if its file is on disk, is not a redirect stub, is not
    flagged noindex, is not in redirect_map.json, noindex_paths.json or the cleanse
    kill list, and is in sitemap-blog.xml (or is an articles.json entry that passes
    the same file checks, so a brand new post is not delayed a build).
  * Cards come from articles.json when the slug is there, otherwise from the page's
    own <title>, meta description, datePublished and author.
  * Categories exist only if they hold at least one live post, so no category link
    can point at a page that is not written.

generate.py calls build() in section 5. To rebuild only the listing without a full
site regeneration (other sessions share the repo):

    python generate.py --blog-listing-only
"""
import html as _html
import json
import re
from datetime import datetime
from pathlib import Path

BLOG_PAGE_SIZE = 48
SUFFIXES = (" | Commercial Lending Solutions", " | CLS CRE")
_LISTING_PREFIXES = ("blog/page/", "blog/category/", "blog/pages/", "blog/topics/", "blog/index")


def _cat_slug(cat):
    return re.sub(r"[^a-z0-9]+", "-", cat.lower()).strip("-")


def _killed(data_dir):
    f = Path(data_dir) / "_cleanse_kill_list.txt"
    if not f.exists():
        return set()
    return {
        l.strip().lstrip("/")
        for l in f.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    }


def _sitemap_posts(website_dir):
    f = Path(website_dir) / "sitemap-blog.xml"
    if not f.exists():
        return []
    sm = f.read_text(encoding="utf-8")
    return [
        loc for loc in re.findall(r"<loc>https://clscre\.com/(blog/[^<]+\.html)</loc>", sm)
        if not loc.startswith(_LISTING_PREFIXES)
    ]


def _category_for(slug):
    if "case-study" in slug:
        return "Case Studies"
    if "rates" in slug:
        return "Rate Commentary"
    if slug.startswith(("market-perspective", "capital-markets-report", "cre-market-report")):
        return "Market Perspective"
    return "Guides"


def _clean(s):
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def _excerpt(desc, limit=190):
    d = _clean(desc)
    if len(d) <= limit:
        return d
    cut = d[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "..."


def _from_page(slug, page, fallback_date):
    t = page.read_bytes().decode("utf-8", "replace")
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    title = _clean(m.group(1)) if m else slug.replace("-", " ").title()
    for s in SUFFIXES:
        if title.endswith(s):
            title = title[: -len(s)]
    d = re.search(r'<meta name="description" content="([^"]*)"', t)
    pub = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', t) \
        or re.search(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', t)
    au = re.search(r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', t)
    date = pub.group(1) if pub else fallback_date
    return {
        "slug": slug,
        "title": title,
        "excerpt": _excerpt(d.group(1)) if d else "",
        "author": au.group(1) if au else "Commercial Lending Solutions",
        "date": date,
        "category": _category_for(slug),
        "tags": [],
        "type": "page",
    }


def live_posts(website_dir, data_dir, articles, redirect_paths, noindex_paths, today):
    """Every blog post that is live and indexable, newest first."""
    website_dir = Path(website_dir)
    killed = _killed(data_dir)
    by_slug = {a["slug"]: a for a in articles}
    candidates = {loc[len("blog/"):-len(".html")] for loc in _sitemap_posts(website_dir)}
    candidates |= set(by_slug)  # filtered below; new posts are not held back a build

    posts = []
    for slug in sorted(candidates):
        rel = f"blog/{slug}.html"
        page = website_dir / rel
        if slug == "case-studies" or not page.exists():
            continue  # case-studies.html is the hub with its own callout, not a card
        if rel in redirect_paths or rel in noindex_paths or rel in killed:
            continue
        head = page.read_bytes()[:8000].decode("utf-8", "replace")
        if 'http-equiv="refresh"' in head or re.search(
                r'name=["\']robots["\'][^>]*noindex', head, re.I):
            continue
        if slug in by_slug:
            a = dict(by_slug[slug])
        else:
            a = _from_page(slug, page, today)
        a["date_formatted"] = datetime.strptime(a["date"], "%Y-%m-%d").strftime("%B %d, %Y")
        posts.append(a)
    posts.sort(key=lambda a: (a["date"], a["title"].lower()), reverse=True)
    return posts


def _page_number_items(cur, total, href_for):
    """Windowed page-number list: 1 2 ... cur-1 cur cur+1 ... N-1 N."""
    nums = sorted(n for n in {1, 2, cur - 1, cur, cur + 1, total - 1, total} if 1 <= n <= total)
    items, prev = [], 0
    for n in nums:
        if n - prev > 1:
            items.append({"ellipsis": True})
        items.append({"num": n, "current": n == cur, "href": href_for(n)})
        prev = n
    return items


def build(env, shared, website_dir, base_url, today, posts, noindex_paths):
    """Write blog/index.html, blog/page/N.html and blog/category/*. Returns
    (pages_written, sitemap_url_dicts, written_paths)."""
    website_dir = Path(website_dir)
    tpl = env.get_template("blog_index.html")
    categories = sorted({a["category"] for a in posts})
    category_links = [
        {"name": c, "slug": _cat_slug(c), "href": f"blog/topics/{_cat_slug(c)}.html"}
        for c in categories
    ]
    written, sitemap, count = set(), [], 0

    def render_series(listing, *, href_for, out_path_for, canonical_for, depth_for,
                      seo_for, hero_for, active_category, active_category_slug, priority_for,
                      in_sitemap=True):
        nonlocal count
        total_pages = max(1, -(-len(listing) // BLOG_PAGE_SIZE))
        for n in range(1, total_pages + 1):
            chunk = listing[(n - 1) * BLOG_PAGE_SIZE: n * BLOG_PAGE_SIZE]
            hero = hero_for(n, total_pages)
            noindex = canonical_for(n) in noindex_paths
            html = tpl.render(
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
                total_articles=len(listing),
                page_start=(n - 1) * BLOG_PAGE_SIZE + 1,
                page_end=(n - 1) * BLOG_PAGE_SIZE + len(chunk),
                rel_prev=f"{base_url}/{canonical_for(n - 1)}" if n > 1 else None,
                rel_next=f"{base_url}/{canonical_for(n + 1)}" if n < total_pages else None,
                hero_title=hero["title"],
                hero_intro=hero["intro"],
                seo=seo_for(n, total_pages),
                canonical_path=canonical_for(n),
                depth=depth_for(n),
                noindex=noindex,
            )
            out = out_path_for(n)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            written.add(out)
            count += 1
            if not noindex and in_sitemap:
                sitemap.append({
                    "loc": f"{base_url}/{canonical_for(n)}",
                    "lastmod": today,
                    "changefreq": "weekly" if n == 1 else "monthly",
                    "priority": priority_for(n),
                })
        return total_pages

    def main_href(n):
        return "blog/index.html" if n == 1 else f"blog/pages/{n}.html"

    def main_seo(n, total):
        if n == 1:
            return {
                "title": "CRE Insights & Market Analysis | Commercial Lending Solutions",
                "meta_description": "Expert insights on commercial real estate financing, interest rates, market trends, and investment strategies from Commercial Lending Solutions.",
            }
        return {
            "title": f"CRE Insights & Market Analysis | Page {n} of {total} | Commercial Lending Solutions",
            "meta_description": f"Commercial real estate financing insights from Commercial Lending Solutions. Page {n} of {total}, newest articles first.",
        }

    def main_hero(n, total):
        intro = ("Expert analysis on CRE financing, market trends, investment "
                 "strategies, and industry news from the CLS CRE team.")
        if n > 1:
            intro += f" Page {n} of {total}."
        return {"title": "Commercial Real Estate Insights", "intro": intro}

    main_pages = render_series(
        posts,
        href_for=main_href,
        out_path_for=lambda n: website_dir / "blog" / ("index.html" if n == 1 else f"pages/{n}.html"),
        canonical_for=lambda n: "blog/" if n == 1 else f"blog/pages/{n}.html",
        depth_for=lambda n: "../" if n == 1 else "../../",
        seo_for=main_seo,
        hero_for=main_hero,
        active_category=None,
        active_category_slug=None,
        priority_for=lambda n: "0.8" if n == 1 else "0.3",
    )
    print(f"  [OK] blog/index.html + blog/pages/*.html  ({len(posts)} live posts across {main_pages} pages)")

    cat_pages = 0
    for cl in category_links:
        name, slug = cl["name"], cl["slug"]
        cat_posts = [a for a in posts if a["category"] == name]
        count_c = len(cat_posts)
        h1 = name if " " in name else f"{name} Articles"

        def href(n, s=slug):
            return f"blog/topics/{s}.html" if n == 1 else f"blog/topics/{s}-{n}.html"

        def seo(n, total, cat=name, c=count_c):
            if n == 1:
                return {
                    "title": f"{cat} | CRE Insights | Commercial Lending Solutions",
                    "meta_description": f"All {c} {cat} articles from Commercial Lending Solutions. Commercial real estate financing analysis, newest first.",
                }
            return {
                "title": f"{cat} | Page {n} of {total} | Commercial Lending Solutions",
                "meta_description": f"{cat} articles from Commercial Lending Solutions. Page {n} of {total}, newest articles first.",
            }

        def hero(n, total, h=h1, cat=name, c=count_c):
            intro = f"All {c} {cat} articles from the CLS CRE team, newest first."
            if n > 1:
                intro += f" Page {n} of {total}."
            return {"title": h, "intro": intro}

        cat_pages += render_series(
            cat_posts,
            href_for=href,
            out_path_for=lambda n, s=slug: website_dir / "blog" / "topics" / (f"{s}.html" if n == 1 else f"{s}-{n}.html"),
            canonical_for=href,
            depth_for=lambda n: "../../",
            seo_for=seo,
            hero_for=hero,
            active_category=name,
            active_category_slug=slug,
            priority_for=lambda n: "0.4" if n == 1 else "0.3",
            in_sitemap=False,  # small topic hubs stay crawlable but are not submitted
        )
    print(f"  [OK] blog/topics/*.html  ({len(category_links)} categories across {cat_pages} pages)")

    # blog/page/N.html and blog/category/*.html are retired paths: the edge 301s
    # them to /blog/ and generate.py suppresses writes to them, so the listing
    # lives at blog/pages/ and blog/topics/ instead. Any leftover real listing in
    # the old folders (blog/page/99.html) becomes a soft-301 stub to /blog/ so it
    # stops advertising retired posts. Stubs already there are left untouched.
    stub = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Redirecting</title>'
            '<meta name="robots" content="noindex,follow">'
            f'<link rel="canonical" href="{base_url}/blog/">'
            f'<meta http-equiv="refresh" content="0; url={base_url}/blog/">'
            f'<script>location.replace("{base_url}/blog/")</script></head>'
            '<body style="font-family:system-ui,sans-serif;padding:2rem">'
            f'<p>This page has moved. If you are not redirected automatically, '
            f'<a href="{base_url}/blog/">continue here</a>.</p></body></html>')
    for d in (website_dir / "blog" / "page", website_dir / "blog" / "category"):
        if d.exists():
            for old in d.glob("*.html"):
                head = old.read_bytes()[:4000].decode("utf-8", "replace")
                if 'http-equiv="refresh"' not in head:
                    old.write_text(stub, encoding="utf-8")
                    print(f"  [stub] {old.relative_to(website_dir).as_posix()} now redirects to /blog/")
    # Remove stale pages inside the new folders (the post count shrank or a
    # category disappeared).
    for d in (website_dir / "blog" / "pages", website_dir / "blog" / "topics"):
        if d.exists():
            for old in d.glob("*.html"):
                if old not in written:
                    old.unlink()
                    print(f"  [cleanup] Removed stale blog listing {old.name}")
    return count, sitemap, written


def sync_sitemaps(website_dir, base_url, listing_urls, tpl_sitemap=None):
    """For a listing-only rebuild: swap the blog listing entries inside the existing
    sitemap-blog.xml and the flat sitemap.xml, so the sitemap never advertises a
    listing page that no longer exists (blog/page/99.html). Text surgery on the
    <url> blocks only: every other entry keeps its bytes, lastmod and layout."""
    website_dir = Path(website_dir)

    def is_listing(loc):
        p = loc.replace(base_url, "").lstrip("/")
        return p == "blog/" or p.startswith(_LISTING_PREFIXES)

    for name in ("sitemap-blog.xml", "sitemap.xml"):
        f = website_dir / name
        if not f.exists():
            continue
        xml = f.read_bytes().decode("utf-8")
        nl = chr(13) + chr(10) if chr(13) in xml else chr(10)
        blocks = list(re.finditer(r"<url>.*?</url>", xml, re.S))
        if not blocks:
            continue

        def block(u):
            return nl.join([
                "<url>",
                f"    <loc>{u['loc']}</loc>",
                f"    <lastmod>{u['lastmod']}</lastmod>",
                f"    <changefreq>{u['changefreq']}</changefreq>",
                f"    <priority>{u['priority']}</priority>",
                "  </url>",
            ])

        out, pos, inserted, removed = [], 0, False, 0
        for m in blocks:
            loc = re.search(r"<loc>(.*?)</loc>", m.group(0)).group(1).strip()
            out.append(xml[pos:m.start()])
            pos = m.end()
            if is_listing(loc):
                removed += 1
                if not inserted:
                    out.append("".join(block(u) if k == 0 else (xml[m.end():m.end()] + block(u))
                                       for k, u in enumerate(listing_urls)))
                    inserted = True
            else:
                out.append(m.group(0))
        out.append(xml[pos:])
        new = "".join(out)
        f.write_bytes(new.encode("utf-8"))
        print(f"  [sitemap] {name}: {removed} listing entries replaced by {len(listing_urls)}")
