"""Context-aware em/en dash scrubber for clscre.com (Trevor's strict no-dash rule).

Rules (idempotent):
  - HTML dash entities are normalized to their literal char first.
  - Em-dash (—): the punctuation dash. "foo — bar" -> "foo, bar". A dash
    immediately before ,.;:!? is dropped (keep the real punctuation).
  - En-dash (–): spaced (" – ") reads as prose punctuation -> comma;
    tight ("5–10", "1.20x–1.25x", "65–75%") is a range -> hyphen.
  - Hyphen-minus (-) is never touched, so "one-on-one", "30-day", "65-75%"
    survive. Hyphenated compounds are fine per Trevor's rule.

Used two ways:
  1. Imported by generate.py -> scrub_tree(WEBSITE_DIR) as a final self-healing
     step, so every content-bot regen strips any dash that slipped into output.
  2. Standalone:  python dash_scrub.py <path|glob> ...   (scrubs files in place)
"""
import re
import sys
from pathlib import Path

_ENTITIES = {
    "&mdash;": "—", "&#8212;": "—", "&#x2014;": "—",
    "&ndash;": "–", "&#8211;": "–", "&#x2013;": "–",
}
_EM = "—"
_EN = "–"


def scrub_text(text: str) -> tuple[str, int]:
    """Return (scrubbed_text, num_dashes_removed)."""
    before_dashes = text.count(_EM) + text.count(_EN) + sum(text.count(e) for e in _ENTITIES)
    if before_dashes == 0:
        return text, 0
    for ent, ch in _ENTITIES.items():
        text = text.replace(ent, ch)
    # Em-dash before real punctuation -> drop the dash, keep the punctuation.
    text = re.sub(r"\s*" + _EM + r"\s*([,.;:!?])", r"\1", text)
    # Em-dash otherwise -> comma.
    text = re.sub(r"\s*" + _EM + r"\s*", ", ", text)
    # En-dash: spaced -> comma; tight (range) -> hyphen.
    text = re.sub(r"\s+" + _EN + r"\s+", ", ", text)
    text = text.replace(_EN, "-")
    # Tidy artifacts.
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s+,", ",", text)
    after_dashes = text.count(_EM) + text.count(_EN)
    return text, before_dashes - after_dashes


def scrub_file(path: Path) -> int:
    try:
        original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return 0
    scrubbed, n = scrub_text(original)
    if n and scrubbed != original:
        path.write_text(scrubbed, encoding="utf-8")
        return n
    return 0


def scrub_tree(root, patterns=("*.html",), exclude_dirs=frozenset({"_generator", ".git"})) -> tuple[int, int]:
    """Scrub every file matching patterns under root. Returns (files_changed, dashes_removed)."""
    root = Path(root)
    files_changed = dashes_removed = 0
    for pat in patterns:
        for p in root.rglob(pat):
            if exclude_dirs & set(p.relative_to(root).parts):
                continue
            n = scrub_file(p)
            if n:
                files_changed += 1
                dashes_removed += n
    return files_changed, dashes_removed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python dash_scrub.py <file-or-dir> [more ...]")
    total_files = total_dashes = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            fc, dr = scrub_tree(p, patterns=("*.html", "*.json", "*.py"))
        else:
            dr = scrub_file(p); fc = 1 if dr else 0
        total_files += fc; total_dashes += dr
        print(f"  {arg}: {fc} files changed, {dr} dashes removed")
    print(f"TOTAL: {total_files} files changed, {total_dashes} dashes removed")
