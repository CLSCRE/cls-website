---
name: cls-cre-website-seo-engine
description: "Use this skill whenever the user asks to build, edit, or update website pages, work on SEO, create landing pages, or mentions 'website', 'homepage', 'clscre.com', 'SEO', 'landing page', 'web page', or 'site rebuild'. This skill manages the full website rebuild for Commercial Lending Solutions with programmatic SEO."
---

# Skill 2: CLS CRE Website & SEO Engine

## Overview
Full website rebuild for Commercial Lending Solutions (commerciallendingsolutions.ai) with programmatic SEO targeting commercial real estate borrowers across all loan types, property types, and geographic markets.

## Live Test Site
- **URL**: https://clscre.github.io/cls-website/
- **Repo**: https://github.com/CLSCRE/cls-website
- **Deploy**: Push to `main` branch auto-deploys via GitHub Pages

## Design System (CBRE/JLL Inspired — Bright & Vibrant)

### Colors
| Token | Value | Usage |
|-------|-------|-------|
| `--navy` | `#153D63` | Headings, accent sections (stats bar, differentiators, footer) |
| `--green` | `#006A4E` | CTAs, links, hover states, accent labels |
| `--green-bright` | `#00A676` | Pulse dot, bright accents on dark backgrounds |
| `--white` | `#FFFFFF` | Primary background — white-dominant design |
| `--gray-50` | `#F9FAFB` | Alternate section backgrounds |
| `--gold` | `#C5A355` | Logo accent only (not used in UI) |

### Typography
- **Display**: DM Serif Display (headings, stats, rate values)
- **Body**: Inter (all body text, labels, nav)
- Sizes: Hero h1 clamp(36px, 4.5vw, 56px), section titles clamp(28px, 3vw, 42px)

### Design Principles
- White-dominant backgrounds (not dark navy like v1)
- Lots of breathing room / white space
- Green accent lines and hover states (inspired by CBRE's teal)
- Clean card-based layouts with subtle shadows
- Scroll reveal animations (fade-up on intersection)
- Mobile-responsive at 1024px and 768px breakpoints

## Brand Assets
| Asset | File | Usage |
|-------|------|-------|
| Skyline Logo (light bg) | `images/cls-logo-skyline.png` | Nav bar, footer |
| Badge Logo (dark bg) | `images/cls-logo-badge.png` | Dark sections, favicon |
| Trevor Headshot | `images/trevor-damyan.jpg` | About section |

## Homepage Sections (Built)
1. **Nav** — Fixed, white bg, dropdown for Financing, smooth-scroll links
2. **Hero** — Tagline + rate widget (Bloomberg-style with pulsing green dot)
3. **Stats Bar** — ~$1B, 1,000+, 20-50 deals, 50 states (navy bg)
4. **Services** — 6 loan type cards with green hover effect
5. **Recent Deals** — 4 deal cards (funded + under application)
6. **Market Indices** — 10 indices table (treasuries, equities, gold, silver, bitcoin) with Today/Yesterday/Last Month/Last Year
7. **Yield Curve** — SVG chart, current vs 1 year ago
8. **Economic Calendar** — 6 upcoming macro events with impact ratings
9. **Differentiators** — 4 cards on navy bg (pedigree, life co access, creative structuring, AI tools)
10. **About Preview** — Trevor headshot + bio
11. **CTA** — Email + call buttons
12. **Footer** — 4-column grid, social links

## Programmatic SEO — Page Architecture (18+ Pages)

### Phase 1: Core Pages (Build First)
| Page | Target Keyword | URL |
|------|---------------|-----|
| Homepage | commercial mortgage broker los angeles | `/` |
| About | commercial lending solutions about | `/about` |
| Contact | commercial loan quote | `/contact` |

### Phase 2: Loan Type Pages (6 pages)
| Page | Target Keyword | URL |
|------|---------------|-----|
| Permanent Loans | commercial permanent loan broker | `/financing/permanent-loans` |
| Construction Loans | construction loan broker los angeles | `/financing/construction-loans` |
| Bridge Loans | commercial bridge loan broker | `/financing/bridge-loans` |
| SBA 504/7(a) | sba 504 loan broker los angeles | `/financing/sba-loans` |
| Mezzanine/Pref Equity | mezzanine financing commercial real estate | `/financing/mezzanine` |
| Specialty Assets | specialty asset commercial financing | `/financing/specialty` |

### Phase 3: Property Type Pages (6 pages)
| Page | Target Keyword | URL |
|------|---------------|-----|
| Multifamily | multifamily loan broker los angeles | `/property/multifamily` |
| Industrial | industrial property loan broker | `/property/industrial` |
| Retail | retail commercial mortgage broker | `/property/retail` |
| Office | office building financing | `/property/office` |
| Mixed-Use | mixed use property loan | `/property/mixed-use` |
| Hospitality | hotel financing broker | `/property/hospitality` |

### Phase 4: Programmatic SEO Landing Pages (Scale)
Template-driven pages for every combination of:
- `{loan_type}` x `{city}` (e.g., "Bridge Loan Broker in Phoenix AZ")
- `{property_type}` x `{city}` (e.g., "Multifamily Financing in Los Angeles")
- Target 50-100+ pages for long-tail keyword capture

### Phase 5: Content Hub
- Market Data page (expanded indices, yield curve, economic calendar)
- Blog/insights (rate commentary, deal case studies)
- AI Tools page (link to clscre.ai)

## Technical Stack
- **Static HTML/CSS/JS** — no framework, maximum performance
- **Hosting**: GitHub Pages (test) → Netlify or custom domain (production)
- **Domain**: commerciallendingsolutions.ai (target)
- **Performance targets**: Lighthouse 95+, < 2s load, < 500KB total
- **SEO**: Schema.org FinancialService markup, Open Graph, canonical URLs

## Build Status
| Phase | Status | Notes |
|-------|--------|-------|
| Homepage v1 (dark navy) | Rejected | User didn't like dark/heavy feel |
| Homepage v2 (bright/CBRE) | **LIVE** | Deployed to GitHub Pages |
| Nav link fix | Done | Dropdown links scroll to specific service cards |
| Market Data page | **LIVE** | Treasury yields, yield curve, economic calendar |
| Loan type hub pages (6) | **LIVE** | Jinja2 generator, Schema.org, FAQ, cross-links |
| Property type hub pages (6) | **LIVE** | Same generator, filtered transactions per type |
| Programmatic SEO city pages (180) | **LIVE** | 15 cities x 6 loan types + 15 cities x 6 property types |
| Sitemap + robots.txt | **LIVE** | 196 URLs in sitemap.xml |
| About page | **LIVE** | Team bios, company story, timeline, differentiators |
| Contact page | **LIVE** | Quote form, contact info, hours, process steps |
| Custom domain | **LIVE** | commerciallendingsolutions.ai → GitHub Pages, HTTPS enforced |
| Google Search Console | **LIVE** | Sitemap submitted, 196 pages discovered |
| Blog / Insights | Not started | Rate commentary, deal case studies |

## Content Rules
- **Voice**: Professional, authoritative, deal-focused — "capital markets insider, not salesperson"
- **Privacy**: Never name borrowers. Lenders anonymous by default. City-level addresses only.
- **Stats to highlight**: ~$1B volume, 1,000+ lender relationships, 20-50 deals/year, 50 states
- **Key differentiators**: CBRE/MMCC pedigree, direct life insurance company access, creative structuring, free AI tools
- **CTA**: Always drive to contact (email/phone) or AI tools (clscre.ai)
