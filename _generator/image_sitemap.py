"""sitemap-images.xml: deal photos for Google Images (audit: photos and details on closed deals sell).

Lists, per page, the images that belong to it:
  * every closed deal case study (blog/*-case-study.html): the deal photo inside its DEAL PHOTO figure
  * la-california-closed-deals.html: every deal card photo
  * index.html: the deal card photos shown on the homepage
Only pages that are in the live sitemaps (and not noindexed) are listed, and only images that exist on disk.

generate.py step 12b calls run(WEBSITE_DIR, BASE_URL) and adds the file to sitemap-index.xml.
Usage: python _generator/image_sitemap.py [website_dir]
"""
import html
import re
import sys
from pathlib import Path


def live_urls(web, base):
    urls = set()
    for sm in web.glob("sitemap-*.xml"):
        if sm.name == "sitemap-images.xml":
            continue
        urls |= set(re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8")))
    return urls


def images_in(text, rel_prefix):
    """Image paths (site-relative, no leading slash) for deal photos inside text."""
    out = []
    for m in re.finditer(r'<img src="(?:\.\./)?(images/deals/[^"]+\.jpg)"', text):
        p = m.group(1)
        if p not in out:
            out.append(p)
    return out


def run(web, base="https://clscre.com", dry=False):
    web = Path(web)
    live = live_urls(web, base)
    entries = []  # (page url, [image paths])
    pages = sorted((web / "blog").glob("*-case-study.html")) + [web / "la-california-closed-deals.html", web / "index.html"]
    for page in pages:
        if not page.exists():
            continue
        rel = page.relative_to(web).as_posix()
        url = f"{base}/{rel}" if rel != "index.html" else f"{base}/"
        if url not in live and f"{base}/{rel}" not in live:
            continue
        text = page.read_text(encoding="utf-8-sig")
        if page.parent.name == "blog":
            m = re.search(r"<!-- DEAL PHOTO -->(.*?)<!-- /DEAL PHOTO -->", text, re.S)
            imgs = images_in(m.group(1), "") if m else []
        else:
            imgs = images_in(text, "")
        # generic representative aerials stay out of image search; only photos of the actual properties are listed
        imgs = [i for i in imgs if (web / i).exists() and not i.startswith("images/deals/aerial-")]
        if imgs:
            entries.append((url if url in live else f"{base}/{rel}", imgs))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    n = 0
    for url, imgs in entries:
        lines.append(f"  <url><loc>{html.escape(url)}</loc>")
        for i in imgs:
            lines.append(f"    <image:image><image:loc>{base}/{html.escape(i)}</image:loc></image:image>")
            n += 1
        lines.append("  </url>")
    lines.append("</urlset>")
    if not dry:
        (web / "sitemap-images.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [OK] sitemap-images.xml  ({len(entries)} pages, {n} images)")
    return len(entries)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
