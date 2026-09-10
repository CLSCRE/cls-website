# Locations Experience Professionalization Implementation Plan

> **For Hermes:** Quarantine the primary checkout, preserve its intentional dirty author/image state independently, then use a fresh clean clone outside OneDrive from the freshly verified `origin/main`. The primary checkout is 7 commits ahead, 8 behind, and has 5,285 tracked modifications; do not use its stale `HEAD` as the release base, attach audit releases to its stale/locked worktrees, or merge its dirty state into audit releases. Implement this plan task-by-task only after Trevor approves execution. Do not run a full regeneration in the dirty primary checkout. Do not commit, push, deploy, redirect, canonicalize, or noindex anything without separate authorization.

**Goal:** Replace the visibly programmatic `locations.html` experience with a credible national commercial mortgage brokerage entry point while preserving the city, state, product, LA, life-company, and ED1 authority architecture already built.

**Architecture:** Keep all existing URLs and intent ownership intact. Change only the locations hub’s presentation and outbound link selection: featured markets, all 242 city authority hubs, 52 state pages, selected national financing pathways, transactions, and broker trust. Remove city×program and city×property permutations from this one hub because they remain reachable through city hubs, national hubs, state hubs, sitemaps, and existing spoke links.

**Tech Stack:** Static HTML, Jinja2, Python generator, scoped CSS, BeautifulSoup/pytest regression tests, Chrome mobile/desktop visual verification, GSC and GA4 monitoring.

---

## Evidence baseline and corrections to the earlier recommendation

### Repository inventory

- 24,405 generated/output HTML pages currently exist outside `_generator/`.
- 24,518 tracked files exist at `origin/main`; 24,454 of them are HTML when Jinja templates are included.
- The sitemap contains **8,724 unique indexable URLs**. Do not double-count `sitemap.xml` and its segmented copies.
- On-disk major page families:
  - `financing/`: 10,317 HTML files; 3,315 currently in the financing sitemap.
  - `property/`: 2,966 HTML files; 1,146 in the property sitemap.
  - `markets/`: 3,016 HTML files; 897 in the core markets sitemap, with additional vertical-market URLs in their own sitemaps.
  - `blog/`: 5,802 HTML files; 1,188 in the blog sitemap.
  - `states/`: 52 HTML files; all 52 in the state sitemap.
- `_generator/data/cities.json` contains 247 raw city records. Five duplicate slugs are excluded by `generate.py`, producing **242 rendered markets**.
- There are 42 loan types, 12 property types, and 2,811 neighborhood labels.
- All 247 city records contain unique local context and unique neighborhood lists; median local-context length is 1,785 characters.
- `_generator/data/noindex_paths.json` contains 15,502 paths.
- `_generator/data/redirect_map.json` contains 82 redirect targets.

### Existing work that must not be rebuilt

- State hubs were shipped July 11, 2026 (`8a6f4ecb6dd`). Do not create another state architecture.
- 14,895 dead programmatic pages were first noindexed/de-sitemapped July 13; the current noindex set is 15,502 (`7e4f1718023`).
- LA hub/submarket consolidation and authority depth were completed July 17–25, including retiring competing LA hubs and preserving the ED1 money URL.
- City hubs were reinforced as owners of broad city CRE queries July 24 (`a8014b6c48a`).
- The documented hub-and-spoke Phase B was implemented July 27 (`44fe6b95830`, rendered in `9fd02cd802c`). National Tier-0 program links, city parent links, FAQ deflectors, and preferred commercial-mortgage city links already exist.
- `locations.html` itself is still based on the March 2–11 directory design. Later commits touching it were mostly rendered-site churn, ADA work, branding, and dash cleanup—not a professional redesign.

### Current locations-hub defect

- Live/rendered page: 13,716 total links; 13,398 unique internal destinations.
- It links directly to 10,207 financing pages and 2,916 property pages.
- **8,809 unique destinations linked from the hub are already in `noindex_paths.json`**; three destinations are redirect stubs.
- The hub also links to all 242 city authority hubs.
- Every generated city financing, city property, and city market hub includes `_related_markets.html`, which itself links all 242 market hubs. State pages also link all cities in that state. Therefore, removing city×program and city×property links from `locations.html` will not orphan the city authority hubs.

