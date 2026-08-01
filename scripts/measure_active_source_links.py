#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "_generator"))
from link_governance import LinkGovernor, normalize_path, path_variants  # noqa: E402

HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)


def main() -> None:
    gov = LinkGovernor(ROOT)
    active_files = []
    for a in sorted(gov.active):
        if (ROOT / a).is_file() and a.endswith(".html"):
            active_files.append(a)
    print("active_html_on_disk", len(active_files))

    fam_pairs: Counter[str] = Counter()
    fam_sources: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    pairs = 0

    for rel in active_files:
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        base = str(PurePosixPath(rel).parent)
        if base == ".":
            base = ""
        local = 0
        for href in HREF_RE.findall(text):
            href = (href or "").strip()
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            if href.startswith("http") and "clscre.com" not in href:
                continue
            if href.startswith("http"):
                dest = normalize_path(urlparse(href).path)
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
                    dest = normalize_path("/".join(parts))
                else:
                    dest = normalize_path(path)
            if not gov.is_contentish(dest):
                continue
            if not gov.is_forbidden_dest(dest):
                continue
            vs = path_variants(dest)
            if vs & gov.redirect_sources:
                cls = "redirect_source"
            elif vs & gov.noindex:
                cls = "noindex"
            else:
                cls = "not_in_sitemap"
            pairs += 1
            local += 1
            sources[rel] += 1
            targets[dest] += 1
            classes[cls] += 1
            fam = rel.split("/", 1)[0] if "/" in rel else "root"
            fam_pairs[fam] += 1
        if local:
            fam = rel.split("/", 1)[0] if "/" in rel else "root"
            fam_sources[fam] += 1

    print("ACTIVE_SOURCE_bad_pairs", pairs)
    print("classes", dict(classes))
    print("family_pairs", fam_pairs.most_common(20))
    print("family_source_pages", fam_sources.most_common(20))
    print("top_sources", sources.most_common(15))
    print("top_targets", targets.most_common(15))

    out = {
        "active_html_on_disk": len(active_files),
        "bad_pairs": pairs,
        "classes": dict(classes),
        "family_pairs": fam_pairs.most_common(),
        "family_source_pages": fam_sources.most_common(),
        "top_sources": sources.most_common(50),
        "top_targets": targets.most_common(50),
    }
    dest = ROOT / "docs" / "link-cleanup"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "after_active_sources.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", dest / "after_active_sources.json")


if __name__ == "__main__":
    main()
