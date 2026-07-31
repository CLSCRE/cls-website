#!/usr/bin/env python
"""Build protect-equity redirects to active-only destinations.

Updates redirect_map.json, writes soft-301 HTML stubs, and emits
cloudflare_bulk_redirects.csv. Never points a redirect at a non-active URL.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_generator" / "data"
OUT_DOCS = ROOT / "docs" / "retired-disposition"
BASE = "https://clscre.com"
STUB_MARKER = "location.replace("


def norm_path(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("http"):
        value = urlparse(value).path
    value = value.split("?")[0].split("#")[0].strip()
    if value in {"", "/"}:
        return "index.html"
    value = value.lstrip("/")
    if value.endswith("/") and value:
        value = value[:-1]
    if value == "":
        return "index.html"
    return value


def to_url(path: str, active_set: set[str] | None = None) -> str:
    path = norm_path(path)
    if path == "index.html":
        return f"{BASE}/"
    if path.endswith("/index.html"):
        # Keep trailing slash for directory hubs (Cloudflare/Pages clean URLs).
        return f"{BASE}/{path[: -len('index.html')]}"
    # Bare directory hubs (blog, markets/city, etc.)
    if active_set is not None and f"{path}/index.html" in active_set:
        return f"{BASE}/{path}/"
    if path.startswith("markets/") and path.count("/") == 1 and not path.endswith(".html"):
        return f"{BASE}/{path}/"
    if path in {"blog", "markets", "glossary", "tools", "resources", "insights"}:
        return f"{BASE}/{path}/"
    return f"{BASE}/{path}"


def load_rows() -> dict[str, dict]:
    rows = {}
    with (OUT_DOCS / "retired_disposition_all.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["path"]] = r
    return rows


def is_active(path: str, rows: dict[str, dict], active_set: set[str]) -> bool:
    p = norm_path(path)
    if p in active_set:
        return True
    # directory hub form
    if f"{p}/index.html" in active_set:
        return True
    if p.endswith("/index.html") and p in rows and rows[p]["disposition"] == "active_keep":
        return True
    return False


def write_stub(path: Path, target_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Redirecting</title>"
        '<meta name="robots" content="noindex,follow">'
        f'<link rel="canonical" href="{target_url}">'
        f'<meta http-equiv="refresh" content="0; url={target_url}">'
        f"<script>location.replace({json.dumps(target_url)})</script>"
        '</head><body style="font-family:system-ui,sans-serif;padding:2rem">'
        "<p>This page has moved. If you are not redirected automatically, "
        f'<a href="{target_url}">continue here</a>.</p></body></html>\n',
        encoding="utf-8",
    )


def main() -> None:
    rows = load_rows()
    active = {p for p, r in rows.items() if r["disposition"] == "active_keep"}
    cities = json.loads((DATA / "cities.json").read_text(encoding="utf-8"))
    city_slugs = {c["slug"] for c in cities}
    # Prefer longer slugs first for parse
    loan_slugs = sorted(
        [x["slug"] for x in json.loads((DATA / "loan_types.json").read_text(encoding="utf-8"))],
        key=len,
        reverse=True,
    )
    prop_slugs = sorted(
        [x["slug"] for x in json.loads((DATA / "property_types.json").read_text(encoding="utf-8"))],
        key=len,
        reverse=True,
    )
    market_hubs = {
        m.group(1)
        for p in active
        if (m := re.match(r"^markets/([^/]+)/index\.html$", p))
    }

    def pick_active(*candidates: str) -> str | None:
        for c in candidates:
            if not c:
                continue
            p = norm_path(c)
            if is_active(p, rows, active):
                if p.endswith("/index.html"):
                    return p
                if f"{p}/index.html" in active:
                    return f"{p}/index.html"
                return p
        return None

    def parse_loan_city(leaf: str) -> tuple[str | None, str | None]:
        for ls in loan_slugs:
            prefix = ls + "-"
            if leaf.startswith(prefix):
                return ls, leaf[len(prefix) :]
        return None, None

    def parse_prop_city(leaf: str) -> tuple[str | None, str | None]:
        for ps in prop_slugs:
            prefix = ps + "-"
            if leaf.startswith(prefix):
                return ps, leaf[len(prefix) :]
        return None, None

    def target_for(path: str) -> str:
        path = norm_path(path)
        # Explicit special cases
        if path in {"submit-deal.html", "submit-deal"}:
            return "apply.html"
        if path.startswith("markets/la/"):
            return pick_active("markets/los-angeles/index.html", "index.html") or "index.html"

        if path.startswith("financing/") and path.endswith(".html"):
            leaf = path[len("financing/") : -len(".html")]
            # program hub exact
            hub = pick_active(f"financing/{leaf}.html")
            if hub and hub == path:
                pass
            loan, city = parse_loan_city(leaf)
            if loan and city:
                # Prefer active same financing city page only if different and active (rare)
                same = pick_active(f"financing/{loan}-{city}.html")
                # never target self
                cands = []
                if city in market_hubs:
                    cands.append(f"markets/{city}/index.html")
                cands.append(f"financing/{loan}.html")
                if loan == "multifamily-loans":
                    cands.append("property/multifamily.html")
                cands.append("financing/commercial-mortgage-loans.html")
                cands.append("index.html")
                chosen = pick_active(*cands)
                if chosen and chosen != path:
                    return chosen
            # financing program-ish page
            chosen = pick_active(f"financing/{leaf}.html", "financing/permanent-loans.html", "index.html")
            return chosen or "index.html"

        if path.startswith("property/") and path.endswith(".html"):
            leaf = path[len("property/") : -len(".html")]
            prop, city = parse_prop_city(leaf)
            if prop and city:
                cands = []
                if city in market_hubs:
                    cands.append(f"markets/{city}/index.html")
                cands.append(f"property/{prop}.html")
                cands.append("index.html")
                chosen = pick_active(*cands)
                if chosen and chosen != path:
                    return chosen
            chosen = pick_active(f"property/{leaf}.html", "property/multifamily.html", "index.html")
            return chosen or "index.html"

        if path.startswith("blog/") and path.endswith(".html"):
            leaf = path[len("blog/") : -len(".html")]
            # blog city loan guides: {loan}-loans-{city}-guide or industrial-investing-{city}-guide
            m = re.match(r"^(?P<kind>.+)-(?P<city>[a-z0-9-]+)-guide$", leaf)
            if m:
                kind = m.group("kind")
                city = m.group("city")
                cands = []
                if city in market_hubs:
                    cands.append(f"markets/{city}/index.html")
                # map kind fragments to financing hubs
                kind_map = [
                    ("bridge-loans", "bridge-loans"),
                    ("permanent-loans", "permanent-loans"),
                    ("construction-loans", "construction-loans"),
                    ("agency-loans", "agency-loans"),
                    ("sba-loans", "sba-loans"),
                    ("life-company-loans", "life-company-loans"),
                    ("hud-fha-loans", "hud-fha-loans"),
                    ("cmbs-loans", "cmbs-loans"),
                    ("hard-money-loans", "hard-money-loans"),
                    ("stated-income-loans", "stated-income-loans"),
                    ("industrial-investing", "property/industrial"),
                    ("multifamily-investing", "property/multifamily"),
                    ("retail-investing", "property/retail"),
                    ("office-investing", "property/office"),
                ]
                for needle, dest in kind_map:
                    if needle in kind:
                        if dest.startswith("property/"):
                            cands.append(f"{dest}.html")
                        else:
                            cands.append(f"financing/{dest}.html")
                        break
                cands.append("blog/index.html")
                cands.append("index.html")
                return pick_active(*cands) or "blog/index.html"
            # topical blog
            if "agency" in leaf or "fannie" in leaf or "freddie" in leaf:
                return pick_active("financing/agency-loans.html", "blog/index.html", "index.html") or "blog/index.html"
            return pick_active("blog/index.html", "index.html") or "index.html"

        if path.startswith("markets/"):
            parts = path.split("/")
            if len(parts) >= 2:
                city = parts[1]
                if city in market_hubs:
                    return f"markets/{city}/index.html"
            return pick_active("locations.html", "index.html") or "index.html"

        if path.startswith("commercial/markets/"):
            leaf = path.split("/")[-1].replace(".html", "")
            # atlanta-medical-office etc.
            for ps in prop_slugs:
                if leaf.endswith("-" + ps) or f"-{ps}-" in leaf or leaf.endswith(ps):
                    # try city prefix
                    city = leaf[: -(len(ps) + 1)] if leaf.endswith("-" + ps) else None
                    cands = []
                    if city and city in market_hubs:
                        cands.append(f"markets/{city}/index.html")
                    cands.append(f"property/{ps}.html")
                    cands.append("index.html")
                    return pick_active(*cands) or "index.html"
            return pick_active("index.html") or "index.html"

        return pick_active("index.html") or "index.html"

    # Start from existing map, fix bad targets, add protect candidates
    old_map: dict[str, str] = json.loads((DATA / "redirect_map.json").read_text(encoding="utf-8"))
    new_map: dict[str, str] = {}
    changes = []

    def set_redirect(src: str, dest_path: str, reason: str) -> None:
        src = norm_path(src)
        dest_path = norm_path(dest_path)
        if dest_path == src:
            raise ValueError(f"self-redirect {src}")
        if not is_active(dest_path, rows, active):
            raise ValueError(f"inactive target {src} -> {dest_path}")
        # Canonicalize directory destinations to */index.html when available
        if f"{dest_path}/index.html" in active:
            dest_path = f"{dest_path}/index.html"
        url = to_url(dest_path, active)
        prev = old_map.get(src) or old_map.get(src.replace("\\", "/"))
        new_map[src] = url
        if prev != url:
            changes.append({"src": src, "from": prev, "to": url, "reason": reason})

    # Fix / carry forward existing map
    for src, dst in old_map.items():
        dest_path = norm_path(dst)
        if is_active(dest_path, rows, active):
            set_redirect(src, dest_path, "preserve_valid_existing")
        else:
            fixed = target_for(src)
            set_redirect(src, fixed, "fix_existing_inactive_target")

    # Protect equity candidates
    protect = json.loads((OUT_DOCS / "protect_equity_redirect_candidate.json").read_text(encoding="utf-8"))
    for row in protect:
        src = row["path"]
        if src in new_map:
            # already handled
            continue
        dest = target_for(src)
        set_redirect(src, dest, "protect_equity")

    # Explicit submit-deal
    if "submit-deal.html" not in new_map:
        set_redirect("submit-deal.html", "apply.html", "explicit_submit_deal")

    # Sort for stability
    ordered = dict(sorted(new_map.items(), key=lambda kv: kv[0]))

    # Validate no inactive targets
    inactive_targets = []
    for src, url in ordered.items():
        dp = norm_path(url)
        if not is_active(dp, rows, active):
            inactive_targets.append((src, url, dp))
    if inactive_targets:
        raise SystemExit(f"inactive targets remain: {inactive_targets[:10]}")

    # Write redirect map
    (DATA / "redirect_map.json").write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Cloudflare bulk redirects CSV (source URL, target URL, status, preserve query)
    bulk_path = ROOT / "cloudflare_bulk_redirects.csv"
    bulk_rows: list[tuple[str, str]] = []
    seen_src = set()
    for src, url in ordered.items():
        # Prefer the literal HTML path users and Google already know.
        if src == "index.html":
            source_urls = [f"{BASE}/"]
        else:
            source_urls = [f"{BASE}/{src}"]
            if src.endswith("/index.html"):
                source_urls.append(f"{BASE}/{src[: -len('index.html')]}")
        for source_url in source_urls:
            if source_url in seen_src:
                continue
            seen_src.add(source_url)
            bulk_rows.append((source_url, url))
    with bulk_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "source_url",
                "target_url",
                "status_code",
                "preserve_query_string",
                "include_subdomains",
                "subpath_matching",
                "preserve_path_suffix",
            ]
        )
        for source_url, url in bulk_rows:
            w.writerow([source_url, url, 301, "true", "false", "false", "false"])

    # Write soft stubs for all map sources that exist as files or should exist
    written = 0
    missing_parents = 0
    for src, url in ordered.items():
        out_path = ROOT / src
        # ensure parent exists in sparse tree
        try:
            write_stub(out_path, url)
            written += 1
        except Exception:
            missing_parents += 1
            raise

    # Summary artifact
    reason_counts = Counter(c["reason"] for c in changes)
    summary = {
        "redirect_count": len(ordered),
        "previous_count": len(old_map),
        "changes": len(changes),
        "reason_counts": dict(reason_counts),
        "stubs_written": written,
        "protect_candidates": len(protect),
        "bulk_csv": str(bulk_path.name),
        "sample_changes": changes[:40],
    }
    OUT_DOCS.mkdir(parents=True, exist_ok=True)
    (OUT_DOCS / "protect_redirect_build_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (OUT_DOCS / "protect_redirect_changes.json").write_text(
        json.dumps(changes, indent=2), encoding="utf-8"
    )

    # Human report
    lines = [
        "# Protect-equity redirect build",
        "",
        f"- Redirect map entries: **{len(ordered)}** (was {len(old_map)})",
        f"- Changes vs previous map: **{len(changes)}**",
        f"- Soft stubs written: **{written}**",
        f"- Bulk CSV: `{bulk_path.name}`",
        "",
        "## Change reasons",
        "",
    ]
    for k, n in reason_counts.most_common():
        lines.append(f"- `{k}`: {n}")
    lines += ["", "## Sample mappings", "", "| Source | Target | Reason |", "|---|---|---|"]
    for c in changes[:30]:
        lines.append(f"| `{c['src']}` | `{c['to']}` | {c['reason']} |")
    (OUT_DOCS / "PROTECT_REDIRECTS_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2)[:2000])
    print("OK redirect_map", len(ordered), "changes", len(changes), "stubs", written)


if __name__ == "__main__":
    main()
