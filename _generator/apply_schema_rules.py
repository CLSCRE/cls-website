"""Apply schema_rules to the existing pages (no regen needed). Dry run by default.

    python apply_schema_rules.py            # report
    python apply_schema_rules.py --write
"""
import argparse
from pathlib import Path

import schema_rules

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    changed = same = missing = 0
    for rel in sorted(schema_rules.ARTICLE_PATHS):
        p = ROOT / rel
        if not p.exists():
            missing += 1
            print("missing:", rel)
            continue
        s = p.read_bytes().decode("utf-8")
        new = schema_rules.apply_to_html(s, rel)
        if new != s:
            changed += 1
            if a.write:
                p.write_bytes(new.encode("utf-8"))
        else:
            same += 1
            print("unchanged:", rel)
    print(f"{'WROTE' if a.write else 'WOULD CHANGE'} {changed}, unchanged {same}, missing {missing}")


if __name__ == "__main__":
    main()
