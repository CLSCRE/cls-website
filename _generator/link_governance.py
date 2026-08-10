#!/usr/bin/env python3
"""Internal link governance for Commercial Lending Solutions.

Only sitemap-active destinations are linkable. Retired/noindex/redirect-source
URLs are resolved to the best active authority:

1. redirect_map target (already protect-equity curated)
2. city market hub markets/{city}/ for geo permutations
3. national program/property hub
4. locations.html / blog/ / apply.html as last resorts

Used by generators and the one-shot active-page rewrite.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

GENERATOR_DIR = Path(__file__).resolve().parent
DATA_DIR = GENERATOR_DIR / "data"
WEBSITE_DIR = GENERATOR_DIR.parent

DUPLICATE_CITY_SLUGS = frozenset(
    {"greenville", "rockford", "oxnard", "albany-ny", "columbia-sc-2"}
)


def _load_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8-sig"))


def normalize_path(path: str) -> str:
    path = (path or "").split("?")[0].split("#")[0].replace("\\", "/").lstrip("/")
    if path == "" or path.endswith("/"):
        path = f"{path}index.html"
    return path


def url_to_path(url_or_path: str) -> str:
    raw = (url_or_path or "").strip()
    if raw.startswith("http"):
        raw = urlparse(raw).path
    return normalize_path(raw)


def path_variants(path: str) -> set[str]:
    d = normalize_path(path)
    out = {d}
    if d.endswith(".html"):
        out.add(d[: -len(".html")])
        if d.endswith("/index.html"):
            out.add(d[: -len("index.html")])
    else:
        out.add(d + ".html")
        out.add(d.rstrip("/") + "/index.html")
    return {x.lstrip("/") for x in out if x}


def public_href(path: str, depth: str = "") -> str:
    """Return site-relative href preferred for templates."""
    p = normalize_path(path)
    if p.endswith("/index.html"):
        rel = p[: -len("index.html")]  # keeps trailing slash
    else:
        rel = p
    if depth:
        return f"{depth}{rel}"
    return rel if rel.startswith(("http://", "https://", "/")) else rel


class LinkGovernor:
    def __init__(self, website_dir: Path | None = None):
        self.website_dir = Path(website_dir or WEBSITE_DIR)
        self.loan_slugs = sorted(
            {row["slug"] for row in _load_json("loan_types.json")},
            key=len,
            reverse=True,
        )
        self.property_slugs = sorted(
            {row["slug"] for row in _load_json("property_types.json")},
            key=len,
            reverse=True,
        )
        self.city_slugs = sorted(
            {
                row["slug"]
                for row in _load_json("cities.json")
                if row["slug"] not in DUPLICATE_CITY_SLUGS
            },
            key=len,
            reverse=True,
        )
        self.city_by_slug = {
            row["slug"]: row
            for row in _load_json("cities.json")
            if row["slug"] not in DUPLICATE_CITY_SLUGS
        }
        self.loan_by_slug = {row["slug"]: row for row in _load_json("loan_types.json")}
        self.property_by_slug = {
            row["slug"]: row for row in _load_json("property_types.json")
        }

        noindex_raw = _load_json("noindex_paths.json")
        self.noindex = set(noindex_raw if isinstance(noindex_raw, list) else noindex_raw)

        redir_raw = _load_json("redirect_map.json")
        self.redirects: dict[str, str] = {}
        if isinstance(redir_raw, dict):
            for src, dst in redir_raw.items():
                if isinstance(dst, str):
                    self.redirects[normalize_path(src)] = url_to_path(dst)
        self.redirect_sources = set(self.redirects)

        self.active = self._load_active()

    def _load_active(self) -> set[str]:
        active: set[str] = set()
        for sm in self.website_dir.glob("sitemap*.xml"):
            text = sm.read_text(encoding="utf-8", errors="ignore")
            for loc in re.findall(r"<loc>(.*?)</loc>", text):
                active.add(normalize_path(urlparse(loc).path))
        # Always treat core conversion/authority pages as active if present on disk
        for core in (
            "index.html",
            "locations.html",
            "apply.html",
            "rates.html",
            "track-record.html",
            "about.html",
            "contact.html",
            "thank-you.html",
            "privacy.html",
            "terms.html",
            "disclaimer.html",
            "accessibility.html",
            "partners.html",
            "refinance.html",
            "refi-check.html",
            "market-data.html",
            "llms.txt",
        ):
            if (self.website_dir / core).exists():
                active.add(core)
        return active

    def is_active(self, path: str) -> bool:
        return bool(path_variants(path) & self.active)

    def is_contentish(self, path: str) -> bool:
        p = normalize_path(path)
        if p.endswith(".html") and "/" not in p:
            return True
        prefixes = (
            "financing/", "property/", "markets/", "blog/", "commercial/",
            "affordable-housing/", "tools/", "states/", "life-company",
            "data-centers/", "loan-size/", "comparisons/", "senior-living/",
            "self-storage/", "medical-office/", "industrial/", "multifamily/",
            "los-angeles/", "retail/", "submit-deal", "broker-portal",
            "about/", "insights/", "resources/", "glossary/", "research/",
            "case-studies/", "transactions", "capital-markets/", "legislative",
        )
        return p.startswith(prefixes)

    def is_forbidden_dest(self, path: str) -> bool:
        """Only retire known content destinations; never touch booking/widgets/assets."""
        if not self.is_contentish(path):
            return False
        vs = path_variants(path)
        if vs & self.redirect_sources:
            return True
        if vs & self.noindex:
            return True
        return not self.is_active(path)

    def canonical_active_path(self, path: str) -> str | None:
        for v in path_variants(path):
            if v in self.active:
                return v
            if not v.endswith(".html") and f"{v}/index.html" in self.active:
                return f"{v}/index.html"
        return None

    def _parse_financing_city(self, path: str) -> tuple[str, str] | None:
        p = normalize_path(path)
        if not p.startswith("financing/") or not p.endswith(".html"):
            return None
        name = p[len("financing/") : -len(".html")]
        for loan in self.loan_slugs:
            prefix = f"{loan}-"
            if name.startswith(prefix):
                city = name[len(prefix) :]
                if city in self.city_by_slug:
                    return loan, city
        return None

    def _parse_property_city(self, path: str) -> tuple[str, str] | None:
        p = normalize_path(path)
        if not p.startswith("property/") or not p.endswith(".html"):
            return None
        name = p[len("property/") : -len(".html")]
        for prop in self.property_slugs:
            prefix = f"{prop}-"
            if name.startswith(prefix):
                city = name[len(prefix) :]
                if city in self.city_by_slug:
                    return prop, city
        return None

    def resolve(self, path: str, source_path: str | None = None) -> str | None:
        """Return an active destination path, or None if link should be dropped."""
        path = normalize_path(path)
        source = normalize_path(source_path) if source_path else None

        # Already good
        if not self.is_forbidden_dest(path):
            canon = self.canonical_active_path(path) or path
            if source and normalize_path(canon) == source:
                return None
            return canon

        # Explicit redirect map (protect-equity)
        for v in path_variants(path):
            if v in self.redirects:
                target = self.redirects[v]
                if not self.is_forbidden_dest(target):
                    canon = self.canonical_active_path(target) or target
                    if source and normalize_path(canon) == source:
                        # avoid self-loop; try national fallbacks below
                        break
                    return canon

        candidates: list[str] = []

        fin = self._parse_financing_city(path)
        if fin:
            loan, city = fin
            candidates.extend(
                [
                    f"markets/{city}/index.html",
                    f"financing/{loan}.html",
                ]
            )

        prop = self._parse_property_city(path)
        if prop:
            pslug, city = prop
            candidates.extend(
                [
                    f"markets/{city}/index.html",
                    f"property/{pslug}.html",
                ]
            )

        # Specialty vertical geo pages. Match the longest known city slug so
        # disambiguated markets such as portland-me do not collapse to portland.
        m = re.match(
            r"^(self-storage|senior-living|medical-office|data-centers|affordable-housing|commercial|industrial|multifamily)/markets/(.+)\.html$",
            path,
        )
        if m:
            vertical, tail = m.group(1), m.group(2)
            city = next(
                (
                    slug
                    for slug in sorted(self.city_by_slug, key=len, reverse=True)
                    if tail == slug or tail.startswith(f"{slug}-")
                ),
                None,
            )
            if city:
                candidates.append(f"markets/{city}/index.html")
            vertical_hub = {
                "self-storage": "property/self-storage.html",
                "senior-living": "property/senior-living.html",
                "medical-office": "property/medical-office.html",
                "data-centers": "property/data-centers.html",
                "affordable-housing": "financing/affordable-housing-loans.html",
                "commercial": None,
                "industrial": "property/industrial.html",
                "multifamily": "property/multifamily.html",
            }.get(vertical)
            if vertical_hub:
                candidates.append(vertical_hub)

        if path.startswith("blog/"):
            candidates.extend(["blog/index.html", "blog/"])

        if path in {"submit-deal.html", "broker-portal.html"}:
            candidates.append("apply.html")

        seen: set[str] = set()
        for cand in candidates:
            cand_n = normalize_path(cand)
            if cand_n in seen:
                continue
            seen.add(cand_n)
            if self.is_forbidden_dest(cand_n):
                continue
            canon = self.canonical_active_path(cand_n) or cand_n
            if source and normalize_path(canon) == source:
                continue
            return canon
        return None

    def market_links_for_program(
        self, loan_slug: str, limit: int = 15
    ) -> list[dict]:
        """Curated market chips for financing hubs."""
        links = []
        for city in sorted(
            self.city_by_slug.values(),
            key=lambda c: (
                0
                if c["slug"]
                in {
                    "los-angeles",
                    "new-york",
                    "chicago",
                    "dallas",
                    "houston",
                    "miami",
                    "atlanta",
                    "phoenix",
                    "denver",
                    "seattle",
                    "san-francisco",
                    "san-diego",
                    "boston",
                    "tampa",
                    "nashville",
                }
                else 1,
                c["city"],
            ),
        ):
            preferred = f"financing/{loan_slug}-{city['slug']}.html"
            resolved = self.resolve(preferred)
            if not resolved:
                continue
            # Prefer market hub presentation when city program page is gone
            href_path = resolved
            links.append(
                {
                    "city": city["city"],
                    "state": city["state"],
                    "slug": city["slug"],
                    "path": href_path,
                    "href_suffix": public_href(href_path, depth=""),
                }
            )
            if len(links) >= limit:
                break
        return links

    def market_links_for_property(self, prop_slug: str, limit: int = 15) -> list[dict]:
        links = []
        for city in sorted(
            self.city_by_slug.values(),
            key=lambda c: (
                0
                if c["slug"]
                in {
                    "los-angeles",
                    "new-york",
                    "chicago",
                    "dallas",
                    "houston",
                    "miami",
                    "atlanta",
                    "phoenix",
                    "denver",
                    "seattle",
                    "san-francisco",
                    "san-diego",
                    "boston",
                    "tampa",
                    "nashville",
                }
                else 1,
                c["city"],
            ),
        ):
            preferred = f"property/{prop_slug}-{city['slug']}.html"
            resolved = self.resolve(preferred)
            if not resolved:
                continue
            links.append(
                {
                    "city": city["city"],
                    "state": city["state"],
                    "slug": city["slug"],
                    "path": resolved,
                    "href_suffix": public_href(resolved, depth=""),
                }
            )
            if len(links) >= limit:
                break
        return links

    def neighborhood_links_for_city(
        self, city_slug: str, neighborhoods: list[dict]
    ) -> list[dict]:
        """Return only active neighborhood pages; never relabel a generic fallback."""
        out = []
        seen: set[str] = set()
        for neighborhood in neighborhoods:
            preferred = f"markets/{city_slug}/{neighborhood['slug']}.html"
            if (
                preferred in seen
                or not self.is_active(preferred)
                or self.is_forbidden_dest(preferred)
            ):
                continue
            seen.add(preferred)
            out.append(
                {
                    **neighborhood,
                    "path": preferred,
                    "href_suffix": public_href(preferred, depth=""),
                }
            )
        return out

    def program_links_for_city(
        self, city_slug: str, exclude_loan: str | None = None
    ) -> list[dict]:
        out = []
        seen: set[str] = set()
        source = f"markets/{city_slug}/index.html"
        for loan_slug, loan in self.loan_by_slug.items():
            if exclude_loan and loan_slug == exclude_loan:
                continue
            preferred = f"financing/{loan_slug}-{city_slug}.html"
            resolved = self.resolve(preferred, source_path=source)
            if not resolved:
                # fall back to national program hub
                resolved = self.resolve(
                    f"financing/{loan_slug}.html", source_path=source
                )
            if not resolved or resolved == "locations.html" or resolved in seen:
                continue
            seen.add(resolved)
            out.append(
                {
                    "name": loan["name"],
                    "slug": loan_slug,
                    "path": resolved,
                    "href_suffix": public_href(resolved, depth=""),
                }
            )
        return out

    def property_links_for_city(self, city_slug: str) -> list[dict]:
        out = []
        seen: set[str] = set()
        source = f"markets/{city_slug}/index.html"
        for prop_slug, prop in self.property_by_slug.items():
            preferred = f"property/{prop_slug}-{city_slug}.html"
            resolved = self.resolve(preferred, source_path=source) or self.resolve(
                f"property/{prop_slug}.html", source_path=source
            )
            if not resolved or resolved == "locations.html" or resolved in seen:
                continue
            seen.add(resolved)
            out.append(
                {
                    "name": prop["name"],
                    "slug": prop_slug,
                    "path": resolved,
                    "href_suffix": public_href(resolved, depth=""),
                }
            )
        return out


    def specialty_links_for_city(self, city_slug: str) -> list[dict]:
        city = self.city_by_slug.get(city_slug) or {"city": city_slug, "state": ""}
        source = f"markets/{city_slug}/index.html"
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
        seen: set[str] = set()
        for preferred, name, subtitle, fallback in specs:
            if self.is_active(preferred) and not self.is_forbidden_dest(preferred):
                resolved = self.canonical_active_path(preferred) or preferred
            else:
                resolved = self.resolve(fallback, source_path=source)
            if not resolved or resolved == "locations.html" or resolved in seen:
                continue
            seen.add(resolved)
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

    def case_studies_for(self, *, loan_slug: str | None = None,
                         property_slug: str | None = None,
                         city_slug: str | None = None,
                         limit: int = 3, depth: str = "") -> list[dict]:
        """Closed-deal case studies that prove a given program, property type, or city.

        Feeds the "Deals We Have Closed" block on the financing and property
        hubs. Sorted by loan amount descending, so the biggest, most credible
        deal leads.

        Why this exists: on 2026-08-09 the 68 published case studies were found
        with exactly ONE inbound internal link each (the hub page). Zero of the
        10,318 financing pages and zero property pages linked to any of them,
        which is the same starved-link-graph pattern that left the LA broker hub
        with zero GSC impressions for six weeks. This gives each case study real
        equity from pages Google already indexes, and simultaneously puts closing
        proof on the money pages.

        Returns [] when nothing matches, so templates guard with {% if %}.
        """
        # Defensive: this index is a generated artifact (see
        # scripts/build_case_study_index.py). A missing or malformed file must
        # degrade to "no case-study links", never break a 23k-page build.
        try:
            index = _load_json("case_study_index.json") or []
        except (OSError, ValueError):
            return []
        out = []
        for rec in index:
            if loan_slug and loan_slug not in rec.get("loan_slugs", []):
                continue
            if property_slug and property_slug not in rec.get("property_slugs", []):
                continue
            if city_slug and rec.get("city_slug") != city_slug:
                continue
            path = f"blog/{rec['slug']}.html"
            if not self.is_active(path):
                continue
            out.append({
                "title": rec["title"],
                "amount": rec.get("amount_display", ""),
                "location": rec.get("location", ""),
                "href": public_href(path, depth=depth),
            })
            if len(out) >= limit:
                break
        return out

    def broker_hub_href_for_city(self, city_slug: str, depth: str = "") -> str | None:
        """Href for a metro broker-hire hub, or None if that city has no hub.

        These are the hand-built `financing/commercial-mortgage-broker-{city}.html`
        pages (currently Los Angeles only) that target broker-HIRE intent
        ("commercial mortgage broker los angeles") rather than product intent
        ("commercial mortgage loans los angeles", which
        commercial_mortgage_href_for_city already covers). Keep the two separate:
        they answer different queries.

        Returns None when no hub exists, so templates can wrap the link in a
        simple `{% if %}` and any future metro hub lights up automatically
        without touching a template again.

        Why this exists: on 2026-08-09 the LA hub was found with ~2 internal
        inlinks across a 23,800-page site and ZERO GSC impressions in 90 days,
        while the homepage absorbed its terms at position 22. It was indexable
        and in the sitemap; it simply had no internal link equity.
        """
        resolved = self.resolve(f"financing/commercial-mortgage-broker-{city_slug}.html")
        return public_href(resolved, depth=depth) if resolved else None

    def featured_cross_link(self, family: str, slug: str, city_slug: str) -> str:
        preferred = f"{family}/{slug}-{city_slug}.html"
        resolved = self.resolve(preferred)
        if resolved:
            return public_href(resolved, depth="../")
        market = self.resolve(f"markets/{city_slug}/index.html")
        if market:
            return public_href(market, depth="../")
        return "../locations.html"


@lru_cache(maxsize=1)
def get_governor() -> LinkGovernor:
    return LinkGovernor()
