#!/usr/bin/env python
"""Render top-level property financing hubs without regenerating city pages."""

import argparse
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

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


def financing_slug(label):
    normalized = label.lower()
    rules = (
        ("agency", "agency-loans"),
        ("hud", "hud-fha-loans"),
        ("life insurance", "life-company-loans"),
        ("life company", "life-company-loans"),
        ("cmbs", "cmbs-loans"),
        ("sba", "sba-loans"),
        ("mezzanine", "mezzanine"),
        ("preferred equity", "preferred-equity"),
        ("c-pace", "cpace-financing"),
        ("value-add", "value-add-bridge-loans"),
        ("bridge", "bridge-loans"),
        ("construction-to-perm", "construction-to-perm-loans"),
        ("construction", "construction-loans"),
        ("bank permanent", "permanent-loans"),
        ("specialty", "specialty"),
        ("infrastructure", "specialty"),
    )
    return next((slug for needle, slug in rules if needle in normalized), "commercial-mortgage-loans")


def render_hubs(slugs=None, write=True):
    properties = load_json("property_types.json")
    loans = load_json("loan_types.json")
    cities = [
        city
        for city in load_json("cities.json")
        if city["slug"] not in DUPLICATE_CITY_SLUGS
    ]
    transactions = load_json("transactions.json")
    faqs_data = load_json("faqs.json")

    requested = set(slugs or [prop["slug"] for prop in properties])
    unknown = requested - {prop["slug"] for prop in properties}
    if unknown:
        raise ValueError(f"Unknown property slug(s): {', '.join(sorted(unknown))}")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    template = env.get_template("property_conversion_page.html")
    rendered = {}

    for prop in properties:
        if prop["slug"] not in requested:
            continue
        links = [
            {"label": label, "slug": financing_slug(label)}
            for label in prop["financing_options"]
        ]
        html = template.render(
            all_loan_types=loans,
            all_property_types=properties,
            all_cities=cities,
            regional_groups=build_regional_groups(cities),
            total_market_count=len(cities),
            current_date=TODAY,
            current_date_human=TODAY_HUMAN,
            has_glossary=(DATA_DIR / "glossary.json").exists(),
            prop=prop,
            seo=prop["seo"],
            canonical_path=f"property/{prop['slug']}.html",
            depth="../",
            transactions=filter_transactions(transactions, prop_slug=prop["slug"]),
            faqs=faqs_data.get("property_types", {}).get(prop["slug"], []),
            financing_links=links,
        )
        html = html.replace("\u2013", "-").replace("\u2014", "-")
        html = stamp_html_asset_versions(html)
        rendered[prop["slug"]] = html
        if write:
            output = WEBSITE_DIR / "property" / f"{prop['slug']}.html"
            output.write_text(html, encoding="utf-8")
            print(f"Rendered {output} ({len(html):,} characters)")

    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        help="Render one property slug; repeat for multiple. Default: all hubs.",
    )
    args = parser.parse_args()
    render_hubs(slugs=args.slugs, write=True)


if __name__ == "__main__":
    main()
