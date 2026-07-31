# Protect-equity redirect release

- Prior map (HEAD): **82**
- New map: **461**
- Added: **379**
- Retargeted existing: **28**
- Removed: **0**
- Soft-301 stubs staged: **461**
- Bulk CSV: `cloudflare_bulk_redirects.csv` (301)

## Guarantees
- Every target is sitemap-active (`active_keep`)
- No self-redirects
- All 379 protect-equity candidates mapped
- `submit-deal.html` → `https://clscre.com/apply.html`
- 28 previously inactive redirect targets retargeted to active hubs

## Mapping policy
1. City financing / property permutations → active `markets/{city}/` when available
2. Else program/property hub (`financing/{program}.html` / `property/{type}.html`)
3. Blog guides → market hub or topical financing/property hub or `/blog/`
4. Never point at noindex/retired URLs

## Sample new mappings
| Source | Target |
|---|---|
| `submit-deal.html` | `https://clscre.com/apply.html` |
| `blog/agency-multifamily-financing-fannie-freddie-2026.html` | `https://clscre.com/financing/agency-loans.html` |
| `financing/bridge-loans-phoenix.html` | `https://clscre.com/markets/phoenix/` |
| `property/multifamily-san-diego.html` | `https://clscre.com/markets/san-diego/` |

## Notes
- Soft stubs ship immediately via Pages.
- Import `cloudflare_bulk_redirects.csv` in Cloudflare Bulk Redirects for true HTTP 301s (optional hardening).
- Soft-equity (~1,856) and full link-cleanup releases remain separate.
