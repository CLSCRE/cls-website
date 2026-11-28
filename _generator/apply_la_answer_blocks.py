#!/usr/bin/env python3
"""Add the LA answer-first block to the live LA bridge, construction and
multifamily pages.

Idempotent (marker <!-- cls-la-answer -->). Renders templates/_la_answer.html
with the same Jinja settings generate.py uses, so a later full generate.py run
produces the same block. Needed because a full regen is not safe to run just to
add one section (post-passes drift the rest of each page).

Data: data/la_answer_blocks.json  {loan slug: {label, heading, items, closed}}
Usage: python apply_la_answer_blocks.py [--dry-run]
"""
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

HERE = Path(__file__).resolve().parent
WEBSITE = HERE.parent
MARK = "<!-- cls-la-answer -->"
ANCHOR = "<!-- KEY FEATURES -->"


def main():
    dry = "--dry-run" in sys.argv
    data = json.loads((HERE / "data" / "la_answer_blocks.json").read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(str(HERE / "templates")),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["la_answer_blocks"] = data
    tpl = env.get_template("_la_answer.html")
    for slug in data:
        path = WEBSITE / "financing" / f"{slug}-los-angeles.html"
        text = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in text
        t = text.replace("\r\n", "\n")
        if MARK in t:
            print(f"skip (already has block): {slug}")
            continue
        if t.count(ANCHOR) != 1:
            print(f"NO ANCHOR: {slug}")
            continue
        block = tpl.render(city={"slug": "los-angeles"}, loan={"slug": slug}, depth="../")
        t = t.replace(ANCHOR, block + ANCHOR)
        if crlf:
            t = t.replace("\n", "\r\n")
        if not dry:
            path.write_bytes(t.encode("utf-8"))
        print(f"{'would add' if dry else 'added'}: {slug}")


if __name__ == "__main__":
    main()
