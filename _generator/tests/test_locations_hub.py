import json
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


GENERATOR_DIR = Path(__file__).resolve().parents[1]
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))


def test_targeted_generator_writes_only_requested_locations_file(tmp_path):
    from generate_locations import render_locations_page

    output = tmp_path / "locations.html"
    rendered = render_locations_page(output)

    assert output.read_text(encoding="utf-8") == rendered
    assert [path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")] == [
        "locations.html"
    ]
    assert "Commercial Lending Solutions" in rendered


def _internal_path(href):
    parsed = urlparse(urljoin("https://clscre.com/locations.html", href))
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc not in ("", "clscre.com", "www.clscre.com"):
        return None
    path = parsed.path.lstrip("/")
    if not path:
        return "index.html"
    return f"{path}index.html" if path.endswith("/") else path


def test_hub_links_every_authority_without_noindex_or_redirect_destinations(tmp_path):
    from generate_locations import DUPLICATE_CITY_SLUGS, render_locations_page

    rendered = render_locations_page(tmp_path / "locations.html")
    soup = BeautifulSoup(rendered, "html.parser")
    hrefs = [anchor["href"] for anchor in soup.find_all("a", href=True)]
    internal_paths = {
        path for href in hrefs if (path := _internal_path(href)) is not None
    }

    cities = json.loads((GENERATOR_DIR / "data" / "cities.json").read_text(encoding="utf-8"))
    states = json.loads((GENERATOR_DIR / "data" / "states.json").read_text(encoding="utf-8"))
    noindex = set(
        json.loads((GENERATOR_DIR / "data" / "noindex_paths.json").read_text(encoding="utf-8"))
    )
    redirects = json.loads(
        (GENERATOR_DIR / "data" / "redirect_map.json").read_text(encoding="utf-8")
    )

    city_authorities = {
        f"markets/{city['slug']}/index.html"
        for city in cities
        if city["slug"] not in DUPLICATE_CITY_SLUGS
    }
    state_authorities = {f"states/{state['slug']}.html" for state in states}

    assert len(city_authorities) == 242
    assert city_authorities <= internal_paths
    assert len(state_authorities) == 51
    assert state_authorities <= internal_paths
    assert "states/index.html" in internal_paths
    assert len(hrefs) < 500
    assert not (internal_paths & noindex)
    assert not (internal_paths & set(redirects))

    sitemap_text = (GENERATOR_DIR.parent / "sitemap.xml").read_text(encoding="utf-8-sig")
    sitemap_paths = {
        _internal_path(url.get_text(strip=True))
        for url in BeautifulSoup(sitemap_text, "xml").find_all("loc")
    }
    assert internal_paths <= sitemap_paths


def test_hub_is_compact_deterministic_and_has_valid_seo_structure(tmp_path):
    from generate_locations import render_locations_page

    first = render_locations_page(tmp_path / "first" / "locations.html")
    second = render_locations_page(tmp_path / "second" / "locations.html")
    soup = BeautifulSoup(first, "html.parser")

    assert first == second
    assert len(first.encode("utf-8")) < 200_000
    assert len(soup.find_all(True)) < 2_000
    assert len(soup.find_all("h1")) == 1
    assert not soup.find("meta", attrs={"name": "robots", "content": lambda value: value and "noindex" in value})
    assert soup.find("link", rel="canonical")["href"] == "https://clscre.com/locations.html"
    assert soup.find("label", attrs={"for": "market-search"})
    assert soup.find("label", attrs={"for": "state-filter"})
    assert soup.find(id="market-results", attrs={"role": "status", "aria-live": "polite"})
    assert soup.find(id="market-reset", attrs={"type": "button"})