### Search and analytics baseline

GSC, April 26–July 25 (90 days):

- `locations.html`: no row, therefore zero reported impressions/clicks.
- Financing-geo: 3,926 pages with visibility, 67,825 impressions, 320 clicks, 0.472% CTR.
- Property-geo: 1,944 pages, 21,642 impressions, 79 clicks, 0.365% CTR.
- City market hubs: 239 pages, 13,243 impressions, 37 clicks, 0.279% CTR.
- Neighborhood pages: 820 pages, 14,665 impressions, 34 clicks, 0.232% CTR.
- 2,408 query rows had multiple competing pages in the latest export; prior documented snapshot had 2,375.
- The July 27 hub-and-spoke release is too recent to judge. Do not launch another mass city consolidation before its 28-day measurement window.

GA4, last 90 days through July 28:

- `/locations.html`: 9 sessions, 7 engaged sessions, no explicit lead action.
- City market hubs: 405 sessions, 34 engaged sessions, one explicit lead action.
- Financing pages: 5,677 sessions, 798 engaged sessions, 53 explicit lead actions.
- Strong explicit-action landing pages include national construction, national bridge, national permanent, LA bridge, and Miami bridge.
- GA4 generic `keyEvents` is not reliable for prioritization: `ads_conversion_Contact_1` fired 1,506 times while `form_submit` fired 39 times. Use explicit lead events until GTM attribution is repaired.

### Performance baseline

- PageSpeed 28-day field data passed Core Web Vitals: LCP 1.0 s, FCP 1.0 s, CLS 0, TTFB 0.6 s.
- Live DOM: ~32,923 elements, ~1.64 million HTML characters, and ~126,000 px page height.
- The problem is primarily presentation, link architecture, and trust—not a failing Core Web Vitals page.

---

## Release boundary

### In scope for the first approved release

- `_generator/templates/locations.html`
- `locations.html`
- New page-scoped stylesheet: `css/locations.css`
- New regression test: `_generator/tests/test_locations_hub.py`
- A small generator-context change in `_generator/generate.py` only if required to pass explicit featured markets or a noindex set to the template
- No other rendered pages

### Explicitly out of scope

- No city-page rewrites in the first locations-hub release; the city-financing hero defect discovered below is tracked as a separate Phase 2 release
- No changes to city titles, H1s, canonicals, robots directives, redirects, or URL paths
- No changes to `noindex_paths.json` or `redirect_map.json`
- No full-site CSS cache-bust
- No changes to life-company, ED1, Capital Markets, Legislative Edge, Market Perspective, or `market-data.html`
- No author-header/mobile-overflow work in this release
- No commit, push, or deploy until separately authorized

### Durable issue register: city-financing hero looks programmatic

**Discovered:** July 29, 2026, on local `financing/bridge-loans-new-york.html` screenshot `composer_2026-07-30_04-11-21-166_cc873b.png`.

**Source:** `_generator/templates/city_financing.html:35-71`. This is not isolated New York copy: the shared template renders the 42-loan-type × 242-city page family (up to 10,164 generated combinations, with the existing noindex set controlling which remain indexable).

**Visible defects:**

- “Quick answer:” reads as exposed AEO/SEO scaffolding rather than broker advice.
- The answer repeats the exact product/city phrase, a terms string, “Best for,” lender categories, and the 1,000+ claim in one machine-like paragraph.
- The full `city.context` essay is placed inside the hero, delaying the application CTA until below the first viewport.
- The narrow left text measure and unused right side create an unfinished, unbalanced desktop composition.
- “Bridge Loans national overview” appears as an orphaned utility link instead of a deliberate product-navigation element.
- Reviewer attribution does not show CA DRE #02244836 or a stronger professional trust treatment.
- The next section repeats “Bridge Financing,” “Bridge Loan Details,” and “Bridge Financing for New York Commercial Properties,” compounding the programmatic impression.
- `_generator/templates/city_financing.html:71` still uses visible “CLS CRE” copy instead of the public name “Commercial Lending Solutions.”

