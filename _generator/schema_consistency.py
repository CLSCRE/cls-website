"""Entity and schema consistency pass for clscre.com (SEO, GEO and AEO).

One idempotent post-processing step that makes the firm and its founder a single
entity on every indexable page, instead of a fresh copy per template:

  1. Organization / FinancialService / ProfessionalService nodes named exactly
     "Commercial Lending Solutions" get the stable @id ORG_ID. Nodes that carry
     contact data (address, telephone, email or sameAs) also get the one canonical
     PostalAddress and the one canonical sameAs list.
  2. Person nodes named "Trevor Damyan" get the stable @id PERSON_ID, and any
     jobTitle is set to FOUNDER_TITLE.
  3. Visible street address "7951 Blackburn Ave" becomes "7951 Blackburn Avenue".
  4. Stale Facebook and Instagram handles are swapped for the current accounts.
  5. Pages with a visible FAQ block and no FAQPage markup get FAQPage JSON-LD built
     FROM that visible block, so markup and page text cannot disagree.
  6. Blog report posts that carry no JSON-LD at all get Article and BreadcrumbList.
  7. One H1 per page: later H1 tags (email-layout archives, repeated blog titles)
     become H2.

Why a post-pass and not template edits: 26 templates emit their own copy of the
Organization node, and hand-written pages have their own. A final pass guarantees the
result no matter which source produced the page (same idea as dash_scrub.py).

Used two ways:
  - generate.py calls run(WEBSITE_DIR) as a final step after the dash scrub.
  - Standalone:  python schema_consistency.py <website_dir> [--check]
    --check reports what would change and exits 1 if anything would.

Only pages listed in the sitemaps are touched. Blocks that do not change stay
byte-identical; a changed block is re-serialized in the style it was written in.
"""
import copy
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ORG_ID = "https://clscre.com/#organization"
PERSON_ID = "https://clscre.com/about/trevor-damyan.html#person"
FIRM_NAME = "Commercial Lending Solutions"
FOUNDER_NAME = "Trevor Damyan"
FOUNDER_TITLE = "Commercial Mortgage Broker"  # the role people search for and the wording ~550 visible bylines use; founder is expressed by Organization.founder

ADDRESS = {
    "@type": "PostalAddress",
    "streetAddress": "7951 Blackburn Avenue",
    "addressLocality": "Los Angeles",
    "addressRegion": "CA",
    "postalCode": "90048",
    "addressCountry": "US",
}
SAME_AS = [
    "https://www.linkedin.com/company/clscre",
    "https://www.linkedin.com/in/trevor-damyan-42636397/",
    "https://www.instagram.com/commerciallendingsolutions/",
    "https://www.facebook.com/profile.php?id=61591993674306",
    "https://www.loopnet.com/commercial-real-estate-brokers/profile/trevor-damyan/5t2wr8mb",
    "https://traded.co/agent/trevor-damyan/",
    "https://x.com/LAloanbroker",
    "https://www.bbb.org/us/ca/los-angeles/profile/real-estate-loans/commercial-lending-solutions-1216-1000067041",
    "https://www.youtube.com/@commercialmortagebroker",  # the handle really is spelled "mortage" (Trevor's channel)
]
STALE_SOCIAL = [
    # (regex, replacement). Old vanity handles auto-resolve to the new pages.
    (re.compile(r"https://www\.facebook\.com/mycommercialloanbroker/?"),
     "https://www.facebook.com/profile.php?id=61591993674306"),
    (re.compile(r"https://www\.instagram\.com/commercialloanbroker/?"),
     "https://www.instagram.com/commerciallendingsolutions/"),
]
ORG_TYPES = {"Organization", "FinancialService", "ProfessionalService", "LocalBusiness"}
CONTACT_KEYS = ("address", "telephone", "email", "sameAs")

LD_RE = re.compile(r'(<script[^>]*application/ld\+json[^>]*>)(.*?)(</script>)', re.S | re.I)
AVE_RE = re.compile(r"Blackburn Ave(?![A-Za-z])(\.?)")


# ── JSON-LD normalisation ────────────────────────────────────────────────────

def _types(node):
    t = node.get("@type")
    return set(t) if isinstance(t, list) else {t}


def _put_id_first(node, ident):
    """Rebuild the dict so @context, @type, @id lead (readable, stable order)."""
    rest = {k: v for k, v in node.items() if k not in ("@context", "@type", "@id")}
    head = {k: node[k] for k in ("@context", "@type") if k in node}
    head["@id"] = ident
    node.clear()
    node.update(head)
    node.update(rest)


