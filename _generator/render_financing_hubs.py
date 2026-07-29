#!/usr/bin/env python
"""Render financing-program hub pages without regenerating the full site."""

import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

SCRIPT_DIR = Path(__file__).resolve().parent
WEBSITE_DIR = SCRIPT_DIR.parent
DATA_DIR = SCRIPT_DIR / "data"
TEMPLATE_DIR = SCRIPT_DIR / "templates"

sys.path.insert(0, str(SCRIPT_DIR))
from generate import (  # noqa: E402
    TODAY,
    TODAY_HUMAN,
    build_regional_groups,
    filter_transactions,
    stamp_html_asset_versions,
)

DUPLICATE_CITY_SLUGS = {
    "greenville",
    "rockford",
    "oxnard",
    "albany-ny",
    "columbia-sc-2",
}


def load_json(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8-sig"))


def render_hubs(slugs=None, write=True):
    loans = load_json("loan_types.json")
    properties = load_json("property_types.json")
    cities = [
        city
        for city in load_json("cities.json")
        if city["slug"] not in DUPLICATE_CITY_SLUGS
    ]
    transactions = load_json("transactions.json")
    faqs_data = load_json("faqs.json")

    requested = set(slugs or [loan["slug"] for loan in loans])
    unknown = requested - {loan["slug"] for loan in loans}
    if unknown:
        raise ValueError(f"Unknown financing slug(s): {', '.join(sorted(unknown))}")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("financing_conversion_page.html")
    rendered = {}

    for loan in loans:
        if loan["slug"] not in requested:
            continue
        html = template.render(
            all_loan_types=loans,
            all_property_types=properties,
            all_cities=cities,
            regional_groups=build_regional_groups(cities),
            total_market_count=len(cities),
            current_date=TODAY,
            current_date_human=TODAY_HUMAN,
            has_glossary=(DATA_DIR / "glossary.json").exists(),
            loan=loan,
            seo=loan["seo"],
            canonical_path=f"financing/{loan['slug']}.html",
            depth="../",
            transactions=filter_transactions(transactions, loan_slug=loan["slug"]),
            faqs=faqs_data.get("loan_types", {}).get(loan["slug"], []),
            related_articles=[],
        )
        html = html.replace("\u2013", "-").replace("\u2014", "-")
        html = stamp_html_asset_versions(html)
        rendered[loan["slug"]] = html
        if write:
            output = WEBSITE_DIR / "financing" / f"{loan['slug']}.html"
            output.write_text(html, encoding="utf-8")
            print(f"Rendered {output} ({len(html):,} characters)")

    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        help="Render one financing slug; repeat to render multiple. Default: all hubs.",
    )
    args = parser.parse_args()
    render_hubs(slugs=args.slugs, write=True)


if __name__ == "__main__":
    main()
