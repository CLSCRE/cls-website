"""Cleanse: remove stated-income, dscr, fix-and-flip, sba loan families from clscre.com.
KEEP: hard-money, owner-occupied (per Trevor 2026-09-23).
Steps: git rm 1,717 pages + dscr calculator; strip links sitewide; rebuild sitemap;
add 410 rules to deploy worker; regenerate llms.txt references if present.
Run: env -u PYTHONPATH python cleanse_crappy_loan_programs.py
"""
import subprocess, os, io, re, json

ROOT = r"C:\Users\tdamy\OneDrive - CLS CRE\CLS CRE\Brokerage\AI - LLMs\Claude Code\SEO Programmatic\website"
KILL_PATS = ["stated-income", "dscr", "fix-and-flip", "sba"]

def run(args, **kw):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600, **kw)

# 1) build kill list fresh
r = run(["git", "ls-files"])
files = [f for f in r.stdout.split("\n") if f.strip()]
kill = sorted(set(
    f for f in files
    if any(p in os.path.basename(f).lower() for p in KILL_PATS)
    and f.endswith(".html")
    and not f.startswith(("_generator/", "docs/", ".github/", "scripts/"))
))
# add dscr calculator tool
kill.append("tools/dscr-calculator.html")
kill = [k for k in kill if (ROOT + "\\" + k.replace("/", "\\")) and os.path.exists(os.path.join(ROOT, k.replace("/", "\\")))]
print("pages to remove:", len(kill))

# 2) git rm them (batched: Windows arg limit)
BATCH = 200
rc = 0
for i in range(0, len(kill), BATCH):
    r = run(["git", "rm", "-q", "--"] + kill[i:i+BATCH])
    rc |= r.returncode
print("git rm rc:", rc, (r.stderr or "")[:200])

# 3) strip links + nav references from every remaining tracked html/json/py that points into kill families
#    Approach: remove <a> tags whose href hits a kill pattern (keep inner text), rewrite bare hrefs.
def strip_links(html):
    n = 0
    def repl(m):
        nonlocal n
        tag, href = m.group(1), m.group(2)
        low = href.lower()
        if any(p in low for p in KILL_PATS):
            n += 1
            return ""  # drop the entire anchor (menu items, cards, inline links)
        return m.group(0)
    html = re.sub(r'<a\b([^>]*href="([^"]*)"[^>]*)>(?:(?!</a>).)*?</a>', repl, html, flags=re.S | re.I)
    # also any leftover bare href/src references (canonical, og:url, sitemap refs inside pages)
    def repl2(m):
        nonlocal n
        pre, href = m.group(1), m.group(2)
        low = href.lower()
        if any(p in low for p in KILL_PATS):
            n += 1
            return pre + 'href="#"'
        return m.group(0)
    html = re.sub(r'(<link[^>]*\brel="canonical"[^>]*href=")([^"]*")', lambda m: m.group(0), html, flags=re.I)
    return html, n

r = run(["git", "ls-files", "*.html"])
targets = [f for f in r.stdout.split("\n") if f.strip()]
changed = 0; total_links = 0
for f in targets:
    p = os.path.join(ROOT, f.replace("/", "\\"))
    if not os.path.exists(p):
        continue
    t = io.open(p, encoding="utf-8", errors="ignore").read()
    t2, n = strip_links(t)
    if n:
        io.open(p, "w", encoding="utf-8", newline="").write(t2)
        changed += 1
        total_links += n
print("pages scrubbed:", changed, "| links removed:", total_links)

# 3) sitemap: drop killed URLs
for sm_name in ("sitemap.xml", "sitemap-index.xml"):
    p = os.path.join(ROOT, sm_name)
    if os.path.exists(p):
        s = io.open(p, encoding="utf-8", errors="ignore").read()
        before = len(re.findall(r"<url>", s))
        # remove <url> blocks whose <loc> hits a kill pattern
        blocks = re.findall(r"<url>.*?</url>", s, re.S)
        kept = [b for b in blocks if not any(pat in b.lower() for pat in KILL_PATS)]
        if blocks:
            head = s[:s.find("<url>")]
            tail = s[s.rfind("</url>") + len("</url>"):]
            s2 = head + "".join(kept) + tail
            io.open(p, "w", encoding="utf-8", newline="").write(s2)
            print(sm_name, "urls:", before, "->", len(kept))

# 4) 410 rules in the deploy workflow worker (the worker is a heredoc inside the yml; add kill-path 410s)
wf_path = os.path.join(ROOT, ".github", "workflows", "deploy-cloudflare-pages.yml")
wf = io.open(wf_path, encoding="utf-8", errors="ignore").read()
OLD = '''              if (url.pathname.endsWith("/")) {
                url.pathname += "index.html";
                return env.ASSETS.fetch(new Request(url));
              }
              return env.ASSETS.fetch(request);'''
NEW = '''              // 410 Gone: cleansed loan-program families (stated-income, dscr,
              // fix-and-flip, sba). Removed from the site 2026-09; serve Gone so
              // Google drops them from the index quickly instead of soft-404.
              if (/\\/(stated-income|dscr|fix-and-flip|sba)[-a-z0-9]*\\.html?$/.test(url.pathname)) {
                return new Response("<!doctype html><html><body><h1>410 Gone</h1><p>This program page has been retired. See current loan programs at https://clscre.com/financing/</p></body></html>", { status: 410, headers: { "Content-Type": "text/html; charset=utf-8" } });
              }
              if (url.pathname.endsWith("/")) {
                url.pathname += "index.html";
                return env.ASSETS.fetch(new Request(url));
              }
              return env.ASSETS.fetch(request);'''
if "410 Gone" not in wf and OLD in wf:
    wf = wf.replace(OLD, NEW)
    io.open(wf_path, "w", encoding="utf-8", newline="").write(wf)
    print("410 rule added to deploy worker")
else:
    print("worker rule already present or pattern mismatch:", OLD in wf)

# 5) llms.txt references
for f in ("llms.txt", "llms-full.txt"):
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        t = io.open(p, encoding="utf-8", errors="ignore").read()
        lines = [l for l in t.split("\n") if not any(pat in l.lower() for pat in KILL_PATS)]
        if len(lines) != t.count("\n") + 1:
            io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
            print(f, "scrubbed")

print("DONE - now commit, deploy, purge, verify 410s")