def normalize_node(node):
    ty = _types(node)
    name = node.get("name")
    if ty & ORG_TYPES and name == FIRM_NAME:
        if node.get("@id") != ORG_ID:
            _put_id_first(node, ORG_ID)
        if any(k in node for k in CONTACT_KEYS):
            if node.get("address") != ADDRESS:
                node["address"] = copy.deepcopy(ADDRESS)
            if node.get("sameAs") != SAME_AS:
                node["sameAs"] = list(SAME_AS)
    elif "Person" in ty and name == FOUNDER_NAME:
        if node.get("@id") != PERSON_ID:
            _put_id_first(node, PERSON_ID)
        if "jobTitle" in node and node["jobTitle"] != FOUNDER_TITLE:
            node["jobTitle"] = FOUNDER_TITLE


def walk(x):
    if isinstance(x, dict):
        normalize_node(x)
        for v in list(x.values()):
            walk(v)
    elif isinstance(x, list):
        for v in x:
            walk(v)


def _dump_like(original_block, obj):
    lead = original_block[: len(original_block) - len(original_block.lstrip())]
    trail = original_block[len(original_block.rstrip()):]
    body = original_block.strip()
    spaced = '": ' in body
    if "\n" in body:
        m = re.search(r"\n( +)\S", body)
        indent = len(m.group(1)) if m else 2
        s = json.dumps(obj, ensure_ascii=False, indent=indent, separators=(",", ": "))
    else:
        s = json.dumps(obj, ensure_ascii=False,
                       separators=(", ", ": ") if spaced else (",", ":"))
    return lead + s + trail


def normalize_ld_blocks(text):
    def sub(m):
        head, block, tail = m.group(1), m.group(2), m.group(3)
        try:
            obj = json.loads(block, strict=False)
        except Exception:
            return m.group(0)
        before = copy.deepcopy(obj)
        walk(obj)
        if obj == before:
            return m.group(0)
        return head + _dump_like(block, obj) + tail
    return LD_RE.sub(sub, text)


# ── Visible text fixes ───────────────────────────────────────────────────────

def fix_visible_text(text):
    text = AVE_RE.sub(lambda m: "Blackburn Avenue" + m.group(1), text)
    for rx, rep in STALE_SOCIAL:
        text = rx.sub(rep, text)
    return text


# ── FAQPage built from the visible FAQ block ─────────────────────────────────

class _FaqParser(HTMLParser):
    """Collects (question, answer) from .faq-item blocks. Handles the three
    layouts on the site: button/div .faq-question + .faq-answer, and h3 + p."""
    VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.item_depth = None
        self.items = []
        self.cur = None
        self.mode = None       # 'q' | 'a' | 'h' | 'p'
        self.mode_depth = None
        self.skip_depth = None  # inside .faq-icon
        self.buf = []

    @staticmethod
    def _classes(attrs):
        return set((dict(attrs).get("class") or "").split())

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        self.depth += 1
        cls = self._classes(attrs)
        if self.item_depth is None:
            if "faq-item" in cls:
                self.item_depth = self.depth
                self.cur = {"q": [], "a": [], "h": [], "p": []}
            return
        if self.skip_depth is None and "faq-icon" in cls:
            self.skip_depth = self.depth
            return
        if self.mode is None:
            if "faq-question" in cls:
                self.mode, self.mode_depth = "q", self.depth
            elif "faq-answer" in cls:
                self.mode, self.mode_depth = "a", self.depth
            elif tag in ("h3", "h4") and not self.cur["h"]:
                self.mode, self.mode_depth = "h", self.depth
            elif tag == "p":
                self.mode, self.mode_depth = "p", self.depth
        elif self.mode == "a" and tag in ("p", "li"):
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.skip_depth is not None and self.depth == self.skip_depth:
            self.skip_depth = None
        if self.mode and self.depth == self.mode_depth:
            self.cur[self.mode].append("".join(self.buf))
            self.buf, self.mode, self.mode_depth = [], None, None
        if self.item_depth is not None and self.depth == self.item_depth:
            c = self.cur
            q = _clean(" ".join(c["q"]) or " ".join(c["h"]))
            a = _clean(" ".join(c["a"]) or " ".join(c["p"]))
            if q and a:
                self.items.append((q, a))
            self.item_depth = self.cur = None
        self.depth -= 1

    def handle_data(self, data):
        if self.mode and self.skip_depth is None:
            self.buf.append(data)


def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def faq_items(text):
    p = _FaqParser()
    try:
        p.feed(text)
    except Exception:
        return []
    seen, out = set(), []
    for q, a in p.items:
        if q not in seen:
            seen.add(q)
            out.append((q, a))
    return out


def has_type(text, wanted):
    for m in LD_RE.finditer(text):
        if re.search(r'"@type"\s*:\s*"%s"' % wanted, m.group(2)):
            return True
    return False


