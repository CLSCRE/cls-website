"""Pure date-rewrite helpers (no imports from the rest of the generator, so the rate bot
can load this file from its sparse checkout). Used by freshness.py and scripts/cmr_rate_sync.py.

rewrite_dates(html, iso) sets a page's modified dates to iso, clamped to
[datePublished, today]:
    "dateModified" / "lastReviewed" in JSON-LD, article:modified_time / og:updated_time meta,
    Updated <time datetime="...">Month YYYY</time> bylines (display format preserved),
    "Updated|Last updated|Rates updated Month YYYY" visible text, and the
    "indicative pricing as of / quote pipeline as of Month YYYY" lines.
It never touches datePublished, "As of <month>" sentences or "Published:" lines.
"""
from __future__ import annotations

import re
from datetime import date, datetime

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
_MON_RX = "|".join(MONTHS)


def fmt_like(sample: str, iso: str) -> str:
    """Render iso in the same style as the visible sample text it replaces."""
    d = datetime.strptime(iso, "%Y-%m-%d")
    s = sample.strip()
    if re.fullmatch(rf"(?:{_MON_RX})\s+\d{{4}}", s):
        return f"{MONTHS[d.month - 1]} {d.year}"
    if re.fullmatch(rf"(?:{_MON_RX})\s+\d{{1,2}},\s*\d{{4}}", s):
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    if re.fullmatch(r"[A-Z][a-z]{2}\.?\s+\d{1,2},\s*\d{4}", s):
        return f"{MONTHS[d.month - 1][:3]} {d.day}, {d.year}"
    return f"{MONTHS[d.month - 1]} {d.year}"


_JSON_MOD = re.compile(r'("dateModified"\s*:\s*")(\d{4}-\d{2}-\d{2})([^"]*")')
_JSON_REV = re.compile(r'("lastReviewed"\s*:\s*")(\d{4}-\d{2}-\d{2})([^"]*")')
_JSON_PUB = re.compile(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})')
_META = re.compile(r'(<meta\s+(?:property|name)="(?:article:modified_time|og:updated_time)"\s+content=")(\d{4}-\d{2}-\d{2})([^"]*")', re.I)
_UPD_TIME = re.compile(r'((?:Updated|updated):?\s*<time[^>]*datetime=")(\d{4}-\d{2}-\d{2})("[^>]*>)([^<]*)(</time>)')
_MON_ABBR = "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec"
_UPD_TEXT = re.compile(rf'((?:Last updated|Rates updated|Updated)\s*:?\s*)((?:{_MON_RX}|(?:{_MON_ABBR})\.?)(?:\s+\d{{1,2}},)?\s+\d{{4}})')


# "indicative pricing as of <month>" / "quote pipeline as of <month>" on comparison, loan-size and
# specialty property pages: the templates emit the build month, the page's own date corrects it.
_ASOF_PRICING = re.compile(rf'((?:indicative pricing|quote pipeline) as of )((?:{_MON_RX})\s+\d{{4}})')


def rewrite_dates(html: str, iso: str, *, today: str | None = None) -> str:
    """Return html with its modified dates set to iso (clamped to [datePublished, today])."""
    today = today or date.today().isoformat()
    pub = _JSON_PUB.findall(html)
    if pub:
        iso = max(iso, min(pub))
    iso = min(iso, today)

    html = _JSON_MOD.sub(lambda m: f"{m.group(1)}{iso}{m.group(3)}", html)
    html = _JSON_REV.sub(lambda m: f"{m.group(1)}{iso}{m.group(3)}", html)
    html = _META.sub(lambda m: f"{m.group(1)}{iso}{m.group(3)}", html)
    html = _UPD_TIME.sub(lambda m: f"{m.group(1)}{iso}{m.group(3)}{fmt_like(m.group(4), iso)}{m.group(5)}", html)
    html = _UPD_TEXT.sub(lambda m: m.group(1) + fmt_like(m.group(2), iso), html)
    html = _ASOF_PRICING.sub(lambda m: m.group(1) + fmt_like(m.group(2), iso), html)
    return html
