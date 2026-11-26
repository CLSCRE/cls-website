import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from title_rules import apply_to_html, in_scope, shorten_title  # noqa: E402


def test_short_base_keeps_full_suffix():
    t = "LTV Calculator | Commercial Lending Solutions"
    assert shorten_title(t) == t


def test_medium_base_uses_short_suffix():
    base = "What Is Debt Yield? Formula and Lender Minimums"  # 47 chars
    assert shorten_title(base + " | Commercial Lending Solutions") == base + " | CLS CRE"


def test_long_base_drops_suffix():
    base = "Commercial Real Estate Loans in Downtown Los Angeles, California Guide"
    assert shorten_title(base + " | Commercial Lending Solutions") == base


def test_no_suffix_is_untouched():
    t = "Some Page With No Brand Suffix at All Even If It Is Quite Long Indeed Yes"
    assert shorten_title(t) == t


def test_entities_counted_as_one_character():
    base = "A &amp; B Loans for Everyone Who Wants Financing Today"  # 51 chars unescaped
    out = shorten_title(base + " | Commercial Lending Solutions")
    assert out.endswith(" | CLS CRE")


def test_scope_and_protected_paths():
    assert in_scope("glossary/debt-yield.html")
    assert not in_scope("blog/anything.html")
    assert not in_scope("markets/san-luis-obispo/downtown-slo.html")


def test_apply_rewrites_all_three_tags_and_not_json_ld():
    base = "What Is Debt Yield? Formula and Lender Minimums"
    full = base + " | Commercial Lending Solutions"
    page = (
        f"<title>{full}</title>"
        f'<meta property="og:title" content="{full}">'
        f'<meta name="twitter:title" content="{full}">'
        f'<script type="application/ld+json">{{"name":"{full}"}}</script>'
    )
    out = apply_to_html(page, "glossary/debt-yield.html")
    assert out.count(base + " | CLS CRE") == 3
    assert f'"name":"{full}"' in out
    assert apply_to_html(page, "blog/x.html") == page
