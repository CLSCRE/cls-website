#!/usr/bin/env python3
"""Link the new placement pages from a short, explicit list of existing pages.

Pages added 2026-11-27 (Peec gap, debt and equity placement slice):
  /financing/debt-and-equity-placement.html
  /financing/commercial-loan-process.html

Idempotent (markers). Touches only the files listed below, never a glob.
Mirrors the link added to templates/financing_conversion_page.html so a later
render of those hubs produces the same line.
Usage: python apply_process_links.py [--dry-run]
"""
import sys
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent.parent
DRY = "--dry-run" in sys.argv

# 1. Financing hubs: link under the "One process" quote.
HUB_FILES = ["commercial-mortgage-loans", "permanent-loans", "mezzanine",
             "preferred-equity", "cmbs-loans", "agency-loans"]
HUB_ANCHOR = '<p class="pf-quote">A well-structured financing process should create real choices for the borrower, not simply deliver the first term sheet.</p>'
HUB_ADD = ('\n      <p class="pf-intro"><!-- cls-process-link --><a class="pf-text-link" href="commercial-loan-process.html">See the step by step timeline &rarr;</a>'
           ' <span aria-hidden="true">&middot;</span> <a class="pf-text-link" href="debt-and-equity-placement.html">What we place</a></p>')

EDITS = []  # (relative path, anchor, replacement, marker)
for slug in HUB_FILES:
    EDITS.append((f"financing/{slug}.html", HUB_ANCHOR, HUB_ANCHOR + HUB_ADD, "cls-process-link"))

# 2. Life company process page: general process cross-link in the lede.
EDITS.append((
    "financing/life-company-loan-process.html",
    'shown on our <a href="life-company-loans.html">life company loans overview</a>.</p>',
    'shown on our <a href="life-company-loans.html">life company loans overview</a>. '
    'For the process that applies to every loan type, see our <a href="commercial-loan-process.html">commercial loan process</a>.</p>',
    'href="commercial-loan-process.html"'))

# 3. About page: link from the access paragraph.
EDITS.append((
    "about.html",
    "to engineer the optimal capital stack for every deal.",
    'to engineer the optimal capital stack for every deal. See <a href="financing/debt-and-equity-placement.html">what we place</a> '
    'and <a href="financing/commercial-loan-process.html">how a financing runs from engagement to closing</a>.',
    'href="financing/debt-and-equity-placement.html"'))

# 4. llms.txt: one new section listing both pages.
LLMS_ANCHOR = "## Construction loans in Los Angeles\n"
LLMS_ADD = ("## Debt and equity placement and process\n\n"
            "- [Commercial Real Estate Debt and Equity Placement](https://clscre.com/financing/debt-and-equity-placement.html): "
            "What CLS CRE places ($2M to $100M+, permanent, construction, bridge, life company, CMBS, agency, mezzanine and preferred equity), "
            "the capital sources behind each program, and our role as broker and correspondent\n"
            "- [Commercial Loan Process: Engagement to Closing](https://clscre.com/financing/commercial-loan-process.html): "
            "The eight step process from intake and underwriting through engagement, lender package, proposals, third-party reports and closing\n\n")
EDITS.append(("llms.txt", LLMS_ANCHOR, LLMS_ADD + LLMS_ANCHOR, "debt-and-equity-placement.html"))

for rel, anchor, repl, marker in EDITS:
    path = WEBSITE / rel
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    crlf = "\r\n" in text
    t = text.replace("\r\n", "\n")
    if marker in t:
        print(f"skip (already linked): {rel}")
        continue
    if t.count(anchor) != 1:
        print(f"NO UNIQUE ANCHOR ({t.count(anchor)}): {rel}")
        continue
    t = t.replace(anchor, repl)
    if crlf:
        t = t.replace("\n", "\r\n")
    if not DRY:
        path.write_bytes(t.encode("utf-8"))
    print(f"{'would edit' if DRY else 'edited'}: {rel}")
