#!/usr/bin/env python3
"""Baseline/after measure of internal links into non-active destinations."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)

PREFIXES = (
    "financing/",
    "property/",
    "markets/",
    "blog/",
    "commercial/",
    "affordable-housing/",
    "tools/",
    "states/",
    "life-company",
    "data-centers/",
    "loan-size/",
    "comparisons/",
    "senior-living/",
    "self-storage/",
    "medical-office/",
    "industrial/",
    "multifamily/",
    "los-angeles/",
    "submit-deal",
    "broker-portal",
    "locations.html",
    "apply.html",
    "rates.html",
    "track-record.html",
)


def load_json(name: str):
    return json.loads((ROOT / "_generator" / "data" / name).read_text(encoding="utf-8"))


def load_active() -> set[str]:
    active: set[str] = set()
    for sm in ROOT.glob("sitemap*.xml"):
        text = sm.read_text(encoding="utf-8", errors="ignore")
        for loc in re.findall(r"<loc>(.*?)</loc>", text):
            path = urlparse(loc).path.lstrip("/")
            if path == "" or path.endswith("/"):
                path = f"{path}index.html"
            active.add(path)
    return active


def load_noindex():
    raw = load_json("noindex_paths.json")
    if isinstance(raw, list):
        return set(raw)
    if isinstance(raw, dict):
        # list-like dict or path->meta
        if all(isinstance(v, (str, dict, bool, type(None))) for v in raw.values()):
            return set(raw.keys())
        return set(raw)
    return set()


def load_redirects() -> dict[str, str]:
    raw = load_json("redirect_map.json")
    if isinstance(raw, dict):
        # path -> target url/path
        out = {}
        for k, v in raw.items():
            if isinstance(v, str):
                out[k] = v
            elif isinstance(v, dict):
                out[k] = v.get("to") or v.get("target") or ""
        return {k: v for k, v in out.items() if k and v}
    out = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        src = row.get("from") or row.get("source") or row.get("path")
        dst = row.get("to") or row.get("target")
        if src and dst:
            out[src] = dst
    return out


def normalize_path(path: str) -> str:
    path = path.split("?")[0].split("#")[0].replace("\\", "/").lstrip("/")
    if path == "" or path.endswith("/"):
        path = f"{path}index.html"
    return path


def variants(path: str) -> set[str]:
    d = normalize_path(path)
    out = {d}
    if d.endswith(".html"):
        out.add(d[: -len(".html")])
        if d.endswith("/index.html"):
            out.add(d[: -len("index.html")])  # trailing slash form
            out.add(d[: -len("/index.html")])
    else:
        out.add(d + ".html")
        out.add(d.rstrip("/") + "/index.html")
    return {x.lstrip("/") for x in out if x}


def classify_dest(dest: str, active: set[str], noindex: set[str], redirs: set[str]) -> str | None:
    """Return issue class or None if OK."""
    vs = variants(dest)
    if vs & redirs:
        return "redirect_source"
    if vs & noindex:
        return "noindex"
    if vs & active:
        return None
    # directory hub
    d = normalize_path(dest)
    if d.endswith("index.html") and d in active:
        return None
    return "not_in_sitemap"


def norm_href(href: str, base: str) -> str | None:
    href = (href or "").strip()
    if href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    if href.startswith("http") and "clscre.com" not in href:
        return None
    if href.startswith("http"):
        path = urlparse(href).path
    else:
        path = href.split("?")[0].split("#")[0]
        if not path.startswith("/"):
            parts: list[str] = []
            for part in f"{base}/{path}".replace("\\", "/").split("/"):
                if part in ("", "."):
                    continue
                if part == "..":
                    if parts:
                        parts.pop()
                    continue
                parts.append(part)
            path = "/".join(parts)
        else:
            path = path.lstrip("/")
    path = normalize_path(path)
    if path.startswith(("css/", "js/", "images/", "fonts/")):
        return None
    if path.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".xml", ".txt", ".woff", ".woff2")):
        return None
    return path


def interesting(dest: str) -> bool:
    if dest.endswith(".html") and "/" not in dest:
        return True
    return dest.startswith(PREFIXES)


def scan(files: list[str], active, noindex, redirs, label: str):
    sources = Counter()
    targets = Counter()
    classes = Counter()
    pairs = 0
    for rel in files:
        p = ROOT / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        base = str(PurePosixPath(rel).parent)
        if base == ".":
            base = ""
        for href in HREF_RE.findall(text):
            dest = norm_href(href, base)
            if not dest or not interesting(dest):
                continue
            cls = classify_dest(dest, active, noindex, redirs)
            if not cls:
                continue
            pairs += 1
            sources[rel] += 1
            targets[dest] += 1
            classes[cls] += 1
    print(f"=== {label} ===")
    print(
        json.dumps(
            {
                "pairs": pairs,
                "sources": len(sources),
                "unique_targets": len(targets),
                "classes": dict(classes),
                "top_sources": sources.most_common(10),
                "top_targets": targets.most_common(12),
            },
            indent=2,
        )
    )
    return {"pairs": pairs, "sources": len(sources), "targets": len(targets), "classes": dict(classes)}


def main():
    active = load_active()
    noindex = load_noindex()
    redirects = load_redirects()
    redirs = set(redirects)
    print(
        json.dumps(
            {
                "active": len(active),
                "noindex": len(noindex),
                "redirect_sources": len(redirs),
            },
            indent=2,
        )
    )

    loans = load_json("loan_types.json")
    props = load_json("property_types.json")
    fin_hubs = [f"financing/{L['slug']}.html" for L in loans]
    prop_hubs = [f"property/{p['slug']}.html" for p in props]
    hubset = set(fin_hubs) | set(prop_hubs)

    scan(fin_hubs, active, noindex, redirs, "financing_hubs")
    scan(prop_hubs, active, noindex, redirs, "property_hubs")
    scan(["locations.html"], active, noindex, redirs, "locations")

    fin_all = [
        f"financing/{p.name}"
        for p in sorted((ROOT / "financing").glob("*.html"))
        if f"financing/{p.name}" not in hubset
    ]
    prop_all = [
        f"property/{p.name}"
        for p in sorted((ROOT / "property").glob("*.html"))
        if f"property/{p.name}" not in hubset
    ]
    market_pages = [
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in (ROOT / "markets").rglob("*.html")
    ]

    # Full family scans (may take a bit)
    scan(fin_all, active, noindex, redirs, "financing_nonhub_all")
    scan(prop_all, active, noindex, redirs, "property_nonhub_all")
    scan(market_pages, active, noindex, redirs, "markets_all")

    # first-15 theoretical hub leak
    cities = [
        c
        for c in load_json("cities.json")
        if c["slug"] not in {"greenville", "rockford", "oxnard", "albany-ny", "columbia-sc-2"}
    ]
    bad = ok = 0
    for loan in loans:
        for city in cities[:15]:
            dest = f"financing/{loan['slug']}-{city['slug']}.html"
            cls = classify_dest(dest, active, noindex, redirs)
            if cls:
                bad += 1
            else:
                ok += 1
    print("hub_first15_theory", {"ok": ok, "bad": bad, "total": ok + bad})
    mok = sum(
        1
        for c in cities
        if classify_dest(f"markets/{c['slug']}/index.html", active, noindex, redirs) is None
    )
    print("markets_active_for_cities", mok, "/", len(cities))


if __name__ == "__main__":
    main()