**Does the locations-hub release fix it?** No. The first release intentionally changes only the locations hub. This defect must not be forgotten or misreported as resolved.

**Phase 2 direction, after the locations review and in a separate patch:**

1. Add regression tests covering representative city-financing pages, including New York bridge, Los Angeles bridge/construction, one life-company city page, and one lower-volume market.
2. Preserve titles, H1s, self-canonicals, URLs, existing hub-and-spoke links, schema facts, and indexation rules.
3. Replace the visible “Quick answer” treatment with a professional financing snapshot: loan range, indicative rate, term, leverage/fit, and a direct CTA. Keep the underlying answer extractable without labeling it for search engines.
4. Move the full city market essay out of the hero into a clearly labeled “Market and underwriting context” section. Keep only a concise, genuinely local advisory sentence or two above the fold.
5. Integrate the national program link into a deliberate related-resource/navigation treatment.
6. Add compact reviewer trust with Trevor Damyan, role, and CA DRE #02244836 without turning every page into an article-author biography.
7. Replace visible “CLS CRE” references with “Commercial Lending Solutions.”
8. Validate 390 px and 1440 px layouts, CTA visibility, overflow, schema, internal links, and representative rendered pages before any corpus regeneration.
9. Build in a fresh isolated clone outside OneDrive because changing the shared template can rewrite thousands of files. Review the generated diff and release this family separately.
10. Measure explicit lead actions and GSC query allocation; do not use contaminated generic GA4 `keyEvents` or change city intent ownership during the visual migration.

### Approved credibility theme: broker credential panel and life-company access

**User-approved visual direction:** The dark navy broker credential card shown in `composer_2026-07-30_04-19-28-218_53d5c5.png` should inform a reusable Commercial Lending Solutions trust pattern. Its strongest elements are the portrait, clear authorship/transaction relationship, Trevor Damyan’s name and role, visible CA DRE credential, concise experience biography, restrained navy/green palette, and immediate transition into substantive deal facts.

**Recurring credential set:**

- Trevor Damyan — Founder & Commercial Mortgage Broker.
- CA DRE Broker License #02244836.
- More than $1 billion in commercial real estate financing closed nationwide.
- Direct access to life insurance company lenders.
- 1,000+ lender relationships across banks, credit unions, CMBS, agency, debt funds, and other capital sources.

**Presentation rules:**

1. Add “Direct access to life insurance company lenders” as a compact credential/chip or short proof line in the broker panel, not as another long paragraph.
2. Treat it as a Commercial Lending Solutions/Trevor capability. On construction, bridge, ED1, or other non-life-company transactions, do not imply the specific deal was financed by a life company.
3. On life-company, permanent-financing, stabilized-asset, and high-value borrower pages, emphasize and contextually link the credential to `/financing/life-company-loans.html` so the recurring trust pattern also concentrates authority on the life-company hub.
4. On unrelated pages, keep the credential subordinate to the page’s primary topic; one proof line is enough.
5. Do not repeat the same full biography twice on one page. The credential panel replaces weak or duplicate bylines rather than stacking beside them.
6. Use the public entity name “Commercial Lending Solutions,” never visible “CLS CRE.”
7. Keep claims consistent across visible copy, Trevor’s profile, Person/Organization schema, life-company hubs, and supporting lender-access language. Do not encode marketing statements as fake licenses or credentials in schema.
8. Preserve truth labels on case studies: “Deal arranged and presented by” only for verified closed transactions; representative scenarios use the approved illustrative/prepared wording.
9. Create compact, standard, and life-company-emphasis variants from one component rather than copying bespoke markup into thousands of pages.
10. Validate the component at 390 px and 1440 px, including long titles, wrapped credentials, portrait sizing, focus order, link contrast, and no duplicate Trevor Damyan attribution.

