#!/usr/bin/env python3
"""Capital stack slice (Peec gap, 2026-11-27): align mezzanine, preferred equity and capital stack content
with Trevor's confirmed terms and add a capital stack block to the two hubs.

Confirmed terms (see docs/automation/PEEC_GAP_WORKSTREAMS_2026-11-27.md and llms.txt):
  mezzanine and preferred equity from a $10M minimum, combined leverage up to 85%, rates 8% to 14%;
  construction loans up to 75% loan to cost.

Every edit is a pure function of the file text, idempotent, and asserts that each replacement matched
(so it fails loudly if a page drifted). transforms() is also used by the commit helper to build the
committed blob from the committed text, so other sessions' uncommitted edits are never swept in.

Usage: python apply_capital_stack_update.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEBSITE = HERE.parent
GUIDE_SLUG = "commercial-real-estate-capital-stack-explained"
GUIDE_URL = f"https://clscre.com/blog/{GUIDE_SLUG}.html"
GUIDE_H1 = "Commercial Real Estate Capital Stack Explained, With an Example"
GUIDE_DESC = ("How the CRE capital stack works: senior debt, mezzanine, preferred equity and common equity, "
              "with a $100 million worked example and when to add each layer.")
MARK = "<!-- cls-capital-stack -->"


class Skip(Exception):
    pass


def rep(t, old, new, label=None, count=None):
    """Replace all occurrences; require at least one unless already applied."""
    n = t.count(old)
    if n == 0:
        if new in t:
            return t
        raise AssertionError(f"pattern not found: {label or old[:70]}")
    if count is not None:
        assert n == count, f"{label or old[:60]}: expected {count} got {n}"
    return t.replace(old, new)


def scoped(t, start, end, fn):
    a = t.index(start)
    b = t.index(end, a + len(start)) if end else len(t)
    return t[:a] + fn(t[a:b]) + t[b:]


# ----------------------------------------------------------------------------- hubs
BLOCK_STYLE = (
    "<style>.cs-t{width:100%;border-collapse:collapse;margin:18px 0;font-size:15px;background:#fff}"
    ".cs-t th,.cs-t td{border:1px solid #e5e7eb;padding:10px 12px;text-align:left;vertical-align:top;line-height:1.45}"
    ".cs-t th{background:#f9fafb;color:#153D63}.cs-tw{overflow-x:auto;-webkit-overflow-scrolling:touch}"
    ".cs-tw .cs-t{min-width:560px}</style>"
)

HUB_COPY = {
    "mezzanine": {
        "h2": "Where mezzanine debt sits in the stack.",
        "intro": ("Mezzanine debt ranks behind the senior mortgage and ahead of preferred equity and common equity. "
                  "It adds leverage through a pledge of the owner's equity interests rather than a second mortgage, "
                  "and the senior lender has to consent."),
        "other_label": "preferred equity",
        "other_href": "preferred-equity.html",
    },
    "preferred-equity": {
        "h2": "Where preferred equity sits in the stack.",
        "intro": ("Preferred equity ranks behind the senior loan and any mezzanine debt and ahead of common equity. "
                  "It is an ownership position, not a loan, so it carries a preferred return and the rights written "
                  "into the operating agreement instead of a lien."),
        "other_label": "mezzanine debt",
        "other_href": "mezzanine.html",
    },
}

HUB_FAQ = [
    ("Where do mezzanine debt and preferred equity sit in the capital stack?",
     "Behind the senior loan and ahead of common equity. The order from first paid to last is senior debt, mezzanine "
     "debt, preferred equity, then common equity, and when a deal uses both layers the mezzanine lender is repaid "
     "before the preferred investor. Losses run the other way, so common equity absorbs them first."),
    ("What does a capital stack look like with real numbers?",
     "On a $100 million ground-up project, a senior construction loan at 75 percent of cost is $75 million and the "
     "sponsor funds $25 million. Adding a $10 million mezzanine or preferred layer takes combined leverage to 85 "
     "percent and cuts the sponsor's equity to $15 million. At 8% to 14%, that layer costs $0.8 million to $1.4 "
     "million a year before fees. These are illustrative round numbers, not an offer."),
]


def hub_block(slug):
    c = HUB_COPY[slug]
    return (
        f"{MARK}\n"
        '<section class="pf-section pf-paper" id="capital-stack">\n'
        f"  {BLOCK_STYLE}\n"
        '  <div class="pf-wrap">\n'
        '    <div class="pf-deal-heading">\n'
        "      <div>\n"
        '        <div class="pf-kicker">Capital stack</div>\n'
        f'        <h2>{c["h2"]}</h2>\n'
        "      </div>\n"
        f'      <a class="pf-text-link" href="../blog/{GUIDE_SLUG}.html">Full capital stack guide &rarr;</a>\n'
        "    </div>\n"
        f'    <p class="pf-intro">{c["intro"]}</p>\n'
        '    <div class="cs-tw"><table class="cs-t">\n'
        "      <thead><tr><th>Layer</th><th>Repaid</th><th>Secured by</th><th>Cost on deals we arrange</th></tr></thead>\n"
        "      <tbody>\n"
        "        <tr><td><strong>Senior debt</strong></td><td>First</td><td>First lien on the property</td><td>Lowest in the stack. See <a class=\"pf-text-link\" href=\"../rates.html\">current rates</a></td></tr>\n"
        "        <tr><td><strong>Mezzanine debt</strong></td><td>Second</td><td>Pledge of the owner's equity interests</td><td>8% to 14%, from a $10M minimum</td></tr>\n"
        "        <tr><td><strong>Preferred equity</strong></td><td>Third</td><td>Operating agreement rights, no lien</td><td>8% to 14%, from a $10M minimum</td></tr>\n"
        "        <tr><td><strong>Common equity</strong></td><td>Last</td><td>Residual claim after every layer above</td><td>No fixed rate, no cap</td></tr>\n"
        "      </tbody>\n"
        "    </table></div>\n"
        '    <p class="pf-intro"><strong>Worked example.</strong> On a $100 million ground-up project, a senior construction '
        "loan at 75 percent of cost is $75 million and the sponsor funds $25 million. Adding a $10 million mezzanine or "
        "preferred layer takes combined leverage to 85 percent and cuts the sponsor's equity to $15 million. At 8% to 14%, "
        "that layer costs $0.8 million to $1.4 million a year before fees. These are illustrative round numbers, not an offer.</p>\n"
        f'    <p class="pf-intro"><strong>Which layer fits.</strong> '
        "Mezzanine debt fits when the senior lender permits a pledge of ownership interests and the sponsor wants a "
        "defined loan with a maturity. Preferred equity fits when the senior loan documents bar more debt but allow equity, "
        f'at the price of control triggers. See the <a style="color:inherit;font-size:inherit;text-decoration:underline" href="../comparisons/mezzanine-vs-preferred-equity.html">mezzanine versus preferred equity comparison</a>'
        f' and our <a style="color:inherit;font-size:inherit;text-decoration:underline" href="{c["other_href"]}">{c["other_label"]} page</a>.</p>\n'
        "  </div>\n"
        "</section>\n"
        "<!-- /cls-capital-stack -->\n\n"
    )


def add_hub_faq(t):
    if HUB_FAQ[0][0] in t:
        return t
    # DOM
    idx = t.rfind('id="pf-faq-panel-')
    assert idx > 0, "no faq panels"
    n = int(re.match(r'id="pf-faq-panel-(\d+)"', t[idx:]).group(1))
    tail = "</p></div></div>\n      </div>"
    p = t.index(tail, idx)
    at = p + len(tail)
    items = ""
    for i, (q, a) in enumerate(HUB_FAQ, start=n + 1):
        items += (
            '\n      <div class="pf-faq-item ">\n'
            f'        <button type="button" class="pf-faq-q" id="pf-faq-button-{i}" aria-expanded="false" aria-controls="pf-faq-panel-{i}">\n'
            f'          <span>{q}</span><span aria-hidden="true">+</span>\n'
            "        </button>\n"
            f'        <div class="pf-faq-a" id="pf-faq-panel-{i}" role="region" aria-labelledby="pf-faq-button-{i}" hidden><div><p>{a}</p></div></div>\n'
            "      </div>")
    t = t[:at] + items + t[at:]
    # schema
    m = re.search(r'\{"@context":"https://schema.org","@type":"FAQPage".*?\}\]\}', t, re.S)
    assert m, "no FAQPage schema"
    j = json.loads(m.group(0))
    for q, a in HUB_FAQ:
        j["mainEntity"].append({"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}})
    return t[:m.start()] + json.dumps(j, ensure_ascii=False, separators=(",", ":")) + t[m.end():]


def add_hub_block(t, slug):
    if MARK in t:
        a = t.index(MARK)
        end = "<!-- /cls-capital-stack -->\n\n"
        b = t.index(end, a) + len(end)
        return t[:a] + hub_block(slug) + t[b:]
    anchor = "<!-- cls-hub-compare -->"
    assert t.count(anchor) == 1, "hub-compare anchor"
    return t.replace(anchor, hub_block(slug) + anchor)


PREF_PAIRS = [
    ("$2MM - $50M+ at 10% - 16% Preferred Return", "$10M+ at 8% to 14% Preferred Return"),
    ("<strong>$2MM - $50M+</strong>", "<strong>$10M+</strong>"),
    ("10% - 16% Preferred Return", "8% to 14% Preferred Return"),
    ("Up to 85-90% of Total Capitalization", "Up to 85% of Total Capitalization"),
    ('"minValue":2000000,"value":"$2MM - $50M+"', '"minValue":10000000,"value":"$10M+"'),
    ("from $2MM. 10-16% preferred returns.", "from $10M. 8% to 14% preferred returns."),
    ("Minimum investment size is $2 million.", "Minimum investment size is $10 million."),
    ("typically 8 to 15 percent current or accruing", "generally 8 to 14 percent current or accruing"),
    ("senior lenders cap at 55 to 65 percent LTV and sponsors want", "the senior loan leaves an equity gap and sponsors want"),
    ("Investments start around $2 million and run to $50 million and above, with terms of 1 to 5 years.",
     "CLS CRE arranges preferred equity from a $10 million minimum, with terms of 1 to 5 years."),
    ("Current market is a 10% to 16% preferred return, structured",
     "On the deals we arrange, preferred equity has generally priced at an 8% to 14% preferred return, structured"),
    ("preferred equity commonly takes total capitalization to 85% to 90%. That matters when a senior lender caps at 55% to 65% of value or cost and the sponsor would otherwise",
     "preferred equity can take total capitalization up to 85%. That matters when the senior loan leaves an equity gap and the sponsor would otherwise"),
    ("requiring 80 to 90 percent capitalization", "requiring up to 85 percent capitalization"),
]


def pref_hub(t):
    for old, new in PREF_PAIRS:
        t = rep(t, old, new)
    t = add_hub_block(t, "preferred-equity")
    return add_hub_faq(t)


def mezz_hub(t):
    t = rep(t, "8% - 14%", "8% to 14%")
    t = rep(t, '"minValue":2000000,"value":"$10M+"', '"minValue":10000000,"value":"$10M+"')
    t = add_hub_block(t, "mezzanine")
    return add_hub_faq(t)


# ----------------------------------------------------------------------------- data json
def loan_types_json(t):
    def pref(s):
        s = rep(s, '"loan_amount": "$2MM - $50M+"', '"loan_amount": "$10M+"')
        s = rep(s, '"rates": "10% - 16% Preferred Return"', '"rates": "8% to 14% Preferred Return"')
        s = rep(s, '"total_leverage": "Up to 85-90% of Total Capitalization"', '"total_leverage": "Up to 85% of Total Capitalization"')
        s = rep(s, "from $2MM. 10-16% preferred returns.", "from $10M. 8% to 14% preferred returns.")
        s = rep(s, "Minimum investment size is $2 million.", "Minimum investment size is $10 million.")
        s = rep(s, "typically 8 to 15 percent current or accruing", "generally 8 to 14 percent current or accruing")
        s = rep(s, "senior lenders cap at 55 to 65 percent LTV and sponsors want", "the senior loan leaves an equity gap and sponsors want")
        s = rep(s, "requiring 80 to 90 percent capitalization", "requiring up to 85 percent capitalization")
        s = rep(s, '"min_amount_usd": 2000000', '"min_amount_usd": 10000000')
        return s
    t = scoped(t, '"slug": "preferred-equity"', '"apply_query": "program=preferred-equity"', pref)

    def mezz(s):
        return rep(s, '"rates": "8% - 14%"', '"rates": "8% to 14%"')
    return scoped(t, '"slug": "mezzanine"', '"apply_query"', mezz)


def faqs_json(t):
    def pref(s):
        s = rep(s, "Investments start around $2 million and run to $50 million and above, with terms of 1 to 5 years.",
                "CLS CRE arranges preferred equity from a $10 million minimum, with terms of 1 to 5 years.")
        s = rep(s, "Current market is a 10% to 16% preferred return, structured",
                "On the deals we arrange, preferred equity has generally priced at an 8% to 14% preferred return, structured")
        s = rep(s, "preferred equity commonly takes total capitalization to 85% to 90%. That matters when a senior lender caps at 55% to 65% of value or cost and the sponsor would otherwise",
                "preferred equity can take total capitalization up to 85%. That matters when the senior loan leaves an equity gap and the sponsor would otherwise")
        return s
    return scoped(t, '"preferred-equity": [', '"bridge-to-perm-loans": [', pref)


# ----------------------------------------------------------------------------- glossary
GLOSS = {
    "capital-stack": (
        "On a $20,000,000 acquisition, a senior lender funds 60 percent of cost, $12,000,000. A mezzanine lender adds $3,000,000, taking combined leverage to $15,000,000, or 75 percent of cost. A preferred equity investor contributes $2,000,000, bringing total outside capital to $17,000,000, or 85 percent. The sponsor's common equity fills the final $3,000,000. In a downside sale, proceeds repay the senior first, then mezzanine, then preferred, and the sponsor's $3,000,000 stands last in line.",
        "On a $100,000,000 ground-up project, a senior lender funds 60 percent of cost, $60,000,000. A mezzanine lender adds $15,000,000, taking combined leverage to $75,000,000, or 75 percent of cost. A preferred equity investor contributes $10,000,000, bringing total outside capital to $85,000,000, or 85 percent. The sponsor's common equity fills the final $15,000,000. In a downside sale, proceeds repay the senior first, then mezzanine, then preferred, and the sponsor's $15,000,000 stands last in line."),
    "mezzanine-debt": (
        "A sponsor acquiring a $40,000,000 multifamily asset gets a senior loan at 60 percent LTV, $24,000,000, but wants 75 percent leverage. A mezzanine lender advances $6,000,000 against a pledge of the membership interests in the property-owning LLC, bringing combined debt to $30,000,000, exactly 75 percent LTV. The sponsor's equity requirement drops from $16,000,000 to $10,000,000, and the mezzanine piece prices well above the senior coupon to compensate for its junior position.",
        "A sponsor acquiring a $50,000,000 multifamily asset gets a senior loan at 65 percent of cost, $32,500,000, but wants more leverage. A mezzanine lender advances $10,000,000 against a pledge of the membership interests in the property-owning LLC, bringing combined debt to $42,500,000, or 85 percent of cost. The sponsor's equity requirement drops from $17,500,000 to $7,500,000, and the mezzanine piece prices well above the senior coupon to compensate for its junior position."),
    "preferred-equity": (
        "A $25,000,000 value-add acquisition is capitalized with a $16,250,000 senior loan at 65 percent of cost. A preferred equity investor contributes $5,000,000, and the sponsor funds the remaining $3,750,000 of common equity. Total outside capital reaches $21,250,000, or 85 percent of cost. Cash flow pays senior debt service first, then accrues the preferred return on the $5,000,000, and the sponsor's common equity collects only after the preferred position is current.",
        "A $50,000,000 value-add acquisition is capitalized with a $32,500,000 senior loan at 65 percent of cost. A preferred equity investor contributes $10,000,000, and the sponsor funds the remaining $7,500,000 of common equity. Total outside capital reaches $42,500,000, or 85 percent of cost. Cash flow pays senior debt service first, then accrues the preferred return on the $10,000,000, and the sponsor's common equity collects only after the preferred position is current."),
}


def glossary_html(slug):
    old, new = GLOSS[slug]

    def f(t):
        return rep(t, old, new)
    return f


def glossary_json(t):
    for old, new in GLOSS.values():
        t = rep(t, old, new)
    return t


# ----------------------------------------------------------------------------- comparison page
CMP_PAIRS = [
    # table rows (HTML and JSON share the text, HTML wraps it in markup)
    ("Pricing range (Apr 2026)", "Pricing on deals we arrange"),
    ("10 to 14 percent current pay (some PIK)", "8 to 14 percent, current pay or accruing"),
    ("11 to 18 percent total return (current + accrual)", "8 to 14 percent preferred return, current pay or accruing"),
    ("5 to 15 percent of capital stack on top of senior", "From a $10M minimum; combined with the senior loan, up to 85 percent of cost"),
    ("10 to 25 percent of capital stack on top of senior", "From a $10M minimum; combined with the senior loan, up to 85 percent of cost"),
    ("Typical leverage", "Size and leverage"),
    ("They look similar to a sponsor seeking 70 to 85 percent LTC on a deal:", "They look similar to a sponsor seeking up to 85 percent of cost on a deal:"),
    ("Capital stack where 5 to 15 percent of additional leverage is needed and pricing in the 10 to 14 percent range works",
     "Capital stack where the gap above the senior loan is a $10M or larger layer and pricing in the 8 to 14 percent range works"),
    ("or when the deal needs 15 to 25 percent of incremental leverage above senior.", "or when the deal needs a layer the senior loan documents allow only as equity."),
    ("Sponsor needs 15 to 25 percent of additional capital that is too much for typical mezz programs",
     "Sponsor needs a layer that the senior loan documents allow as equity but not as debt"),
    ("the after-tax cost of mezz at 12 percent can be similar to preferred equity at 14 to 15 percent, narrowing the apparent pricing gap.",
     "the after-tax cost of mezz can come out closer to preferred equity than the headline rates suggest, narrowing the apparent pricing gap. Confirm the treatment with your tax advisor."),
    ("Mezz typically prices at 10 to 14 percent current pay (sometimes with PIK accrual). Common equity typically targets 15 to 22 percent IRR, depending on deal risk profile. Mezz fills the gap between senior debt and common equity at a cost between the two.",
     "On the deals we arrange, mezzanine has generally priced at 8 to 14 percent, current pay or accruing. Common equity has no fixed rate: it keeps whatever is left after every layer above it is paid, so investors underwrite it to a higher return than either layer. Mezz fills the gap between senior debt and common equity at a cost between the two."),
    ("On a $40M Class B multifamily acquisition with a Fannie Mae senior at 70 percent LTC and a 15 percent gap to the sponsor's 85 percent LTC equity-light target, two execution paths emerged. Option one was a Fannie-approved mezz lender providing $6M (15 percent of LTC) at 12 percent current pay with a Fannie intercreditor on standard agency terms. Option two was a private credit preferred equity provider offering $6M at 14 percent total return (10 percent current pay, 4 percent accrual) with force-sale rights at year 5 if the property had not exited. The sponsor took the mezz execution because the senior was Fannie (which has a clean intercreditor framework with its approved mezz list), the after-tax cost on the mezz was approximately 8.5 percent versus 10 percent on the preferred (assuming a 30 percent partnership tax rate), and the standstill protected the sponsor from forced action during the planned value-add period.",
     "Illustration with round numbers, not a specific closed loan. On a $100M multifamily project with a senior loan at 75 percent of cost ($75M), a sponsor wants to reach 85 percent combined leverage and cut its equity from $25M to $15M. Option one is a $10M mezzanine loan: the senior lender must consent and sign an intercreditor agreement, the lender's remedy is to foreclose on the pledged ownership interests, and the layer costs between $0.8M and $1.4M a year at 8 to 14 percent. Option two is $10M of preferred equity at the same price range: no second loan to repay, but the investor's operating agreement rights can include control triggers if agreed tests are missed. The decision turns first on what the senior loan documents permit, then on how much control the sponsor will give up if the plan slips."),
]
CMP_HTML_ONLY = [
    ("Rate ranges reflect indicative pricing as of May 2026, sourced from active CLS CRE quote pipeline. Pricing is property, sponsor, and structure dependent.",
     "Ranges are those CLS CRE arranges on transactions from a $10M minimum, with combined leverage up to 85 percent of cost. They are not offers, and pricing depends on the property, sponsor and structure."),
    ('<div class="section-label reveal">From the CLS CRE Pipeline</div>\n  <h2 class="section-title reveal">A Real Decision in Action</h2>',
     '<div class="section-label reveal">Worked example</div>\n  <h2 class="section-title reveal">A Decision in Action</h2>'),
    ("All deal references anonymize borrower and lender identities and use city-level geography only.",
     "Illustrative numbers only. Not a specific loan, not an offer."),
]


def cmp_html(t):
    for old, new in CMP_PAIRS + CMP_HTML_ONLY:
        t = rep(t, old, new)
    return t


def cmp_json(t):
    def f(s):
        for old, new in CMP_PAIRS:
            s = rep(s, old, new)
        return s
    a = t.index('"slug": "mezzanine-vs-preferred-equity"')
    b = t.find('"slug": "', a + 40)
    b = len(t) if b < 0 else b
    return t[:a] + f(t[a:b]) + t[b:]


# ----------------------------------------------------------------------------- discovery files
def blog_index(t):
    if GUIDE_SLUG in t:
        return t
    key = 'href="../blog/bridge-mezzanine-construction-loans-borrowers-guide.html" class="blog-card'
    a = t.index(key)
    end = "    </a>\n"
    b = t.index(end, a) + len(end)
    card = (
        f'    <a href="../blog/{GUIDE_SLUG}.html" class="blog-card reveal" data-cat="guides">\n'
        '      <div class="blog-card-hero" data-category="guides"></div>\n'
        '      <div class="blog-card-category">Guides</div>\n'
        f'      <h3 class="blog-card-title">{GUIDE_H1}</h3>\n'
        f'      <p class="blog-card-excerpt">{GUIDE_DESC}</p>\n'
        '      <div class="blog-card-meta">\n'
        '        <span>Commercial Lending Solutions</span>\n'
        '        <span>November 26, 2026</span>\n'
        '      </div>\n'
        '    </a>\n')
    return t[:b] + card + t[b:]


def sitemap(t):
    if GUIDE_SLUG in t:
        return t
    entry = (f"  <url>\n    <loc>{GUIDE_URL}</loc>\n    <lastmod>2026-11-27</lastmod>\n"
             "    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>\n")
    assert t.count("</urlset>") == 1
    return t.replace("</urlset>", entry + "</urlset>")


def llms(t):
    if GUIDE_SLUG in t:
        return t
    anchor = "- [Mezzanine and Preferred Equity](https://clscre.com/financing/mezzanine.html)\n"
    assert t.count(anchor) == 1, "llms anchor"
    line = (f"- [Commercial Real Estate Capital Stack Explained, With an Example]({GUIDE_URL}): "
            "Senior debt, mezzanine, preferred equity and common equity ranked by repayment priority, with a $100 million "
            "worked example and when to use each layer\n")
    return t.replace(anchor, anchor + line)


TRANSFORMS = {
    "financing/mezzanine.html": mezz_hub,
    "financing/preferred-equity.html": pref_hub,
    "_generator/data/loan_types.json": loan_types_json,
    "_generator/data/faqs.json": faqs_json,
    "_generator/data/glossary.json": glossary_json,
    "glossary/capital-stack.html": glossary_html("capital-stack"),
    "glossary/mezzanine-debt.html": glossary_html("mezzanine-debt"),
    "glossary/preferred-equity.html": glossary_html("preferred-equity"),
    "comparisons/mezzanine-vs-preferred-equity.html": cmp_html,
    "_generator/data/comparisons.json": cmp_json,
    "blog/index.html": blog_index,
    "sitemap-blog.xml": sitemap,
    "sitemap.xml": sitemap,
    "llms.txt": llms,
}


def apply_text(rel, text):
    """Line-ending and BOM safe wrapper around a transform."""
    bom = text.startswith("﻿")
    body = text[1:] if bom else text
    crlf = "\r\n" in body
    body = body.replace("\r\n", "\n")
    out = TRANSFORMS[rel](body)
    if crlf:
        out = out.replace("\n", "\r\n")
    return ("﻿" if bom else "") + out


def main():
    dry = "--dry-run" in sys.argv
    for rel in TRANSFORMS:
        p = WEBSITE / rel
        text = p.read_bytes().decode("utf-8")
        new = apply_text(rel, text)
        if new == text:
            print("unchanged:", rel)
            continue
        if not dry:
            p.write_bytes(new.encode("utf-8"))
        print(("would change" if dry else "changed") + f": {rel} ({len(text)} -> {len(new)})")


if __name__ == "__main__":
    main()
