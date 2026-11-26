"""Apply title_rules to existing sitemap pages in the current batch (no regen needed).

Dry run by default. Idempotent. Only touches pages that are listed in the
sitemaps AND in scope per title_rules.TITLE_RULE_PREFIXES.

    python apply_title_rule.py            # report
    python apply_title_rule.py --write    # rewrite files
"""
import argparse
import glob
import re
import sys
from pathlib import Path

import title_rules

ROOT = Path(__file__).resolve().parent.parent
TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)


def sitemap_pages():
    urls = set()
    for f in glob.glob(str(ROOT / "sitemap*.xml")):
        if Path(f).name in ("sitemap-index.xml", "sitemap.xml"):
            continue
        urls |= set(re.findall(r"<loc>https://clscre\.com([^<]*)</loc>", Path(f).read_text(encoding="utf-8")))
    for u in sorted(urls):
        rel = u.lstrip("/")
        if rel == "" or rel.endswith("/"):
            rel += "index.html"
        yield rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    changed = same = 0
    over = []
    for rel in sitemap_pages():
        if not title_rules.in_scope(rel):
            continue
        p = ROOT / rel
        if not p.exists():
            continue
        s = p.read_bytes().decode("utf-8")
        new = title_rules.apply_to_html(s, rel)
        if new != s:
            changed += 1
            if a.write:
                p.write_bytes(new.encode("utf-8"))
        else:
            same += 1
        m = TITLE.search(new)
        if m and len(m.group(1)) > title_rules.LIMIT:
            over.append((rel, len(m.group(1))))
    print(f"{'WROTE' if a.write else 'WOULD CHANGE'} {changed} pages, {same} already compliant")
    print(f"still over {title_rules.LIMIT} chars after rule: {len(over)}")
    for rel, n in over[:20]:
        print("  ", n, rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
