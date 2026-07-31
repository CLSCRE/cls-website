#!/usr/bin/env python
"""Tests for protect-equity redirect map integrity."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "_generator" / "data"
DOCS = ROOT / "docs" / "retired-disposition"


def test_redirect_map_targets_are_active_keep():
    rows = {
        r["path"]: r
        for r in csv.DictReader((DOCS / "retired_disposition_all.csv").open(encoding="utf-8"))
    }
    active = {p for p, r in rows.items() if r["disposition"] == "active_keep"}
    redirect_map = json.loads((DATA / "redirect_map.json").read_text(encoding="utf-8"))
    assert len(redirect_map) >= 400

    def is_active_target(url: str) -> bool:
        path = url.replace("https://clscre.com/", "").split("?")[0]
        if path in {"", "/"}:
            return "index.html" in active
        path = path.lstrip("/")
        if path.endswith("/"):
            cand = path + "index.html"
            return cand in active
        if path in active:
            return True
        if f"{path}/index.html" in active:
            return True
        return False

    bad = [(s, t) for s, t in redirect_map.items() if not is_active_target(t)]
    assert bad == [], f"Inactive redirect targets: {bad[:10]}"


def test_no_self_redirects():
    redirect_map = json.loads((DATA / "redirect_map.json").read_text(encoding="utf-8"))
    for src, target in redirect_map.items():
        src_url = "https://clscre.com/" if src == "index.html" else f"https://clscre.com/{src}"
        assert target.rstrip("/") != src_url.rstrip("/"), src


def test_protect_candidates_are_mapped():
    protect = json.loads((DOCS / "protect_equity_redirect_candidate.json").read_text(encoding="utf-8"))
    redirect_map = json.loads((DATA / "redirect_map.json").read_text(encoding="utf-8"))
    missing = [r["path"] for r in protect if r["path"] not in redirect_map]
    assert missing == [], f"Unmapped protect paths: {missing[:10]}"


def test_submit_deal_maps_to_apply():
    redirect_map = json.loads((DATA / "redirect_map.json").read_text(encoding="utf-8"))
    assert redirect_map["submit-deal.html"] == "https://clscre.com/apply.html"


def test_soft_stubs_exist_and_point_at_map_targets():
    redirect_map = json.loads((DATA / "redirect_map.json").read_text(encoding="utf-8"))
    # spot-check high-value sources
    samples = [
        "submit-deal.html",
        "blog/agency-multifamily-financing-fannie-freddie-2026.html",
        "financing/bridge-loans-phoenix.html",
        "property/multifamily-san-diego.html",
    ]
    for src in samples:
        assert src in redirect_map, src
        text = (ROOT / src).read_text(encoding="utf-8")
        target = redirect_map[src]
        assert 'meta name="robots" content="noindex,follow"' in text
        assert f'canonical" href="{target}"' in text or f"canonical\" href=\"{target}\"" in text
        assert f'url={target}' in text
        assert "location.replace(" in text


def test_cloudflare_bulk_csv_matches_map():
    redirect_map = json.loads((DATA / "redirect_map.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((ROOT / "cloudflare_bulk_redirects.csv").open(encoding="utf-8")))
    assert {r["status_code"] for r in rows} == {"301"}
    by_src = {r["source_url"]: r["target_url"] for r in rows}
    for src, target in redirect_map.items():
        src_url = "https://clscre.com/" if src == "index.html" else f"https://clscre.com/{src}"
        assert by_src[src_url] == target
    assert len(rows) >= len(redirect_map)