### Global directive: physically decommission retired page inventory

**User direction:** Prefer a smaller, cleaner, higher-quality website. Pages already designated inactive/noindex should not remain as 15,000 fully rendered public files unless a documented operational reason requires them.

**Verified inventory on July 29, 2026:**

- 24,405 public HTML files in the repository.
- 8,724 unique sitemap-active HTML pages, with every sitemap content URL mapped to a local file.
- 15,502 files explicitly designated retired/noindex in `_generator/data/noindex_paths.json`.
- 81 local redirect-source stubs from an 82-entry redirect map; one path overlaps the noindex set.
- 99 additional non-sitemap files, predominantly intentional paid landing, thank-you, portal, email-template, and utility surfaces that require separate keep/delete classification.
- The generator still renders noindex financing, property, blog, and neighborhood pages, so manual file deletion would be reversed by the next full generation.

**Current blockers to deletion:**

- Active pages contain 230,440 links to retired destinations.
- 6,011 active pages link to at least one retired URL.
- 11,149 unique retired URLs remain linked from active pages.
- `locations.html` alone contributes 8,990 retired-destination links, while national financing/property templates contribute hundreds each.
- Final GSC data for July 20-28 still shows 476 retired URLs with impressions: 1,111 impressions and 8 clicks. Several remain in positions 2-10 and require redirect/protection review instead of blind 404 deletion.

**Required end state:** approximately the 8,724 intentionally active pages plus only necessary paid/noindex utilities and real redirect infrastructure. The repository, generator, sitemap, internal links, and deployed responses must agree about which pages exist.

**Decommissioning sequence:**

1. Produce a versioned URL-disposition manifest with one decision per retired URL: `redirect`, `remove`, `temporary_keep`, or `operational_noindex`.
2. Protect any retired URL with recent clicks, meaningful impressions/position, explicit lead activity, known external links, or a unique conversion purpose until its replacement and redirect are verified.
3. Assign redirects to the closest surviving authority URL when intent and content genuinely match; do not redirect every retired URL to the homepage or a loosely related hub.
4. Remove all active-to-retired internal links before deleting files. Templates must filter against the disposition/noindex set when building featured markets, related cities, city/property grids, article relations, neighborhood links, and the locations directory.
5. Change `generate.py` so pages marked `remove` are not rendered, not added to related-content pools, and not recreated on future full runs. Redirect sources should be emitted only when still needed by the selected redirect delivery mechanism.
6. Keep paid landing pages, thank-you pages, portals, email templates, and other operational noindex surfaces only when their business purpose is documented; being outside the sitemap is not itself a deletion reason.
7. Physically delete `remove` outputs in a fresh isolated clone outside OneDrive after the link graph reaches zero and the redirect/protection manifest passes validation.
8. Serve verified 301 redirects for equity-bearing consolidations. Use a deliberate 404/410 retirement response for true dead inventory rather than leaving full-content noindex copies indefinitely.
9. Regenerate sitemaps and assert: no retired URL in a sitemap, no active page links to a removed URL, no removed file regenerates, no redirect chain/loop, every target returns 200 and is indexable, and all active canonical files remain present.
10. Monitor GSC crawl/indexing, clicks, impressions, query reassignment, 404s, and explicit GA4 lead actions at 7, 14, 28, 60, and 90 days. Restore or redirect only from evidence, not from file-count anxiety.
11. After retired inventory is removed, evaluate whether the remaining 8,724 active pages should be reduced further using URL-level performance, similarity, backlinks, query ownership, and conversion relevance. Do not assume every sitemap page deserves to remain merely because it escaped the July noindex pass.
12. Keep this as a separate, reversible release series; do not combine 15,000 deletions with locations design, Quick Answer cleanup, modal fixes, author work, or macro automation.

### Global directive: remove visible “Quick answer” treatment everywhere

**User directive:** Remove the visible “Quick answer” treatment across every public page that has it, not only city-financing pages.

