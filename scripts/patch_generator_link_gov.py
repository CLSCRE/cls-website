#!/usr/bin/env python3
"""Patch generate.py + link_governance.py for governed internal links."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
gov_path = ROOT / "_generator" / "link_governance.py"
gen_path = ROOT / "_generator" / "generate.py"

gov = gov_path.read_text(encoding="utf-8")
if "specialty_links_for_city" not in gov:
    needle = "    def featured_cross_link(self, family: str, slug: str, city_slug: str) -> str:"
    insert = '''
    def specialty_links_for_city(self, city_slug: str) -> list[dict]:
        city = self.city_by_slug.get(city_slug) or {"city": city_slug, "state": ""}
        specs = [
            (
                f"self-storage/markets/{city_slug}-climate-controlled.html",
                "Self-Storage Financing",
                f"{city.get('city')}: Climate-Controlled, Drive-Up, Multi-Story",
                "property/self-storage.html",
            ),
            (
                f"senior-living/markets/{city_slug}-assisted-living.html",
                "Senior Living Financing",
                f"{city.get('city')}: Assisted Living, Memory Care, Independent",
                "property/senior-living.html",
            ),
            (
                f"medical-office/markets/{city_slug}-off-campus-mob.html",
                "Medical Office Financing",
                f"{city.get('city')}: On-Campus, Off-Campus, Surgery Centers",
                "property/medical-office.html",
            ),
            (
                f"data-centers/markets/{city_slug}-colocation.html",
                "Data Center Financing",
                f"{city.get('city')}: Colocation, Hyperscale, Edge Computing",
                "property/data-centers.html",
            ),
        ]
        out = []
        for preferred, name, subtitle, fallback in specs:
            resolved = self.resolve(preferred) or self.resolve(fallback) or self.resolve(
                f"markets/{city_slug}/index.html"
            )
            if not resolved:
                continue
            out.append(
                {
                    "name": name,
                    "subtitle": subtitle,
                    "path": resolved,
                    "href_suffix": public_href(resolved, depth=""),
                }
            )
        return out

    def commercial_mortgage_href_for_city(self, city_slug: str) -> str:
        preferred = f"financing/commercial-mortgage-loans-{city_slug}.html"
        resolved = (
            self.resolve(preferred)
            or self.resolve("financing/commercial-mortgage-loans.html")
            or self.resolve(f"markets/{city_slug}/index.html")
            or "locations.html"
        )
        return public_href(resolved, depth="")

'''
    if needle not in gov:
        raise SystemExit("featured_cross_link missing")
    gov = gov.replace(needle, insert + needle)
    gov_path.write_text(gov, encoding="utf-8")
    print("link_governance specialty helpers added")
else:
    print("link_governance already has specialty helpers")

t = gen_path.read_text(encoding="utf-8")
if "from link_governance import LinkGovernor" not in t:
    t = t.replace(
        "from jinja2 import Environment, FileSystemLoader\n",
        "from jinja2 import Environment, FileSystemLoader\nfrom link_governance import LinkGovernor\n",
    )
    print("import added")

if "link_gov = LinkGovernor" not in t:
    marker = 'print(f"  [redirect] {len(REDIRECT_PATHS)} paths emit redirect stubs")\n'
    if marker not in t:
        raise SystemExit("redirect marker missing")
    t = t.replace(
        marker,
        marker
        + "    link_gov = LinkGovernor(WEBSITE_DIR)\n"
        + '    print(f"  [link-gov] active={len(link_gov.active)} noindex={len(link_gov.noindex)} redirects={len(link_gov.redirects)}")\n',
    )
    print("link_gov init added")

# featured market cross links - use regex for flexible whitespace
def sub_cross(family: str, var: str, text: str) -> str:
    pat = rf'("cross_link_url":\s*)f"\.\./{family}/\{{\s*{var}\[\'slug\'\]\s*\}}-\{{c\[\'slug\'\]\}}\.html"'
    repl = rf'\1link_gov.featured_cross_link("{family}", {var}["slug"], c["slug"])'
    new, n = re.subn(pat, repl, text)
    print(family, "cross replacements", n)
    return new

t = sub_cross("financing", "loan", t)
t = sub_cross("property", "prop", t)

# city financing render injection
if "program_links_for_city=link_gov.program_links_for_city(city" not in t:
    t = t.replace(
        "la_deepdive=la_financing_deepdive.get(loan[\"slug\"]),\n            )",
        "la_deepdive=la_financing_deepdive.get(loan[\"slug\"]),\n"
        "                program_links_for_city=link_gov.program_links_for_city(city[\"slug\"], exclude_loan=loan[\"slug\"]),\n"
        "                property_links_for_city=link_gov.property_links_for_city(city[\"slug\"]),\n"
        "            )",
    )
    print("city_fin vars")
if "la_property_deepdive.get(prop[\"slug\"]),\n                program_links_for_city" not in t:
    t = t.replace(
        "la_deepdive=la_property_deepdive.get(prop[\"slug\"]),\n            )",
        "la_deepdive=la_property_deepdive.get(prop[\"slug\"]),\n"
        "                program_links_for_city=link_gov.program_links_for_city(city[\"slug\"]),\n"
        "                property_links_for_city=[\n"
        "                    x for x in link_gov.property_links_for_city(city[\"slug\"]) if x[\"slug\"] != prop[\"slug\"]\n"
        "                ],\n"
        "            )",
    )
    print("city_prop vars")

# market index
if "specialty_links_for_city=link_gov.specialty_links_for_city" not in t:
    t = t.replace(
        "html = tpl_market_index.render(\n            **shared,\n            city=city,",
        "html = tpl_market_index.render(\n            **shared,\n            city=city,\n"
        "            program_links_for_city=link_gov.program_links_for_city(city[\"slug\"]),\n"
        "            property_links_for_city=link_gov.property_links_for_city(city[\"slug\"]),\n"
        "            specialty_links_for_city=link_gov.specialty_links_for_city(city[\"slug\"]),\n"
        "            commercial_mortgage_href=link_gov.commercial_mortgage_href_for_city(city[\"slug\"]),",
    )
    print("market index vars")

# financing hubs in full generate
if "market_links=link_gov.market_links_for_program" not in t:
    t = t.replace(
        "related_articles=rel_articles,\n        )",
        "related_articles=rel_articles,\n"
        "            market_links=link_gov.market_links_for_program(loan[\"slug\"], limit=15),\n"
        "        )",
        1,
    )
    print("financing hub market_links")

if "market_links=link_gov.market_links_for_property" not in t:
    # property hub block ends with financing_links list then )
    t = t.replace(
        "for label in prop[\"financing_options\"]\n            ],\n        )",
        "for label in prop[\"financing_options\"]\n            ],\n"
        "            market_links=link_gov.market_links_for_property(prop[\"slug\"], limit=15),\n"
        "        )",
        1,
    )
    print("property hub market_links")

gen_path.write_text(t, encoding="utf-8")
print("generate.py patched")
