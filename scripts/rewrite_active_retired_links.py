#!/usr/bin/env python3
"""Rewrite active-page hrefs that point at retired/noindex/redirect sources.

Only sitemap-active HTML sources are modified. Destinations are resolved via
_generator.link_governance.LinkGovernor.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_generator"))
from link_governance import (  # noqa: E402
    LinkGovernor,
    normalize_path,
    public_href,
    url_to_path,
)

HREF_RE = re.compile(r"""href\s*=\s*(["'])([^"']+)\1""", re.I)
ANCHOR_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a\s*>", re.I | re.S)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.I)
TAG_RE = re.compile(r"<[^>]+>")
CLASS_RE = re.compile(r"""class\s*=\s*(["'])([^"']*)\1""", re.I)
SECTION_RE = re.compile(r"<section\b[^>]*>.*?</section\s*>", re.I | re.S)
CL_TITLE_RE = re.compile(
    r"<div\b[^>]*class=[\"'][^\"']*\bcl-title\b[^\"']*[\"'][^>]*>(.*?)</div>",
    re.I | re.S,
)
ADJACENT_DUPLICATE_ANCHOR_RE = re.compile(
    r"(?P<anchor><a\b[^>]*>.*?</a\s*>)(?P<gap>\s*)(?P=anchor)",
    re.I | re.S,
)


def depth_prefix(rel: str) -> str:
    parts = PurePosixPath(rel).parts
    if len(parts) <= 1:
        return ""
    return "../" * (len(parts) - 1)


def rel_href_from_source(source_rel: str, dest_path: str) -> str:
    """Build a relative href from source file to dest path."""
    dest = normalize_path(dest_path)
    # Prefer pretty trailing-slash hubs
    if dest.endswith("/index.html"):
        dest_pub = dest[: -len("index.html")]
    else:
        dest_pub = dest

    src_dir = PurePosixPath(source_rel).parent
    if str(src_dir) == ".":
        return dest_pub

    # Compute relative path
    dest_parts = PurePosixPath(dest_pub).parts
    # if dest is directory-like trailing slash, PurePosixPath drops it
    dest_is_dir = dest_pub.endswith("/")
    if dest_is_dir:
        target = PurePosixPath(*PurePosixPath(dest_pub.rstrip("/")).parts)
        # represent as dir
        rel = Path(os_path_rel(src_dir, target)).as_posix()
        if not rel.endswith("/"):
            rel += "/"
        return rel

    target = PurePosixPath(dest_pub)
    return Path(os_path_rel(src_dir, target)).as_posix()


def os_path_rel(src_dir: PurePosixPath, target: PurePosixPath) -> str:
    src_parts = [] if str(src_dir) == "." else list(src_dir.parts)
    tgt_parts = list(target.parts)
    i = 0
    while i < len(src_parts) and i < len(tgt_parts) and src_parts[i] == tgt_parts[i]:
        i += 1
    up = [".."] * (len(src_parts) - i)
    down = tgt_parts[i:]
    if not up and not down:
        return target.name if target.suffix else "./"
    return "/".join(up + down)


def abs_or_site_href(original: str, dest_path: str) -> str:
    if original.startswith("http"):
        p = public_href(dest_path)
        return f"https://clscre.com/{p}" if not p.startswith("http") else p
    if original.startswith("/"):
        p = public_href(dest_path)
        return "/" + p if not p.startswith("/") else p
    return None  # relative handled separately


def load_active_files(gov: LinkGovernor) -> list[str]:
    files = []
    for path in sorted(gov.active):
        p = ROOT / path
        if p.is_file() and p.suffix == ".html":
            files.append(path)
    return files


def href_to_site_path(raw: str, source_rel: str) -> str | None:
    """Resolve an internal href to a normalized site path."""
    raw = raw.strip()
    if raw.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    if raw.startswith("http"):
        parsed = urlparse(raw)
        if "clscre.com" not in parsed.netloc:
            return None
        return normalize_path(parsed.path)
    path_only = raw.split("?", 1)[0].split("#", 1)[0]
    if path_only.startswith("/"):
        return normalize_path(path_only)
    base = PurePosixPath(source_rel).parent
    parts: list[str] = []
    joined = f"{base.as_posix()}/{path_only}" if str(base) != "." else path_only
    for part in joined.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return normalize_path("/".join(parts))


def cleanup_misleading_location_anchors(
    text: str, source_rel: str, gov: LinkGovernor
) -> tuple[str, Counter]:
    """Remove mislabeled generic fallbacks and unwrap misleading inline links."""
    stats = Counter()

    def repl(match: re.Match) -> str:
        attrs, body = match.group("attrs"), match.group("body")
        href_match = HREF_RE.search(attrs)
        if not href_match:
            return match.group(0)
        dest = href_to_site_path(href_match.group(2), source_rel)
        if not dest:
            return match.group(0)

        class_match = CLASS_RE.search(attrs)
        classes = class_match.group(2).casefold() if class_match else ""
        source_submarket = re.match(r"^markets/([^/]+)/[^/]+\.html$", source_rel)
        if source_submarket and "pill-link" in classes:
            parent_market = f"markets/{source_submarket.group(1)}"
            if dest in (parent_market, f"{parent_market}/index.html"):
                stats["parent_market_pills_removed"] += 1
                return ""

        unresolved_forbidden = gov.is_forbidden_dest(dest) and not gov.resolve(
            dest, source_path=source_rel
        )
        if dest != "locations.html" and not unresolved_forbidden:
            return match.group(0)

        text_label = " ".join(html.unescape(TAG_RE.sub(" ", body)).split())
        label = text_label.casefold()
        legitimate_locations_label = (
            label == "locations"
            or "location directory" in label
            or (
                "market" in label
                and any(word in label for word in ("view", "browse", "explore", "all"))
            )
        )
        if dest == "locations.html" and legitimate_locations_label:
            return match.group(0)

        if any(token in classes for token in ("card", "pill-link")):
            stats["misleading_cards_removed"] += 1
            return ""

        stats["misleading_inline_unwrapped"] += 1
        return body

    cleaned = ANCHOR_RE.sub(repl, text)

    def remove_unresolved_link_tag(match: re.Match) -> str:
        href_match = HREF_RE.search(match.group(0))
        if not href_match:
            return match.group(0)
        dest = href_to_site_path(href_match.group(2), source_rel)
        if (
            dest
            and gov.is_forbidden_dest(dest)
            and not gov.resolve(dest, source_path=source_rel)
        ):
            stats["unresolved_link_tags_removed"] += 1
            return ""
        return match.group(0)

    cleaned = LINK_TAG_RE.sub(remove_unresolved_link_tag, cleaned)

    while True:
        cleaned, removed = ADJACENT_DUPLICATE_ANCHOR_RE.subn(
            lambda match: match.group("anchor") + match.group("gap"), cleaned
        )
        if not removed:
            break
        stats["duplicate_adjacent_anchors_removed"] += removed

    def remove_empty_link_section(match: re.Match) -> str:
        section = match.group(0)
        has_link_container = (
            'class="cross-link-grid"' in section
            or 'class="pill-links"' in section
        )
        if has_link_container and not re.search(r"<a\b", section, re.I):
            stats["empty_link_sections_removed"] += 1
            return ""
        return section

    cleaned = SECTION_RE.sub(remove_empty_link_section, cleaned)
    return cleaned, stats


def retarget_semantic_market_card_anchors(
    text: str, source_rel: str, gov: LinkGovernor
) -> tuple[str, Counter]:
    """Retarget program/property cards from generic markets to topical hubs."""
    semantic_targets: dict[str, tuple[str, tuple[str, ...]]] = {}
    for slug, loan in gov.loan_by_slug.items():
        target = f"financing/{slug}.html"
        if gov.is_active(target) and not gov.is_forbidden_dest(target):
            semantic_targets[loan["name"].casefold()] = (
                target,
                (f"financing/{slug}-",),
            )
    for slug, prop in gov.property_by_slug.items():
        target = f"property/{slug}.html"
        if gov.is_active(target) and not gov.is_forbidden_dest(target):
            semantic_targets[prop["name"].casefold()] = (
                target,
                (f"property/{slug}-",),
            )
    semantic_targets.update(
        {
            "self-storage financing": (
                "property/self-storage.html",
                ("self-storage/markets/",),
            ),
            "senior living financing": (
                "property/senior-living.html",
                ("senior-living/markets/",),
            ),
            "medical office financing": (
                "property/medical-office.html",
                ("medical-office/markets/",),
            ),
            "data center financing": (
                "property/data-centers.html",
                ("data-centers/markets/",),
            ),
        }
    )
    stats = Counter()

    def repl(match: re.Match) -> str:
        attrs, body = match.group("attrs"), match.group("body")
        class_match = CLASS_RE.search(attrs)
        classes = class_match.group(2).casefold() if class_match else ""
        if "cross-link-card" not in classes:
            return match.group(0)
        href_match = HREF_RE.search(attrs)
        title_match = CL_TITLE_RE.search(body)
        if not href_match or not title_match:
            return match.group(0)
        dest = href_to_site_path(href_match.group(2), source_rel)
        if not dest:
            return match.group(0)
        title = " ".join(
            html.unescape(TAG_RE.sub(" ", title_match.group(1))).split()
        ).casefold()
        semantic_target = semantic_targets.get(title)
        if not semantic_target:
            return match.group(0)
        target, allowed_prefixes = semantic_target
        if target == dest or any(dest.startswith(prefix) for prefix in allowed_prefixes):
            return match.group(0)
        raw = href_match.group(2)
        if raw.startswith("http"):
            new_href = "https://clscre.com/" + public_href(target)
        elif raw.startswith("/"):
            new_href = "/" + public_href(target)
        else:
            new_href = rel_href_from_source(source_rel, target)
        quote = href_match.group(1)
        new_attrs = HREF_RE.sub(
            f"href={quote}{new_href}{quote}", attrs, count=1
        )
        stats["semantic_cards_retargeted"] += 1
        return f"<a{new_attrs}>{body}</a>"

    return ANCHOR_RE.sub(repl, text), stats


def rewrite_file(rel: str, gov: LinkGovernor, dry_run: bool = False) -> dict:
    text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
    base = str(PurePosixPath(rel).parent)
    if base == ".":
        base = ""
    stats = Counter()
    replacements = []

    def repl(match: re.Match) -> str:
        quote, href = match.group(1), match.group(2)
        raw = href.strip()
        if raw.startswith(("#", "mailto:", "tel:", "javascript:")):
            return match.group(0)
        if raw.startswith("http") and "clscre.com" not in raw:
            return match.group(0)

        # resolve to site path
        if raw.startswith("http"):
            dest = normalize_path(urlparse(raw).path)
        else:
            path_only = raw.split("?")[0].split("#")[0]
            q = ""
            if "?" in raw:
                q = "?" + raw.split("?", 1)[1].split("#")[0]
            frag = ""
            if "#" in raw:
                frag = "#" + raw.split("#", 1)[1]
            if path_only.startswith("/"):
                dest = normalize_path(path_only)
            else:
                parts: list[str] = []
                joined = f"{base}/{path_only}" if base else path_only
                for part in joined.replace("\\", "/").split("/"):
                    if part in ("", "."):
                        continue
                    if part == "..":
                        if parts:
                            parts.pop()
                        continue
                    parts.append(part)
                dest = normalize_path("/".join(parts))
            # keep query/frag for non-path changes only if dest stays
            _q, _f = q, frag

        if dest.startswith(("css/", "js/", "images/", "fonts/")):
            return match.group(0)
        if dest.endswith((".css", ".js", ".png", ".jpg", ".webp", ".svg", ".ico", ".xml", ".txt")):
            return match.group(0)

        if not gov.is_forbidden_dest(dest):
            return match.group(0)

        resolved = gov.resolve(dest, source_path=rel)
        stats["bad_seen"] += 1
        if not resolved:
            stats["unresolved_for_omission"] += 1
            return match.group(0)

        if normalize_path(resolved) == normalize_path(dest):
            return match.group(0)

        # Build new href preserving absolute vs relative style
        if raw.startswith("http"):
            new_href = "https://clscre.com/" + public_href(resolved)
        elif raw.startswith("/"):
            new_href = "/" + public_href(resolved)
        else:
            new_href = rel_href_from_source(rel, resolved)

        # Preserve query only for apply.html style targets
        if raw.startswith("http") or raw.startswith("/"):
            pass
        else:
            if "?" in raw and normalize_path(resolved).endswith("apply.html"):
                new_href += "?" + raw.split("?", 1)[1].split("#")[0]
            if "#" in raw and "apply.html" in new_href:
                # drop random fragments on rewritten non-apply
                pass

        stats["rewritten"] += 1
        replacements.append((dest, resolved))
        return f"href={quote}{new_href}{quote}"

    new_text = HREF_RE.sub(repl, text)
    new_text, semantic_stats = retarget_semantic_market_card_anchors(
        new_text, rel, gov
    )
    stats.update(semantic_stats)
    new_text, cleanup_stats = cleanup_misleading_location_anchors(
        new_text, rel, gov
    )
    stats.update(cleanup_stats)
    changed = new_text != text
    if changed and not dry_run:
        (ROOT / rel).write_text(new_text, encoding="utf-8")
        stats["files_written"] = 1
    elif changed:
        stats["files_would_write"] = 1
    return {"rel": rel, "stats": dict(stats), "sample": replacements[:5], "changed": changed}


def rewrite_active_corpus(
    gov: LinkGovernor,
    *,
    dry_run: bool = False,
    limit: int = 0,
    families: set[str] | None = None,
    write_report: bool = True,
    progress: bool = True,
) -> dict:
    """Rewrite governed links for the final active inventory."""
    files = load_active_files(gov)
    selected = []
    for rel in files:
        fam = rel.split("/", 1)[0] if "/" in rel else "root"
        if families is None or fam in families or ("root" in families and "/" not in rel):
            selected.append(rel)
    if limit:
        selected = selected[:limit]

    totals = Counter()
    changed_files = 0
    samples = []
    for i, rel in enumerate(selected, 1):
        result = rewrite_file(rel, gov, dry_run=dry_run)
        for key, value in result["stats"].items():
            totals[key] += value
        if result["changed"]:
            changed_files += 1
            if len(samples) < 20:
                samples.append({"file": rel, "sample": result["sample"]})
        if progress and i % 500 == 0:
            print(f"... {i}/{len(selected)} files, rewritten_hrefs={totals['rewritten']}")

    out = {
        "dry_run": dry_run,
        "files_scanned": len(selected),
        "files_changed": changed_files,
        "totals": dict(totals),
        "samples": samples,
    }
    if write_report:
        dest = ROOT / "docs" / "link-cleanup"
        dest.mkdir(parents=True, exist_ok=True)
        name = "rewrite_dry_run.json" if dry_run else "rewrite_result.json"
        (dest / name).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2)[:4000])
        print("wrote", dest / name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--families",
        default="all",
        help="Comma families to include, or all",
    )
    args = ap.parse_args()
    requested = {f.strip() for f in args.families.split(",") if f.strip()}
    families = None if not requested or "all" in requested else requested
    rewrite_active_corpus(
        LinkGovernor(ROOT),
        dry_run=args.dry_run,
        limit=args.limit,
        families=families,
    )


if __name__ == "__main__":
    main()