**Repository inventory refreshed against `origin/main` (`7909e17855e`) on July 29, 2026:** 18,630 tracked HTML/template files contain “Quick answer,” comprising 14 source templates and 18,616 public files. Of those public files, 5,580 are sitemap-active pages that require a real design/content cleanup, 12,794 are already retired/noindex pages that should be removed through the decommissioning program rather than individually migrated, and 242 non-sitemap/non-noindex public files require utility/editorial classification. Major families are 10,177 financing, 4,757 blog, 2,954 property, 325 loan-size, 242 market hubs, 60 comparisons, 51 state pages, 30 multifamily, 9 industrial, 9 retail, and 2 research pages. Recent financing/property-hub releases reduced the active affected count but did not eliminate the shared-template problem.

**Shared sources:** `_generator/templates/blog_article.html`, `city_financing.html`, `city_property.html`, `comparison_page.html`, `financing_page.html`, `la_apartment_page.html`, `la_industrial_page.html`, `la_retail_page.html`, `loan_size_page.html`, `market_city_index.html`, `property_page.html`, `research_page.html`, `specialty_property_page.html`, and `state_page.html`, plus isolated article content in `_generator/data/articles.json`.

**Required outcome:**

1. Remove the literal “Quick answer” and “The Quick Answer” labels from every public page.
2. Remove the generic gray/green `page-tldr` callout wherever it visibly exposes AEO/SEO scaffolding; do not merely rename the same mass-produced box.
3. Preserve genuinely useful facts by integrating them into natural editorial introductions, glossary definitions, market context, or purpose-built financing snapshots.
4. Do not remove substantive unique guidance merely to satisfy a string search.
5. Use page-family-appropriate presentation rather than one repeated component across 18,000+ pages.
6. Decommission the 12,794 retired affected outputs first. Update source templates and source article data, then migrate or regenerate only the 5,580 surviving sitemap-active pages in a fresh isolated clone outside OneDrive.
7. Add a regression test requiring zero public HTML matches for case-insensitive `quick answer` after retired-file deletion and active-page migration, while separately validating that each surviving affected template still supplies a concise user-facing answer or summary where useful.
8. Review representative pages from every affected family at 390 px and 1440 px before corpus-wide release.
9. Preserve titles, H1s, URLs, canonicals, schema facts, indexation rules, and hub-and-spoke ownership unless a separate approved task changes them.
10. Keep this migration isolated from locations-hub, macro, author-header, and modal-collision releases.

### Durable issue register: duplicate exit-intent modals stack sitewide

**Discovered:** July 29, 2026, screenshot `composer_2026-07-30_04-12-09-079_541f0d.png`.

**Visible failure:** The global “Questions about your deal?” dialog opens above the already-open “Free Rate Sheet: Bridge Loans” dialog. It obscures the active lead form and CAPTCHA, presents three competing actions, and forces the user to dismiss one interruption before returning to the original conversion task.

**Root cause confirmed in source:**

- `_generator/templates/_base.html:220-263` implements the page-specific rate-sheet/guide/report exit modal and stores `sessionStorage.exitShown`.
- `js/chatbot.js:351-406` independently implements the “Questions about your deal?” fallback and stores `sessionStorage['cls-exit-shown']`.
- Both listen for a top-of-window exit gesture, but neither checks whether another dialog, lead form, CAPTCHA, or focused input is active.
- `js/chatbot.js` is loaded on 24,034 generated pages, making this a sitewide conversion and accessibility defect rather than a one-page problem.
- Final overlap review found 21,680 pages with both implementations and 2,354 pages with only the global fallback. Of the fallback-only pages, 1,976 are sitemap-active. Therefore, blanket removal of the global fallback would unnecessarily remove behavior from active pages.

**Additional defects:**

- The foreground dialog says “Email CLS CRE” instead of “Email Commercial Lending Solutions.”
- The call-to-action text wraps awkwardly inside a narrow three-column action row.
- The close control is small and low-contrast.
- The JavaScript-created dialog lacks `aria-modal="true"`, focus placement, focus trapping, focus restoration, and Escape-key handling.
- The two systems emit different analytics events (`exit_intent_shown` and `exit_popup_shown`), compounding the already-unreliable conversion reporting.

