"""Standardize navigation across all HTML pages on clscre.com."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

WEBSITE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

SKIP_DIRS = {"_generator"}


def get_nav_html(prefix: str) -> str:
    """Return the standardized nav HTML with the given prefix for relative links."""
    p = prefix  # e.g. "", "../", "../../"
    # For the homepage logo, link to index or #home
    if p == "":
        logo_href = "index.html"
    else:
        logo_href = f"{p}index.html"

    return f'''<nav class="nav" id="nav">
<div class="nav-inner">
  <a href="{logo_href}" class="nav-logo"><img src="{p}images/cls-logo-emblem.png" alt="Commercial Lending Solutions" width="140" height="140"><span class="nav-logo-text">Commercial<br>Lending Solutions</span></a>
  <div class="nav-links" id="navLinks">
    <div class="nav-dropdown">
      <a href="{p}index.html#programs">Financing</a>
      <div class="nav-dropdown-menu">
        <a href="{p}financing/permanent-loans.html">Permanent Loans</a>
        <a href="{p}financing/construction-loans.html">Construction Loans</a>
        <a href="{p}financing/bridge-loans.html">Bridge Loans</a>
        <a href="{p}financing/sba-loans.html">SBA Loans</a>
        <a href="{p}financing/mezzanine.html">Mezzanine &amp; Pref Equity</a>
        <a href="{p}financing/specialty.html">Specialty Financing</a>
      </div>
    </div>
    <div class="nav-dropdown">
      <a href="{p}index.html#transactions">Properties</a>
      <div class="nav-dropdown-menu">
        <a href="{p}property/multifamily.html">Multifamily</a>
        <a href="{p}property/industrial.html">Industrial</a>
        <a href="{p}property/retail.html">Retail</a>
        <a href="{p}property/office.html">Office</a>
        <a href="{p}property/mixed-use.html">Mixed-Use</a>
        <a href="{p}property/hospitality.html">Hospitality</a>
      </div>
    </div>
    <a href="{p}about.html">About</a>
    <a href="{p}blog/index.html">Insights</a>
    <a href="{p}market-data.html">Market Data</a>
    <a href="https://clscre.ai" target="_blank" rel="noopener">AI Tools</a>
    <a href="{p}submit-deal.html">Submit Deal</a>
    <a href="{p}apply.html" class="nav-cta">Apply Now</a>
  </div>
  <button class="nav-mobile" id="mobileToggle" aria-label="Toggle menu">
    <span></span><span></span><span></span>
  </button>
</div>
</nav>'''


# Regex to match the entire <nav class="nav" ...> ... </nav> block
NAV_PATTERN = re.compile(
    r'<nav\s+class="nav"[^>]*>.*?</nav>',
    re.DOTALL
)


def main():
    changed = 0
    no_nav = 0
    already_ok = 0
    total = 0

    for root, dirs, files in os.walk(WEBSITE_DIR):
        # Skip _generator and hidden dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for fname in files:
            if not fname.endswith(".html"):
                continue

            total += 1
            filepath = os.path.join(root, fname)
            rel = os.path.relpath(filepath, WEBSITE_DIR).replace("\\", "/")

            # Check if nav exists first
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except (UnicodeDecodeError, PermissionError) as e:
                print(f"  SKIP (read error): {rel} - {e}")
                no_nav += 1
                continue

            match = NAV_PATTERN.search(content)
            if not match:
                no_nav += 1
                continue

            depth = rel.count("/")
            if depth == 0:
                prefix = ""
            elif depth == 1:
                prefix = "../"
            else:
                prefix = "../" * depth

            old_nav = match.group(0)
            new_nav = get_nav_html(prefix)

            if old_nav.strip() == new_nav.strip():
                already_ok += 1
                continue

            new_content = content[:match.start()] + new_nav + content[match.end():]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)

            print(f"  UPDATED: {rel}")
            changed += 1

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total HTML files scanned: {total}")
    print(f"Files updated:            {changed}")
    print(f"Files already correct:    {already_ok}")
    print(f"Files with no nav:        {no_nav}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
