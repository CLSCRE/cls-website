"""Related Articles blocks for every live blog post (audit row 10).

Why: the generator's old rule picked the first three same-category articles from articles.json, which
pointed at pruned posts (cards that resolved to the blog index) and sent every post to the same few
targets. 169 of 215 live posts are static HTML with no articles.json entry at all and had no related block.

What it does: reads the live blog sitemap, extracts title, description, category and date from each
post's HTML, scores topical similarity (TF-IDF cosine plus a small same-category bonus), and gives each
post RELATED_COUNT cards chosen to spread inbound links evenly (a load penalty stops a few posts hoarding
them) and to avoid stacking several posts from one weekly series. Writes the block into every post.

Idempotent: the block sits between <!-- RELATED ARTICLES --> and <!-- /RELATED ARTICLES -->. An old block
(ending at <!-- EXPLORE BY MARKET -->) is replaced; a post with none gets one before </main> (or <footer).

Usage: python _generator/related_posts.py [--dry-run] [--website DIR]
"""
import argparse
import html as htmllib
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RELATED_COUNT = 4
START = "<!-- RELATED ARTICLES -->"
END = "<!-- /RELATED ARTICLES -->"
EXPLORE = "<!-- EXPLORE BY MARKET -->"
STOP = set("""a an and are as at be by for from how in into is it its of on or that the this to vs with your you what when
which who why will can does do not no more most than then their they we our us new now per via about after before between
through over under up out all any each other such these those has have had was were been being if so also may must should
guide complete 2025 2026 2027 loan loans commercial real estate cre financing finance lender lenders""".split())
MONTHS = "january february march april may june july august september october november december".split()


def stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokens(text):
    out = []
    for w in re.findall(r"[a-z][a-z0-9\-]+", text.lower()):
        for part in w.split("-"):
            if len(part) >= 3 and part not in STOP and not part.isdigit():
                out.append(stem(part))
    return out


def series_key(slug):
    s = re.sub(r"-(" + "|".join(MONTHS) + r")-\d{1,2}(-\d{4})?$", "", slug)
    s = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", s)
    s = re.sub(r"-\d{4}$", "", s)
    return s


def meta(page_html):
    def g(rx):
        m = re.search(rx, page_html, re.S)
        return m.group(1).strip() if m else ""
    h1 = re.sub(r"<[^>]+>", "", g(r"<h1[^>]*>(.*?)</h1>"))
    desc = g(r'name="description" content="([^"]*)"')
    cat = g(r'property="article:section" content="([^"]*)"') or "Insights"
    dp = g(r'"datePublished":\s*"(\d{4}-\d{2}-\d{2})')
    pretty = ""
    if dp:
        d = datetime.strptime(dp, "%Y-%m-%d")
        pretty = f"{d.strftime('%B')} {d.day}, {d.year}"
    return h1, desc, cat, pretty, dp