**Priority:** First release / P0 sequencing for conversion hygiene. This is a high-severity conversion and accessibility defect, not a security or availability outage. Address it before judging landing-page or city-page conversion performance.

**Fix direction:**

1. Select one page-aware exit-intent controller. Where `#exitOverlay` exists, it owns exit intent and the chatbot fallback must not register. On the 2,354 fallback-only pages, retain a governed fallback unless the route is retired or explicitly suppressed. Do not blanket-disable the fallback across 1,976 active sitemap pages and do not maintain two competing managers on the same page.
2. Add a shared “modal already open / form interaction active” guard so exit intent never interrupts an open dialog, CAPTCHA, focused form field, dirty form, application flow, or thank-you page.
3. Enforce one exit prompt per session with one storage key and one analytics event.
4. Add proper dialog accessibility: `aria-modal`, initial focus, focus trap, Escape close, overlay close, and focus restoration.
5. Restore background scrolling/focus behavior correctly after close and prevent stacked overlays by automated test.
6. Use the public name “Commercial Lending Solutions” in all visible actions.
7. Add regression coverage that dispatches both `mouseout` and `mouseleave` and asserts that at most one visible dialog exists.
8. Test financing, property, blog, markets, landing, apply, thank-you, desktop, and mobile paths.
9. Validate explicit lead-event tracking after the fix; do not treat `ads_conversion_Contact_1` as a trustworthy conversion KPI until GTM is separately repaired.
10. Release the shared JavaScript fix separately and verify cache invalidation without regenerating unrelated author/location work.

---

### Task 1: Quarantine the primary checkout and establish an isolated implementation clone

**Objective:** Preserve the 5,285 tracked modifications and 17 untracked files in the primary checkout while preventing them from contaminating this release.

**Files:** None in the primary checkout.

**Steps:**

1. Quarantine the primary checkout: do not pull, reset, rebase, switch, stash, clean, regenerate, or use `git add -A` there.
2. Preserve the intentional author/image state, including untracked files, through an independently verified backup/manifest before any later manipulation of that checkout. Do not rely on a normal stash for a 5,285-file OneDrive tree.
3. In a fresh clone outside OneDrive, fetch `origin/main` immediately before implementation and record the exact remote SHA, local `HEAD`, divergence, and dirty-file count.
4. Pin the release baseline to the freshly fetched `origin/main`; do not base the release on the stale local `HEAD` or existing stale/locked worktrees.
5. Keep the seven local-only rate-update commits and dirty author/image work isolated. Reconcile or transplant only separately reviewed intentional changes; never merge the primary checkout wholesale.
6. Confirm the new clone is clean before editing and record its `core.autocrlf`/EOL behavior.
7. Never run `_generator/generate.py` in the dirty primary checkout.
8. After validation, move only the explicit release allowlist through a reviewed commit path from the clean clone; do not copy the remote-based release back into the dirty tree and push from there.

**Verification:** `git status --short` in the isolated clone returns no output before work begins, and the pinned baseline SHA equals the freshly fetched `origin/main`.

---

### Task 2: Add locations-hub regression tests first

**Objective:** Define the professional and crawl-safety contract before changing markup.

**Files:**
- Create: `_generator/tests/test_locations_hub.py`
- Read: `_generator/data/noindex_paths.json`
- Read: `_generator/data/redirect_map.json`
- Read: `_generator/data/cities.json`
- Validate: `locations.html`

**Required tests:**

