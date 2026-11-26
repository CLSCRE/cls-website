"""One-time seed of the per-page date sidecar from git history.

Why: the sitemap sidecar (data/sitemap_lastmod.json) was first seeded from whatever the
sitemaps already said, and 96.8% of URLs shared one bulk stamp (2026-09-09). That date is
not when those pages changed. This walks each sitemap page's git history and finds the
last commit that really changed the page's CONTENT, and stores that commit's date.

"Really changed" means:
  * the normalized text differs from the page's previous version (same normalization the
    sidecar uses: nav, footer, scripts, styles, comments and all dates dropped; rate
    figures masked on rate pages), and
  * the commit is not a site-wide sweep. A commit that touched more than BULK_FILES html
    files (a phone-number swap, a schema field, a title-suffix rule, a link pass) says
    nothing about any one page being updated, so it is skipped. If a page's only change
    events are sweeps, its date is the date it first appeared.

    python seed_page_dates_from_git.py            # report only
    python seed_page_dates_from_git.py --write    # rewrite data/sitemap_lastmod.json

Run it against a clean checkout (it reads HEAD blobs, not the working tree). After seeding,
generate.py keeps the dates honest: a hash change moves a page's date to the build day,
nothing else does.
"""
import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import freshness  # noqa: E402
import lastmod_sidecar as sc  # noqa: E402

ROOT = sc.ROOT
MAX_WALK = 120    # commits inspected per page
BULK_FILES = 40   # a commit touching more html files than this is a sweep, not a page edit


def git_text(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


class BlobReader:
    """One long-lived `git cat-file --batch` so reading thousands of blobs stays fast."""

    def __init__(self):
        self.p = subprocess.Popen(["git", "-C", str(ROOT), "cat-file", "--batch"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, spec):
        self.p.stdin.write((spec + "\n").encode())
        self.p.stdin.flush()
        head = self.p.stdout.readline().decode().split()
        if len(head) < 3 or head[1] != "blob":
            return None
        data = self.p.stdout.read(int(head[2]))
        self.p.stdout.read(1)
        return data.decode("utf-8", "replace")

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def history():
    """One pass over the whole log: (sizes, files). sizes: commit -> html files it touched;
    files: path -> [(commit, date), ...] newest first."""
    out = git_text("log", "--format=@@%H %cs", "--name-only", "--", "*.html")
    sizes, files = defaultdict(int), defaultdict(list)
    cur = None
    for line in out.splitlines():
        if line.startswith("@@"):
            c, d = line[2:].split()
            cur = (c, d)
        elif line.strip() and cur:
            sizes[cur[0]] += 1
            files[line.strip()].append(cur)
    return sizes, files


def seed_one(rel, reader, sizes, files):
    commits = list(files.get(rel, []))[:MAX_WALK]  # newest first
    if not commits:
        return None, None
    hashes = []
    for c, _ in commits:
        raw = reader.read(f"{c}:{rel}")
        hashes.append(freshness.page_hash(rel, raw) if raw is not None else None)
    head_hash = hashes[0]
    # change events: commit i changed the text if its hash differs from the next-older version
    events = []
    for i, (c, d) in enumerate(commits):
        older = hashes[i + 1] if i + 1 < len(commits) else None
        if hashes[i] is not None and hashes[i] != older:
            events.append((c, d))
    real = [e for e in events if sizes.get(e[0], 0) <= BULK_FILES]
    if real:
        return real[0][1], head_hash
    if events:
        return events[-1][1], head_hash  # only sweeps touched it: date it by its first appearance
    return commits[-1][1], head_hash


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    side = freshness.load_sidecar()
    locs = sorted(side)
    if a.limit:
        locs = locs[:a.limit]
    sizes, files = history()
    bulk = sum(1 for n in sizes.values() if n > BULK_FILES)
    print(f"{len(sizes)} commits touched html; {bulk} are sweeps (> {BULK_FILES} files)")
    reader = BlobReader()
    out, dist, changed = {}, Counter(), 0
    for i, loc in enumerate(locs, 1):
        rel = freshness.rel_of(loc)
        date, head_hash = seed_one(rel, reader, sizes, files)
        if date is None or head_hash is None:
            out[loc] = side[loc]
            continue
        out[loc] = {"hash": head_hash, "lastmod": date}
        dist[date[:7]] += 1
        if side[loc].get("lastmod") != date:
            changed += 1
        if i % 100 == 0:
            print(f"  {i}/{len(locs)}", flush=True)
    reader.close()
    print(f"seeded {len(out)} pages; {changed} dates differ from the previous sidecar")
    for d, n in sorted(dist.items()):
        print(f"  {d}: {n}")
    if a.write:
        merged = dict(side)
        merged.update(out)
        sc.SIDECAR.write_text(json.dumps(merged, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        print("wrote", sc.SIDECAR)


if __name__ == "__main__":
    main()
