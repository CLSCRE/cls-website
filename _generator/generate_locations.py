#!/usr/bin/env python
"""Render only the nationwide locations hub.

This entry point deliberately avoids the full-site generator so a locations
release cannot rewrite sitemaps, robots.txt, or unrelated rendered pages.
"""

import argparse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from generate import (
    DATA_DIR,
    TEMPLATE_DIR,
    TODAY,
    TODAY_HUMAN,
    WEBSITE_DIR,
    build_locations_hub_context,
    build_regional_groups,
    load_json,
    stamp_html_asset_versions,
)


DUPLICATE_CITY_SLUGS = {
    "greenville",
    "rockford",
    "oxnard",
    "albany-ny",
    "columbia-sc-2",
}


def active_cities():
    """Return the 242 canonical city authorities used by the main generator."""
    return [
        city
        for city in load_json("cities.json")
        if city["slug"] not in DUPLICATE_CITY_SLUGS
    ]


def render_locations_page(output_path=None):
    """Render the locations hub and write exactly one requested output file."""
    output_path = Path(output_path or WEBSITE_DIR / "locations.html")
    cities = active_cities()
    loan_types = load_json("loan_types.json")
    property_types = load_json("property_types.json")
    states = load_json("states.json")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("locations.html")
    shared = {
        "all_loan_types": loan_types,
        "all_property_types": property_types,
        "all_cities": cities,
        "regional_groups": build_regional_groups(cities),
        "total_market_count": len(cities),
        "current_date": TODAY,
        "current_date_human": TODAY_HUMAN,
        "has_glossary": (DATA_DIR / "glossary.json").exists(),
    }
    rendered = template.render(
        **shared,
        **build_locations_hub_context(cities, states, loan_types, property_types),
        seo={
            "title": "Commercial Real Estate Financing Locations | Commercial Lending Solutions",
            "meta_description": (
                "Commercial Lending Solutions provides commercial mortgage brokerage "
                f"in {len(cities)} major U.S. markets. Browse financing coverage by city and state."
            ),
        },
        canonical_path="locations.html",
        depth="",
    )
    rendered = stamp_html_asset_versions(rendered)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=WEBSITE_DIR / "locations.html",
        help="Output path; defaults to the production locations.html file.",
    )
    args = parser.parse_args()
    render_locations_page(args.output)
    print(f"[OK] generated only {args.output}")


if __name__ == "__main__":
    main()
