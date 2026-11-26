"""Title length rule for SERP titles (added 2026-11-25 from the SEO audit).

Problem: 695 of 788 sitemap titles were over 60 characters, mostly because the
" | Commercial Lending Solutions" suffix (31 chars) is appended to a base title
that is already long. Google truncates around 60 characters and rewrites many
of these titles anyway.

Rule, applied to a title that ends in a brand suffix:
  1. base + " | Commercial Lending Solutions" if that is 60 characters or fewer
  2. else base + " | CLS CRE" if that is 60 characters or fewer
  3. else the base title with no suffix (still long? it needs a hand rewrite)

Titles with no brand suffix are never touched. The rule only changes the
<title>, og:title and twitter:title tags, never the JSON-LD.

Rollout is by batch so each can be measured in Search Console before the next
ships. TITLE_RULE_PREFIXES lists the website-relative path prefixes in scope.
Extend it one batch at a time. generate.py applies the rule at its write choke
point, so a regeneration reproduces the same titles instead of reverting them.
"""
import html as _html
import re

SUFFIX_FULL = " | Commercial Lending Solutions"
SUFFIX_SHORT = " | CLS CRE"
LIMIT = 60

# Batch 1 (2026-11-25): glossary 64 pages + markets 47 pages.
TITLE_RULE_PREFIXES = (
    "glossary/",
    "markets/",
)

# Pages that earn clicks today: never retitled by the rule.
PROTECTED_PATHS = frozenset({
    "index.html",
    "financing/commercial-mortgage-broker-los-angeles.html",
    "financing/permanent-loans-los-angeles.html",
    "markets/san-luis-obispo/downtown-slo.html",
})

_TITLE_RE = re.compile(r"(<title>)(.*?)(</title>)", re.S | re.I)
_META_RE = re.compile(
    r'(<meta\s+(?:property="og:title"|name="twitter:title")\s+content=")([^"]*)(")',
    re.I,
)


def _length(raw):
    return len(_html.unescape(raw))


def shorten_title(raw):
    """Return the title after the suffix rule. raw may contain HTML entities."""
    for suffix in (SUFFIX_FULL, SUFFIX_SHORT):
        if raw.endswith(suffix):
            base = raw[: -len(suffix)]
            break
    else:
        return raw
    for candidate in (base + SUFFIX_FULL, base + SUFFIX_SHORT):
        if _length(candidate) <= LIMIT:
            return candidate
    return base


def in_scope(rel_path):
    rel = rel_path.replace("\\", "/")
    return rel.startswith(TITLE_RULE_PREFIXES) and rel not in PROTECTED_PATHS


def apply_to_html(html_text, rel_path):
    """Apply the rule to <title>, og:title and twitter:title of one page."""
    if not in_scope(rel_path):
        return html_text
    out = _TITLE_RE.sub(lambda m: m.group(1) + shorten_title(m.group(2)) + m.group(3), html_text, count=1)
    out = _META_RE.sub(lambda m: m.group(1) + shorten_title(m.group(2)) + m.group(3), out)
    return out