def excerpt(desc, limit=185):
    d = htmllib.unescape(desc)
    if len(d) <= limit:
        return htmllib.escape(d, quote=False)
    cut = d[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return htmllib.escape(cut, quote=False) + "&hellip;"


def card(p):
    cat_slug = re.sub(r"[^a-z0-9]+", "-", p["cat"].lower()).strip("-")
    date = f"\n        <span>{p['date']}</span>" if p["date"] else ""
    return (
        f'    <a href="../blog/{p["slug"]}.html" class="blog-card reveal" data-cat="{cat_slug}">\n'
        f'      <div class="blog-card-category">{p["cat"]}</div>\n'
        f'      <h3 class="blog-card-title">{p["title"]}</h3>\n'
        f'      <p class="blog-card-excerpt">{excerpt(p["desc"])}</p>\n'
        f'      <div class="blog-card-meta">\n        <span>Trevor Damyan</span>{date}\n      </div>\n'
        f"    </a>\n"
    )


def block(cards):
    return (
        f"{START}\n<section class=\"content-section\">\n<div class=\"section-inner\">\n"
        f'  <h2 class="section-title reveal">Related Articles</h2>\n  <div class="blog-grid">\n'
        + "".join(cards)
        + f"  </div>\n</div>\n</section>\n{END}\n"
    )


def live_slugs(web):
    xml = (web / "sitemap-blog.xml").read_text(encoding="utf-8")
    out = []
    for u in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = re.search(r"/blog/([^/]+)\.html$", u)
        if m and m.group(1) != "index" and (web / "blog" / f"{m.group(1)}.html").exists():
            out.append(m.group(1))
    return sorted(set(out))


def choose(posts):
    df = Counter()
    for p in posts.values():
        for t in set(p["tok"]):
            df[t] += 1
    n = len(posts)
    vec = {}
    for s, p in posts.items():
        tf = Counter(p["tok"])
        v = {t: (1 + math.log(c)) * math.log(n / df[t]) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vec[s] = {t: x / norm for t, x in v.items()}

    def sim(a, b):
        va, vb = vec[a], vec[b]
        if len(va) > len(vb):
            va, vb = vb, va
        return sum(x * vb.get(t, 0.0) for t, x in va.items())

    load = defaultdict(int)
    picks = {}
    order = sorted(posts, key=lambda s: (posts[s]["inl"], s))  # least-linked posts choose first
    for s in order:
        cands = []
        for c in posts:
            if c == s:
                continue
            sc = sim(s, c) + (0.05 if posts[c]["cat"] == posts[s]["cat"] else 0.0)
            cands.append((sc, c))
        cands.sort(reverse=True)
        pool = cands[:90]
        chosen, used_series = [], {series_key(s)}
        # greedy: best adjusted score, penalizing posts that already received many related links
        while len(chosen) < RELATED_COUNT and pool:
            best = max(pool, key=lambda x: x[0] - 0.05 * load[x[1]])
            pool.remove(best)
            sk = series_key(best[1])
            if sk in used_series:
                continue
            chosen.append(best[1])
            used_series.add(sk)
        if len(chosen) < RELATED_COUNT:  # thin pool: fill from the rest of the ranking
            for sc, c in cands[90:]:
                if series_key(c) not in used_series:
                    chosen.append(c)
                    used_series.add(series_key(c))
                if len(chosen) >= RELATED_COUNT:
                    break
        for c in chosen:
            load[c] += 1
        picks[s] = chosen
    return picks, load


def run(web, dry_run=False):
    web = Path(web)
    slugs = live_slugs(web)
    posts = {}
    for s in slugs:
        t = (web / "blog" / f"{s}.html").read_text(encoding="utf-8-sig")
        if re.search(r'name="robots"[^>]*noindex', t[:6000], re.I):
            continue
        h1, desc, cat, pretty, dp = meta(t)
        if not h1:
            continue
        # inbound links today (any page), from the blog listing and elsewhere, used only to order choices
        posts[s] = {"slug": s, "title": h1, "desc": desc, "cat": cat, "date": pretty,
                    "tok": tokens(h1 + " " + htmllib.unescape(desc) + " " + s.replace("-", " ")), "inl": 0}
    picks, load = choose(posts)
    changed = 0
    for s, chosen in picks.items():
        path = web / "blog" / f"{s}.html"
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw[:4000]
        new_block = block([card(posts[c]) for c in chosen])
        if crlf:
            new_block = new_block.replace("\n", "\r\n")
        t = raw
        if END in t and START in t:
            t = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\r?\n?", lambda m: new_block, t, count=1, flags=re.S)
        elif START in t and EXPLORE in t:
            t = re.sub(re.escape(START) + r".*?(?=" + re.escape(EXPLORE) + ")", lambda m: new_block + ("\r\n" if crlf else "\n"), t, count=1, flags=re.S)
        elif START in t:  # old block with no EXPLORE marker after it: it is one section
            _s = t.index(START)
            _e = t.index('</section>', _s) + len('</section>')
            while t[_e:_e + 1] in ('\r', '\n'):
                _e += 1
            t = t[:_s] + new_block + t[_e:]
        elif EXPLORE in t:
            t = t.replace(EXPLORE, new_block + ("\r\n" if crlf else "\n") + EXPLORE, 1)
        elif "</main>" in t:
            t = t.replace("</main>", new_block + "</main>", 1)
        elif "<footer" in t:
            t = t.replace("<footer", new_block + "<footer", 1)
        else:
            continue
        if t != raw:
            changed += 1
            if not dry_run:
                path.write_bytes(t.encode("utf-8"))
    dist = Counter(load[s] for s in posts)
    print(f"posts {len(posts)}  blocks written {changed}  new inbound per post (n:count) {sorted(dist.items())}")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--website", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.website, a.dry_run)


if __name__ == "__main__":
    main()