def _insert_ld(text, obj):
    block = '<script type="application/ld+json">' + json.dumps(
        obj, ensure_ascii=False, separators=(",", ":")) + "</script>"
    last = None
    for m in LD_RE.finditer(text):
        last = m
    if last:
        nl = "\r\n" if "\r\n" in text else "\n"
        return text[: last.end()] + nl + block + text[last.end():]
    i = text.lower().find("</head>")
    if i == -1:
        return text
    nl = "\r\n" if "\r\n" in text else "\n"
    return text[:i] + block + nl + text[i:]


def add_faq_schema(text):
    if has_type(text, "FAQPage"):
        return text
    items = faq_items(text)
    if len(items) < 2:
        return text
    obj = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in items
        ],
    }
    return _insert_ld(text, obj)


# ── Report posts with no JSON-LD at all ──────────────────────────────────────

_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}


def add_report_post_schema(text, rel):
    if not rel.startswith("blog/") or LD_RE.search(text):
        return text
    if 'property="og:type" content="article"' not in text:
        return text
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', text)
    desc = re.search(r'<meta name="description" content="([^"]*)"', text)
    img = re.search(r'<meta property="og:image" content="([^"]+)"', text)
    dm = re.search(r"(%s)\s+(\d{1,2}),\s+(\d{4})" % "|".join(_MONTHS),
                   h1.group(1) if h1 else "")
    if not (h1 and canon and desc and dm):
        return text
    date = "%s-%02d-%02d" % (dm.group(3), _MONTHS[dm.group(1)], int(dm.group(2)))
    title = _clean(re.sub(r"<[^>]+>", "", h1.group(1)))
    url = canon.group(1)
    article = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": title, "description": html.unescape(desc.group(1)),
        "image": img.group(1) if img else "https://clscre.com/images/cls-og-image.png",
        "author": {"@type": "Person", "@id": PERSON_ID, "name": FOUNDER_NAME,
                   "jobTitle": FOUNDER_TITLE,
                   "url": "https://clscre.com/about/trevor-damyan.html"},
        "datePublished": date, "dateModified": date,
        "publisher": {"@type": "Organization", "@id": ORG_ID, "name": FIRM_NAME,
                      "url": "https://clscre.com",
                      "logo": {"@type": "ImageObject",
                               "url": "https://clscre.com/images/cls-logo-skyline.png"}},
        "mainEntityOfPage": url,
    }
    crumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://clscre.com"},
            {"@type": "ListItem", "position": 2, "name": "Insights", "item": "https://clscre.com/blog/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url},
        ],
    }
    text = _insert_ld(text, article)
    return _insert_ld(text, crumbs)


# ── Driver ───────────────────────────────────────────────────────────────────

def sitemap_files(root):
    root = Path(root)
    out = []
    for sm in sorted(root.glob("sitemap-*.xml")):
        if sm.name == "sitemap-index.xml":
            continue
        for loc in re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8")):
            rel = loc.replace("https://clscre.com", "").lstrip("/")
            if rel == "" or rel.endswith("/"):
                rel += "index.html"
            p = root / rel
            if p.exists() and p.suffix == ".html":
                out.append(p)
    return sorted(set(out))


H1_OPEN = re.compile(r"<h1\b", re.I)
H1_CLOSE = re.compile(r"</h1>", re.I)


def demote_extra_h1(text):
    """One H1 per page: keep the first, turn every later <h1> into an <h2>.
    Email-layout archives use H1 for every section; some blog bodies repeat the title."""
    opens = list(H1_OPEN.finditer(text))
    if len(opens) < 2:
        return text
    first_close = H1_CLOSE.search(text, opens[0].end())
    if not first_close:
        return text
    head, tail = text[: first_close.end()], text[first_close.end():]
    tail = H1_OPEN.sub("<h2", tail)
    tail = H1_CLOSE.sub("</h2>", tail)
    return head + tail


def process(text, rel):
    out = normalize_ld_blocks(text)
    out = demote_extra_h1(out)
    out = fix_visible_text(out)
    out = add_faq_schema(out)
    out = add_report_post_schema(out, rel)
    return out


def run(root, check=False):
    root = Path(root)
    changed = 0
    for p in sitemap_files(root):
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        new = process(text, p.relative_to(root).as_posix())
        if new != text:
            changed += 1
            if not check:
                p.write_bytes(new.encode("utf-8"))
    return changed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python schema_consistency.py <website_dir> [--check]")
    chk = "--check" in sys.argv
    n = run(sys.argv[1], check=chk)
    print(f"  [schema-consistency] {n} pages {'would change' if chk else 'updated'}")
    sys.exit(1 if (chk and n) else 0)