1. Exactly one visible H1.
2. Canonical remains `https://clscre.com/locations.html`.
3. Page is indexable and remains in `sitemap-pages.xml`.
4. Visible public company naming uses “Commercial Lending Solutions”; “CLS CRE” may appear only as an alternate-name/entity reference where appropriate.
5. Page does not display “13,068 local pages,” “42 loan programs × 242 cities,” or equivalent factory language.
6. All 242 rendered market-hub URLs are reachable from the page exactly once, grouped for human navigation.
7. All 52 state destinations are available directly or through the linked state index.
8. No outbound hub link targets a path in `noindex_paths.json`.
9. No outbound hub link targets a source path in `redirect_map.json`.
10. Unique internal links stay below 600.
11. The page contains no city×program or city×property bulk link grid.
12. Structured data blocks parse as JSON.
13. Trevor Damyan, Commercial Mortgage Broker, CA DRE #02244836 appears once in the trust block.
14. The published minimum is $2MM wherever an engagement minimum is stated.

**Test command:**

`uv run --with pytest --with beautifulsoup4 pytest _generator/tests/test_locations_hub.py -q -p no:cacheprovider`

**Expected first result:** targeted failures against the current 13,000-link page.

---

### Task 3: Create a page-scoped visual system

**Objective:** Improve the locations experience without changing shared CSS used by thousands of pages.

**Files:**
- Create: `css/locations.css`
- Modify: `_generator/templates/locations.html` using `_base.html`’s existing `extra_meta` block to load the stylesheet only on this page

**Requirements:**

- Use existing brand tokens, fonts, spacing, and button conventions.
- Do not modify `css/pages.css` or `css/pages.min.css` in this release.
- Design for 390 px, 768 px, 1024 px, and 1440 px viewports.
- Avoid horizontal overflow.
- Use progressive disclosure and accessible native controls for the full market directory.
- Preserve keyboard navigation, visible focus, semantic headings, and reduced-motion behavior.

---

### Task 4: Rebuild the hub’s information hierarchy

**Objective:** Make the page a brokerage capability and market-discovery experience rather than a generated-URL inventory.

**Files:**
- Modify: `_generator/templates/locations.html`
- Potentially modify: `_generator/generate.py` near the current locations render block if explicit featured-market data must be supplied

**Required section order:**

1. **National financing hero**
   - Human-first nationwide capability statement
   - No generated-page counts
   - Primary CTA to `apply.html`
   - Secondary CTA to call/contact
2. **Verified brokerage proof**
   - Nationwide placement capability
   - 1,000+ lender relationships only if still verified
   - $2MM published minimum
   - Trevor Damyan / CA DRE #02244836
3. **Featured markets**
   - Controlled editorial set, not automatically “the first 12 cities”
   - Initial candidates must reconcile business priority with GSC/GA4 evidence; Los Angeles and Miami are evidence-backed, while other major markets require explicit selection rather than assumption
4. **How market conditions change financing**
   - Brief advisory explanation connecting local regulation, lender appetite, property types, and transaction structure
5. **Representative transactions**
   - Reuse the existing transaction data/partial
   - Only geographically accurate labels
6. **Browse all markets**
   - All 242 market hubs grouped by state or region
   - Accessible search/filter enhancement
   - Links go to `markets/{slug}/`, not every product/property permutation
7. **Browse by state**
   - Link the existing `/states/` architecture; do not create duplicate state pages
8. **Financing pathways**
   - Curated national hubs only: permanent, bridge, construction, commercial mortgage, life company, CMBS, multifamily, and other verified priority hubs
9. **Broker trust and CTA**
   - Portrait, name, role, concise biography, license, contact/application path

**Schema:** Keep the existing FinancialService and BreadcrumbList where accurate. Add at most one useful CollectionPage/ItemList representation for the curated market collection; do not add redundant schema types merely to increase schema count.

---

### Task 5: Render without full-site churn

**Objective:** Produce the generated page while touching only scoped artifacts.

**Files:**
- Generate: `locations.html`

**Steps:**

1. Render in the isolated clean clone outside OneDrive.
2. Inspect `git diff --stat` before transferring anything.
3. If full `generate.py` rewrites unrelated pages, discard those outputs and transfer only:
   - `_generator/templates/locations.html`
   - `_generator/generate.py` if intentionally changed
   - `_generator/tests/test_locations_hub.py`
   - `css/locations.css`
   - `locations.html`
