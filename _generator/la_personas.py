#!/usr/bin/env python3
"""
Los Angeles persona hub pages -- investors, developers, owner-users.

Rendered through the existing la_guide.html template (same shape as
la_vertical.py's RAW_GUIDES: slug, title, category, seo, hero_intro,
key_facts, sections, faqs) at /los-angeles/{slug}.html, alongside the
round-1 regulatory guides. Cross-links tie together every LA vertical
built so far: multifamily/la/, industrial/la/, retail/la/, and the
los-angeles/ guide set, so a visitor from any entry point can find the
buyer-type page that matches them, and vice versa.

Authored directly (not via agent fan-out): these are synthesis/cross-link
pages built from verticals that already exist elsewhere in the generator,
not new factual research, so hand-authoring kept voice and link accuracy
tightly controlled.
"""

RAW_PERSONAS = [
    {
        "slug": "investors",
        "title": "Los Angeles CRE Financing for Investors",
        "category": "Buyer Type",
        "seo": {
            "h1": "Los Angeles Commercial Real Estate Financing for Investors",
            "title": "LA CRE Financing for Investors | Commercial Lending Solutions",
            "meta_description": (
                "Acquisition, value-add, and income financing for LA multifamily, industrial, and "
                "retail investors: bridge, agency, bank, net-lease, and DSCR debt from a Los "
                "Angeles-based broker."
            ),
        },
        "hero_intro": (
            "Los Angeles rewards investors who understand its texture: which multifamily submarkets "
            "still have real turnover upside, which industrial corridors have genuine lease-up demand, "
            "which retail corridors are destination plays versus commodity strip centers. Commercial "
            "Lending Solutions places investor debt across all three property types, matched to the "
            "actual business plan, not a generic national underwriting box."
        ),
        "key_facts": [
            {"label": "Loan range", "value": "$1M to $100M+"},
            {"label": "Property types", "value": "Multifamily, industrial, retail, mixed-use"},
            {"label": "Typical response", "value": "Term sheet in 24 to 72 hours"},
            {"label": "Lender network", "value": "1,000+ relationships, all capital sources"},
        ],
        "sections": [
            {
                "heading": "What LA Investors Are Buying Right Now",
                "body": (
                    "Multifamily value-add remains the deepest trade in the county: buying a "
                    "rent-regulated building below market and executing a credible, unit-by-unit "
                    "turnover plan under Costa-Hawkins vacancy decontrol. That thesis plays out "
                    "differently by submarket, from the classic Sherman Oaks dingbat to a low-basis "
                    "South LA courtyard building, which is why we built neighborhood-level financing "
                    "detail for LA multifamily rather than treating the whole county the same.\n\n"
                    "Industrial investors are chasing infill logistics in the South Bay, rail-served "
                    "manufacturing conversions in Vernon and Commerce, and aerospace-adjacent flex space "
                    "near Inglewood and Hawthorne. Retail investors split between net-lease acquisitions "
                    "of credit-tenant pad sites and value-add plays on older strip centers along corridors "
                    "like Ventura Boulevard, where a repositioning and re-tenanting story can meaningfully "
                    "move rents."
                ),
            },
            {
                "heading": "Financing Investors Actually Use",
                "body": (
                    "Bridge debt funds the acquisition-and-execute thesis across all three property "
                    "types: renovate-at-turnover multifamily, lease-up industrial, and reposition retail. "
                    "Once the business plan is executed, the takeout shifts to whichever permanent capital "
                    "fits the stabilized asset: agency debt for multifamily, bank or life-company debt for "
                    "industrial, and net-lease or CMBS execution for retail.\n\n"
                    "DSCR loans have become a common tool for smaller, straightforward stabilized "
                    "acquisitions where speed and simplicity matter more than the last basis point of "
                    "leverage. And for investors selling one LA asset to buy another, 1031 exchange "
                    "timing (the 45-day identification and 180-day close windows) drives real urgency "
                    "into the financing timeline, which is exactly where a broker with 1,000+ lender "
                    "relationships can move faster than a single-source lender shopping."
                ),
            },
            {
                "heading": "The LA-Specific Things That Change Investor Math",
                "body": (
                    "Every LA investor deal runs into a local overlay that a generic national platform "
                    "will underprice or misprice. Multifamily buyers need to know which rent-control "
                    "regime applies and what Measure ULA does to a City of LA exit above $5 million. "
                    "Industrial buyers need to know whether a warehouse's size triggers SCAQMD's WAIRE "
                    "compliance program. Retail buyers need to know whether a drive-thru or alcohol use "
                    "needs a conditional use permit before it can operate.\n\n"
                    "None of this is disqualifying, but all of it changes proceeds, timeline, or exit "
                    "strategy if you find out about it after you are in contract instead of before."
                ),
            },
            {
                "heading": "Why a Local Broker Beats a National Platform Here",
                "body": (
                    "We are headquartered in Los Angeles. When we tell "
                    "a lender a deal is in Koreatown, Vernon, or on Abbot Kinney, we can describe the "
                    "actual submarket, not read a market report. That matters most in exactly the "
                    "moments a national platform struggles: pricing a regulated rent roll correctly, "
                    "explaining an entitlement nuance to an out-of-state lender, or getting a term sheet "
                    "revised in hours instead of days when a deal detail changes."
                ),
            },
        ],
        "faqs": [
            {
                "q": "What kind of down payment do LA investors typically need?",
                "a": (
                    "It depends on leverage and lender type, but a useful range is 25% to 40% down for "
                    "conventional bank and agency debt on stabilized assets, and somewhat less equity-heavy "
                    "structures are available through bridge lenders on value-add deals where the business "
                    "plan itself supports proceeds. Larger, well-capitalized sponsors on institutional-grade "
                    "assets can sometimes access higher leverage through life company or CMBS execution."
                ),
            },
            {
                "q": "Can I finance a 1031 exchange purchase quickly enough to meet the deadline?",
                "a": (
                    "Yes, this is one of the most common reasons investors come to us "
                    "rather than shopping a single lender. Bridge and DSCR lenders are built "
                    "for exchange timelines, and running your deal against 1,000+ lender relationships "
                    "simultaneously, instead of waiting on one bank's committee schedule, is how we help "
                    "sponsors hit the 45-day identification and 180-day close windows."
                ),
            },
            {
                "q": "Do you finance investors buying outside Los Angeles too?",
                "a": (
                    "Yes. Commercial Lending Solutions arranges commercial real estate loans nationwide "
                    "in all 50 states. LA is our home market and where our local knowledge runs deepest, "
                    "but the same 1,000+ lender network and $1 million to $100 million-plus loan range "
                    "applies everywhere we work."
                ),
            },
        ],
    },
    {
        "slug": "developers",
        "title": "Los Angeles CRE Financing for Developers",
        "category": "Buyer Type",
        "seo": {
            "h1": "Los Angeles Construction and Development Financing",
            "title": "LA Developer Financing | Construction Loans | Commercial Lending Solutions",
            "meta_description": (
                "Construction-to-takeout financing for LA developers: TOC multifamily, ED1 affordable, "
                "adaptive reuse, industrial, and retail ground-up projects from a Los Angeles broker."
            ),
        },
        "hero_intro": (
            "Los Angeles has more ways to build than almost any city in the country, and more ways for "
            "a construction loan to go wrong if the entitlement path is not understood before the "
            "capital stack is built. Commercial Lending Solutions arranges ground-up and adaptive-reuse "
            "construction financing across LA's major development programs, matched to a realistic "
            "timeline and a real takeout strategy."
        ),
        "key_facts": [
            {"label": "Loan range", "value": "$1M to $100M+"},
            {"label": "Project types", "value": "TOC multifamily, ED1 affordable, ARO, industrial, retail"},
            {"label": "Structure", "value": "Construction to bridge-to-perm or agency/HUD takeout"},
            {"label": "Lender network", "value": "1,000+ relationships, all capital sources"},
        ],
        "sections": [
            {
                "heading": "What LA Developers Are Building Right Now",
                "body": (
                    "TOC (Transit Oriented Communities) density bonuses have made transit-adjacent "
                    "multifamily construction the most active development product in the city, clustered "
                    "around the Purple Line extension in Koreatown, the Expo Line through Culver City and "
                    "Mar Vista, and the Red/Orange Line hub in North Hollywood. ED1 has opened a parallel "
                    "pipeline of 100% affordable projects with ministerial, non-discretionary approval, "
                    "removing much of the entitlement risk that used to slow affordable development to a "
                    "crawl.\n\n"
                    "The Adaptive Reuse Ordinance continues to convert older office and industrial stock, "
                    "concentrated in Downtown LA, into residential product with reduced parking "
                    "requirements. And outside the residential conversation entirely, ground-up industrial "
                    "and cold-storage development and retail and mixed-use projects each have their own "
                    "financing rhythm, covered in dedicated guides linked below."
                ),
            },
            {
                "heading": "Financing the Construction-to-Takeout Lifecycle",
                "body": (
                    "A construction loan is never the whole story. Construction and bridge-to-perm "
                    "lenders fund the build, sized to a detailed budget and draw schedule, but the deal "
                    "that actually gets financed at attractive terms is the one where the takeout is "
                    "planned from day one, not figured out after the certificate of occupancy.\n\n"
                    "TOC and market-rate multifamily typically takes out into agency debt (Fannie Mae or "
                    "Freddie Mac) once stabilized. ED1 and other affordable projects often layer HUD, bond, "
                    "or LIHTC-adjacent permanent financing on top of the construction loan. Industrial and "
                    "retail projects take out into bank, life-company, or CMBS permanent debt, or in some "
                    "cases a sale-leaseback exit instead of a refinance at all. Structuring the construction "
                    "loan with the actual takeout lender's requirements in mind avoids a scramble at "
                    "completion."
                ),
            },
            {
                "heading": "Entitlement Risk Is a Financing Question Too",
                "body": (
                    "Lenders price entitlement risk whether or not a developer thinks about it explicitly. "
                    "A TOC project with a confirmed tier and affordable set-aside gets priced differently "
                    "than one still working through zoning verification. An ED1 project with ministerial "
                    "approval already secured is a fundamentally lower-risk construction loan than a "
                    "discretionary approval still pending public hearing.\n\n"
                    "This is where a broker who actually understands LA's specific programs earns their "
                    "fee: presenting a construction request to lenders with the entitlement story already "
                    "de-risked in the package produces better terms than presenting the same physical "
                    "project with the entitlement question still open."
                ),
            },
            {
                "heading": "Guides for Every Development Path",
                "body": (
                    "Each major LA development program gets its own deep-dive guide covering the "
                    "mechanics and, more importantly, the financing implications: what changes for a "
                    "construction lender, what the realistic timeline looks like, and how the takeout "
                    "typically works. Start with the program your project actually uses rather than a "
                    "generic construction-lending overview."
                ),
            },
        ],
        "faqs": [
            {
                "q": "How does a TOC or ED1 project affect construction loan terms?",
                "a": (
                    "Both programs reduce entitlement risk and timeline uncertainty compared to a "
                    "discretionary approval, which lenders generally reward with more favorable "
                    "construction terms once the specific tier, density bonus, and affordable set-aside "
                    "are confirmed. Lenders still underwrite the blended pro forma carefully, since "
                    "affordable units rent below market and change the project's overall NOI."
                ),
            },
            {
                "q": "What is the difference between a construction loan and a bridge-to-perm loan?",
                "a": (
                    "A construction loan funds the build itself, disbursed in draws against a budget and "
                    "schedule, and typically converts or gets refinanced once the certificate of occupancy "
                    "is issued. A bridge-to-perm structure combines construction and initial stabilization "
                    "financing into one facility that carries the project through lease-up before a "
                    "permanent takeout, which can simplify the transition compared to arranging two "
                    "separate loans."
                ),
            },
            {
                "q": "Do you finance adaptive reuse and industrial construction, not just apartments?",
                "a": (
                    "Yes. Commercial Lending Solutions arranges construction financing across LA's full "
                    "development landscape: TOC and market-rate multifamily, ED1 affordable housing, "
                    "Adaptive Reuse Ordinance conversions, ground-up and cold-storage industrial, and "
                    "retail and mixed-use projects, each matched to lenders who understand that specific "
                    "product type and its takeout path."
                ),
            },
        ],
    },
    {
        "slug": "owner-users",
        "title": "Los Angeles CRE Financing for Owner-Users",
        "category": "Buyer Type",
        "seo": {
            "h1": "Los Angeles Owner-User Commercial Real Estate Financing",
            "title": "LA Owner-User Financing | SBA Loans | Commercial Lending Solutions",
            "meta_description": (
                "SBA 504 and 7(a) financing for LA business owners buying their own industrial, retail, "
                "or office building instead of leasing. Up to 90% financing from a Los Angeles broker."
            ),
        },
        "hero_intro": (
            "Los Angeles's commercial leasing market is tight and expensive enough that owning your "
            "building has become a genuine competitive advantage for many operating businesses, not "
            "just a real estate decision. Commercial Lending Solutions arranges SBA and conventional "
            "owner-user financing for LA business owners buying the space their business already "
            "occupies, or is about to."
        ),
        "key_facts": [
            {"label": "SBA 504 leverage", "value": "Up to 90% financing"},
            {"label": "Occupancy requirement", "value": "51%+ owner-occupied"},
            {"label": "Property types", "value": "Industrial, retail, office, medical"},
            {"label": "Loan range", "value": "$1M to $100M+"},
        ],
        "sections": [
            {
                "heading": "Why LA Business Owners Buy Instead of Lease",
                "body": (
                    "Owning removes the single biggest variable in a Los Angeles operating business's "
                    "cost structure: lease renewal risk. A tenant with a strong location and years of "
                    "buildout investment has real leverage taken away at every renewal negotiation, and "
                    "in tight submarkets like small-bay South Bay industrial or Ventura Boulevard retail, "
                    "the alternative space simply may not exist at a comparable price.\n\n"
                    "Ownership also builds equity in an appreciating asset instead of paying down someone "
                    "else's mortgage, and it locks in the largest fixed cost in the business at today's "
                    "terms rather than tomorrow's market rent. For many LA operators, the real estate "
                    "becomes as valuable as the business itself over a long hold."
                ),
            },
            {
                "heading": "SBA 504 and 7(a): The Owner-User Playbook",
                "body": (
                    "SBA 504 loans are purpose-built for exactly this: up to 90% total financing on an "
                    "owner-occupied commercial property, with a long-term, below-market fixed rate on the "
                    "second-lien portion funded through a Certified Development Company. SBA 7(a) offers "
                    "more flexibility, including financing for a business acquisition alongside the real "
                    "estate, at a somewhat lower maximum leverage.\n\n"
                    "The core eligibility requirement for either program is that the business must occupy "
                    "at least 51% of the property (for existing buildings; new construction has a higher "
                    "occupancy bar). That single rule is what separates an owner-user purchase from a "
                    "conventional investment acquisition in the eyes of every SBA lender."
                ),
            },
            {
                "heading": "Property Types That Work Best for Owner-Users in LA",
                "body": (
                    "Small-bay and flex industrial space is one of the strongest owner-user categories "
                    "in LA, particularly in submarkets like the San Fernando Valley and San Gabriel "
                    "Valley where a growing manufacturing or distribution business can outgrow leased "
                    "space and buy its next building instead. Retail pad sites, including auto-related "
                    "and quick-service concepts, are frequently owner-occupied rather than leased "
                    "investment product.\n\n"
                    "Medical and professional office is another deep owner-user category: a practice "
                    "with a stable patient or client base often has more certainty about its space needs "
                    "than a typical office tenant, which makes ownership a more comfortable long-term bet."
                ),
            },
            {
                "heading": "What Changes at Smaller Deal Sizes",
                "body": (
                    "Many owner-user transactions land at the smaller end of the commercial spectrum "
                    "relative to large institutional deals, and Commercial Lending Solutions works these "
                    "transactions starting at our $1 million minimum. At this size, local and regional "
                    "banks and credit unions with SBA lending programs are frequently the most competitive "
                    "capital sources, and relationship depth with the right lender matters more than it "
                    "does on a large institutional deal shopped to a dozen life companies."
                ),
            },
        ],
        "faqs": [
            {
                "q": "What is the minimum occupancy requirement for an SBA owner-user loan?",
                "a": (
                    "For an existing building, the business generally must occupy at least 51% of the "
                    "total square footage to qualify as owner-user under SBA 504 or 7(a) rules. New "
                    "construction typically carries a higher occupancy requirement. If your business will "
                    "occupy less than the required threshold, the deal is usually financed as a conventional "
                    "investment property instead."
                ),
            },
            {
                "q": "How much down payment does an SBA 504 loan require?",
                "a": (
                    "SBA 504 loans are structured to finance up to 90% of the total project cost in many "
                    "cases, meaning a down payment as low as 10% for a qualifying owner-occupied purchase, "
                    "well below typical conventional commercial down payment requirements. Exact leverage "
                    "depends on the specific business type, property type, and whether the transaction "
                    "involves new construction versus an existing building."
                ),
            },
            {
                "q": "Can I finance a business acquisition along with the real estate?",
                "a": (
                    "Yes, this is one of the main uses of an SBA 7(a) loan specifically: combining a "
                    "business acquisition with the purchase of the real estate the business operates "
                    "from, in a single financing structure. SBA 504 is generally used for real estate and "
                    "major fixed assets rather than business acquisition financing itself."
                ),
            },
        ],
    },
]


def build_personas() -> list:
    return RAW_PERSONAS
