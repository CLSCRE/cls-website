#!/usr/bin/env python3
"""One-time patch: per-loan-type FAQ rate ranges in _generator/generate.py.

Bug: build_city_faqs() hardcoded {rate_low}=5.34% and {rate_high}=8.25%
(the permanent range) for every loan type, so bridge/construction/hard money
city pages all claimed permanent pricing. build_neighborhood_faqs() also
hardcoded a stale rate sentence that disagreed with loan_types.json.

Fix: rate ranges now parse from loan_types.json key_features.rates (single
source of truth), with explicit overrides for the two display strings that
are not simple ranges. Idempotent. Fails loudly if anchors are not found.

Run from repo root:  python scripts/fix_city_faq_rates.py
Then regenerate per the standard sequence in docs/SEO_ARCHITECTURE.md.
"""
import py_compile
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parent.parent / "_generator" / "generate.py"

MARKER = "_loan_rates_by_slug"

HELPER_LINES = [
    "# \u2500\u2500 Per-loan-type FAQ rate ranges \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    "# Fix (2026-07-08): city and neighborhood FAQs previously hardcoded the",
    "# permanent range (5.34% to 8.25%) for every loan type. Ranges now come",
    "# from loan_types.json key_features.rates, the single source of truth.",
    "_RATE_RANGE_RE = re.compile(r\"(\\d+(?:\\.\\d+)?%)\\s*(?:-|to)\\s*(\\d+(?:\\.\\d+)?%)\")",
    "",
    "# Display strings that are not simple ranges. If rate_low / rate_high",
    "# fields are ever added to loan_types.json entries, those win instead.",
    "_RATE_OVERRIDES = {",
    "    \"net-lease-financing\": (\"5.00%\", \"6.75%\"),",
    "    \"bridge-to-perm-loans\": (\"6.50%\", \"10.00%\"),",
    "}",
    "",
    "_LOAN_RATES_CACHE = None",
    "",
    "",
    "def _loan_rates_by_slug():",
    "    \"\"\"slug -> (rate_low, rate_high) from loan_types.json.\"\"\"",
    "    global _LOAN_RATES_CACHE",
    "    if _LOAN_RATES_CACHE is None:",
    "        table = {}",
    "        for lt in load_json(\"loan_types.json\"):",
    "            slug = lt.get(\"slug\", \"\")",
    "            if lt.get(\"rate_low\") and lt.get(\"rate_high\"):",
    "                table[slug] = (lt[\"rate_low\"], lt[\"rate_high\"])",
    "                continue",
    "            if slug in _RATE_OVERRIDES:",
    "                table[slug] = _RATE_OVERRIDES[slug]",
    "                continue",
    "            rates_str = (lt.get(\"key_features\") or {}).get(\"rates\", \"\")",
    "            m = _RATE_RANGE_RE.search(rates_str)",
    "            if m:",
    "                table[slug] = (m.group(1), m.group(2))",
    "        _LOAN_RATES_CACHE = table",
    "    return _LOAN_RATES_CACHE",
    "",
    "",
    "def _loan_rate_range(loan):",
    "    \"\"\"(rate_low, rate_high) for a loan dict; all-programs span fallback.\"\"\"",
    "    default = (\"5.34%\", \"13.04%\")",
    "    if not loan:",
    "        return default",
    "    return _loan_rates_by_slug().get(loan.get(\"slug\", \"\"), default)",
    "",
    "",
    "def _slug_rate_text(slug):",
    "    low, high = _loan_rates_by_slug().get(slug, (\"5.34%\", \"13.04%\"))",
    "    return f\"{low} to {high}\"",
    "",
    "",
]

ANCHOR_DEF = "def build_city_faqs(templates, loan=None, prop=None, city=None):"

OLD_DICT = (
    '            "{rate_low}": "5.34%",\n'
    '            "{rate_high}": "8.25%",\n'
)
NEW_DICT = (
    '            "{rate_low}": _loan_rate_range(loan)[0],\n'
    '            "{rate_high}": _loan_rate_range(loan)[1],\n'
)

OLD_SENTENCE = (
    "Permanent loan rates typically range from 5.34% to 8.25%, "
    "bridge loans from 7.5% to 12%, and construction loans from 8% to 13%."
)
NEW_SENTENCE = (
    "Permanent loan rates typically range from {_slug_rate_text('permanent-loans')}, "
    "bridge loans from {_slug_rate_text('bridge-loans')}, "
    "and construction loans from {_slug_rate_text('construction-loans')}."
)


def main():
    with open(GEN, "r", encoding="utf-8", newline="") as f:
        src = f.read()
    eol = "\r\n" if "\r\n" in src else "\n"

    if MARKER in src:
        print("Already patched. Nothing to do.")
        return 0

    fails = []
    if ANCHOR_DEF not in src:
        fails.append("build_city_faqs def anchor")
    old_dict = OLD_DICT.replace("\n", eol)
    if old_dict not in src:
        fails.append("hardcoded rate_low/rate_high dict lines")
    if OLD_SENTENCE not in src:
        fails.append("neighborhood hardcoded rate sentence")
    if fails:
        print("ABORT, anchors not found (file changed upstream?):")
        for f in fails:
            print("  -", f)
        return 1

    helper = eol.join(HELPER_LINES) + eol
    src = src.replace(ANCHOR_DEF, helper + ANCHOR_DEF, 1)
    src = src.replace(old_dict, NEW_DICT.replace("\n", eol), 1)
    src = src.replace(OLD_SENTENCE, NEW_SENTENCE, 1)

    with open(GEN, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    py_compile.compile(str(GEN), doraise=True)
    print("Patched and compiled OK:", GEN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