4. Confirm no unrelated files differ in the release patch.

---

### Task 6: Validate source, mobile, accessibility, and performance

**Objective:** Prove that the page is professionally usable and does not regress crawl/index behavior.

**Automated checks:**

- Run the new locations test suite.
- Run `git diff --check`.
- Parse every JSON-LD block.
- Confirm no noindex/redirect targets in outbound links.
- Confirm 242 unique market hubs remain reachable.
- Confirm sitemap inclusion and self-canonical.
- Confirm no missing local assets.

**Live-local checks:**

1. Serve the isolated clone through a local HTTP server.
2. Capture Chrome screenshots at 390×844 and 1440×1000.
3. Verify `document.documentElement.scrollWidth <= window.innerWidth` at 390 px.
4. Verify keyboard access through search/filter, region/state controls, and CTAs.
5. Measure DOM and document size. Acceptance targets:
   - Under 600 unique internal links
   - Under 3,500 DOM elements
   - Under 300 KB uncompressed rendered HTML unless a documented accessibility requirement justifies more
6. Recheck PageSpeed field data after deployment; do not invent a lab score if the Windows Lighthouse launcher fails.

---

### Task 7: Review before any publication

**Objective:** Give Trevor an exact visual and technical diff before the page changes publicly.

**Deliverables:**

- Desktop screenshot
- Mobile screenshot
- Before/after link counts
- Before/after DOM and HTML size
- List of files changed
- Test output
- Confirmation that no city URL, canonical, title, H1, robots rule, redirect, newsletter, macro page, life-company page, or ED1 page changed

**Stop condition:** Do not commit, push, deploy, or submit for indexing until Trevor approves this review.

---

### Task 8: Measure the first release before changing city architecture

**Objective:** Separate the locations-hub UX repair from broader city-page decisions.

**Post-release windows:**

- Day 7: indexability, crawl errors, broken links, Core Web Vitals, GA4 sessions/engagement
- Day 14: query/page assignment anomalies
- Day 28: GSC impressions/clicks/CTR and explicit lead actions

**Rules:**

- Allow the July 27 hub-and-spoke change a full 28-day observation period before judging it.
- Use explicit events (`form_submit`, `web_sourced_lead`, `book_a_call`, `contact_click`) rather than generic `keyEvents` until GTM is repaired.
- Do not designate city-page winners or losers solely from the locations redesign.
- Any later flagship-city pilot requires a separate keep/improve/consolidate matrix based on current GSC, backlinks, conversion evidence, and deal relevance.

---

## Risks and tradeoffs

1. **Dirty checkout risk:** A full generator run in the primary checkout could mix thousands of blog author changes into this release. A fresh isolated clone outside OneDrive is mandatory; the primary checkout remains quarantined.
2. **Crawl-path risk:** Removing all market links would be unsafe. The redesigned hub must retain direct links to all 242 city authority hubs, even if presented through progressive disclosure.
3. **Premature cannibalization changes:** July 27 changes have not had time to settle. No mass city changes in this release.
4. **Conversion attribution risk:** GA4 generic key-event reporting is contaminated. Do not use it to rank markets.
5. **Shared CSS risk:** Editing `pages.css` would force broad cache-busting and could affect thousands of pages. Use `css/locations.css` only.
6. **Unsupported proof claims:** Every count, lender claim, minimum, transaction label, and geographic claim must be verified before display.
7. **SEO-looking AEO:** Answer-ready structure should remain semantic and source-backed, not presented as visible “Quick answer” or keyword scaffolding.

## Corrected recommendation

Proceed, after approval, with **one narrow locations-hub professionalization release**. Do not rebuild the state/city architecture and do not mass-edit city pages. The first release should remove stale links to noindexed permutations, preserve all city authority hubs, surface verified brokerage evidence, and create a premium market-discovery experience. Measure that release and the July 27 hub-and-spoke work before deciding on any broader city-page program.
