"""Mark evergreen informational pages as Article as well as WebPage (2026-11-26 SEO audit).

Ahrefs Site Audit ("Article page missing Article schema") flagged 61 pages whose
JSON-LD already carries a WebPage node with author, publisher and dateModified,
but is not typed as an Article. For those paths the WebPage node becomes
["WebPage", "Article"] and gets a headline (its own name). Nothing is invented:
author, publisher and dates are left exactly as the page already states them.

generate.py applies this at its write choke point so a regeneration keeps it.
apply_schema_rules.py applies it to the existing files.
"""
import json
import re

# Pages Ahrefs flagged on 2026-11-24 (website-relative paths).
ARTICLE_PATHS = frozenset("""
financing/permanent-loans.html financing/mezzanine.html financing/self-storage-financing.html
financing/senior-housing-financing.html resources/cre-financing-guide.html resources/welfare-exemption.html
financing/commercial-mortgage-rates.html comparisons/index.html financing/agency-loans.html accessibility.html
financing/multifamily-construction-loans.html financing/preferred-equity.html financing/hotel-motel-financing.html
financing/bridge-to-perm-loans.html financing/value-add-bridge-loans.html financing/multifamily-bridge-loans.html
financing/1031-exchange-bridge-loans.html financing/mixed-use-bridge-loans.html financing/acquisition-bridge-loans.html
financing/construction-to-perm-loans.html financing/multifamily-loans.html financing/middle-market-loans.html
blog/case-studies.html glossary/cash-on-cash-return.html markets/santa-barbara/index.html
financing/bridge-loan-rates.html financing/how-to-qualify-for-hard-money-loans.html
affordable-housing/edi-streamlined/index.html financing/how-to-qualify-for-bridge-to-perm-loans.html
financing/how-to-qualify-for-agency-loans.html financing/net-lease-loan-rates.html
research/lender-pricing-report-q1-2026.html financing/how-to-qualify-for-bridge-loans.html
financing/cmbs-loan-rates.html financing/hud-fha-loan-rates.html financing/how-to-qualify-for-construction-loans.html
financing/mezzanine-modesto.html affordable-housing/9pct-lihtc/index.html financing/how-to-qualify-for-mezzanine.html
financing/hard-money-loan-rates.html financing/how-to-qualify-for-life-company-loans.html
financing/bridge-to-perm-loan-rates.html affordable-housing/hud-221d4/index.html
professionals/opportunity-zone-advisors/index.html professionals/family-offices/index.html
research/methodology.html financing/construction-loan-rates.html affordable-housing/4pct-lihtc/index.html
financing/portfolio-loan-rates.html financing/how-to-qualify-for-permanent-loans.html
financing/life-company-loan-rates.html financing/how-to-qualify-for-cmbs-loans.html
financing/how-to-qualify-for-portfolio-loans.html financing/mezzanine-san-francisco.html
research/closed-deal-report-q1-2026.html financing/how-to-qualify-for-hud-fha-loans.html
research/lender-pricing-report-q2-2026-mid.html professionals/fiduciaries-probate/index.html
financing/agency-loan-rates.html financing/10-million-commercial-loan.html
financing/how-to-qualify-for-net-lease-financing.html
""".split())

_BLOCK = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)


def _upgrade(node):
    """Upgrade WebPage nodes in place. Return the number changed."""
    changed = 0
    if isinstance(node, dict):
        t = node.get("@type")
        if t == "WebPage":
            node["@type"] = ["WebPage", "Article"]
            if not node.get("headline") and node.get("name"):
                head = str(node["name"])
                for suffix in (" | Commercial Lending Solutions", " | CLS CRE"):
                    if head.endswith(suffix):
                        head = head[: -len(suffix)]
                node["headline"] = head[:110]
            changed += 1
        for v in node.values():
            changed += _upgrade(v)
    elif isinstance(node, list):
        for v in node:
            changed += _upgrade(v)
    return changed


def apply_to_html(html_text, rel_path):
    rel = rel_path.replace("\\", "/")
    if rel not in ARTICLE_PATHS:
        return html_text

    def fix(m):
        body = m.group(2)
        if '"WebPage"' not in body:
            return m.group(0)
        try:
            data = json.loads(body)
        except ValueError:
            return m.group(0)
        if not _upgrade(data):
            return m.group(0)
        return m.group(1) + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + m.group(3)

    return _BLOCK.sub(fix, html_text)
