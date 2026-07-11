#!/usr/bin/env python3
"""
Los Angeles neighborhood-financing vertical -- data + builders.

Feeds la_hub.html, la_guide.html, la_apartment_page.html, and
la_apartments_index.html (templates authored 2026-07-10, wired in 2026-07-11).

Design note (scope decision, 2026-07-11): rather than mail-merging the
canonical ~114-neighborhood LA list, this module curates ~30 genuinely
distinct investment submarkets, grouping adjacent micro-neighborhoods that
share the same rent-regulation regime and building stock (e.g. Highland
Park + Eagle Rock + Mount Washington as one "Northeast LA" submarket)
rather than atomizing every one. Depth over breadth: every hood below has
a distinct vintage/character/financing-angle, not a template with the
name swapped in. See feedback_professional_channel_priority in the
assistant's memory for the "deeper, not wider" standard this follows.

Regulatory grounding: the dev-tool-la-regulatory skill (RSO, Measure ULA,
seismic retrofit ordinances, TOC, ARO, Costa-Hawkins, Ellis Act, Mello Act,
Hillside/BMO) plus the jurisdiction facts already hardcoded in
tool_la_rentcontrol.html (City of LA RSO pre-10/1/1978 cutoff; AB 1482
statewide 15-year/5%+CPI/10%-cap; Santa Monica pre-4/10/1979; West
Hollywood pre-7/1/1979; Beverly Hills/Culver City/Inglewood/Pasadena/
unincorporated LA County pre-2/1995 Costa-Hawkins line). Neighborhood-level
claims (which submarket, what stock looks like, deal profile) are kept
general/conservative rather than inventing precise boundaries, addresses,
or dates that cannot be verified -- consistent with the "verify specifics
with the city or counsel" disclaimer voice already used on
tool_la_rentcontrol.html and in the affordable-housing LIHTC pages.
"""

# ── Jurisdiction rent-regulation facts (shared, one source of truth) ────
# Mirrors the logic already hardcoded in tool_la_rentcontrol.html's JS so
# the guide/hood prose never contradicts the interactive checker.
JURISDICTIONS = {
    "la": {
        "label": "City of LA RSO / AB 1482",
        "text": (
            "Buildings with a certificate of occupancy on or before October 1, 1978 and two or more "
            "units generally fall under the City of Los Angeles Rent Stabilization Ordinance (RSO): "
            "CPI-formula annual increases, relocation and just-cause rules, and SCEP inspection "
            "requirements. Buildings built after that date are generally exempt from RSO; once they "
            "reach 15 years old, statewide AB 1482 applies instead, capping increases at 5% plus local "
            "CPI (10% maximum) with just-cause eviction protections. Costa-Hawkins vacancy decontrol "
            "lets rents reset to market when a regulated unit turns over, under either regime."
        ),
    },
    "santa_monica": {
        "label": "Santa Monica Rent Control",
        "text": (
            "Buildings built before April 10, 1979 fall under Santa Monica's charter rent control, one "
            "of the strictest rent regimes in the country, with its own Rent Control Board, registration "
            "requirements, and narrow eviction grounds. Buildings 15 years or older that postdate that "
            "cutoff fall under statewide AB 1482 (5% plus CPI, 10% cap) instead. Costa-Hawkins vacancy "
            "decontrol applies at turnover either way, and the city's Measure GS layers on a 5.6% transfer "
            "tax on sales above roughly $8 million that shapes exit math independent of the rent regime."
        ),
    },
    "west_hollywood": {
        "label": "West Hollywood RSO",
        "text": (
            "Buildings built before July 1, 1979 fall under West Hollywood's rent stabilization "
            "ordinance, with its own annual increase formula and strong tenant protections. Buildings "
            "15 years or older that postdate that cutoff fall under statewide AB 1482 instead. "
            "Costa-Hawkins vacancy decontrol applies at turnover under either regime."
        ),
    },
    "beverly_hills": {
        "label": "Beverly Hills Rent Stabilization",
        "text": (
            "Buildings built before February 1995, the statewide Costa-Hawkins cutoff, generally fall "
            "under Beverly Hills' rent stabilization program, with CPI-tied annual caps set under the "
            "city's rent stabilization chapters. Newer buildings 15 years or older fall under statewide "
            "AB 1482 instead. Vacancy decontrol applies at turnover under either regime."
        ),
    },
    "culver_city": {
        "label": "Culver City Rent Control",
        "text": (
            "Buildings built before February 1995 generally fall under Culver City's rent control "
            "ordinance, with a CPI-tied annual cap generally in the 2% to 5% band. Newer buildings 15 "
            "years or older fall under statewide AB 1482 instead. Costa-Hawkins vacancy decontrol applies "
            "at turnover, and the city's Measure RE layers on a tiered transfer tax reaching 4% on sales "
            "of $10 million or more."
        ),
    },
    "inglewood": {
        "label": "Inglewood Rent Control",
        "text": (
            "Buildings built before February 1995 generally fall under Inglewood's rent control ordinance "
            "(adopted 2019), with CPI-tied annual caps. Newer buildings 15 years or older fall under "
            "statewide AB 1482 instead. Costa-Hawkins vacancy decontrol applies at turnover under either regime."
        ),
    },
    "pasadena": {
        "label": "Pasadena Measure H Rent Control",
        "text": (
            "Buildings built before February 1995 generally fall under Pasadena's Measure H rent control, "
            "which caps annual increases at 75% of CPI and is administered by a city rental board. Newer "
            "buildings 15 years or older fall under statewide AB 1482 instead. Costa-Hawkins vacancy "
            "decontrol applies at turnover under either regime."
        ),
    },
    "county": {
        "label": "Unincorporated LA County RSO",
        "text": (
            "Buildings built before February 1995 in unincorporated Los Angeles County generally fall "
            "under the county's rent stabilization ordinance, with CPI-tied annual caps. Newer buildings "
            "15 years or older fall under statewide AB 1482 instead. Costa-Hawkins vacancy decontrol "
            "applies at turnover under either regime, and county (not City of LA) planning and permitting "
            "rules govern entitlements here."
        ),
    },
    "none_local": {
        "label": "AB 1482 only (no local ordinance)",
        "text": (
            "This city has no rent stabilization ordinance of its own, so statewide AB 1482 is the "
            "controlling regulation: buildings 15 years or older are capped at 5% plus local CPI (10% "
            "maximum) with just-cause eviction rules, while newer construction is exempt during its "
            "first 15 years. That makes this one of the more conventionally underwritten apartment "
            "submarkets in the county."
        ),
    },
}

DISCLAIMER = (
    "Rent-regulation coverage has exemptions and edge cases (owner move-ins, condo conversions, "
    "deed-restricted units, and city-specific carve-outs). Confirm the applicable ordinance and any "
    "recent amendments with the city rent board, LA County, or counsel before underwriting a specific "
    "building."
)

REGION_ORDER = [
    "Central LA & Downtown",
    "Eastside",
    "South LA",
    "Westside",
    "San Fernando Valley",
    "South Bay & Harbor",
    "Pasadena & San Gabriel Valley",
    "Unincorporated LA County",
]

# ── Raw neighborhood facts (curated, ~30 distinct submarkets) ───────────
# Each entry: name, region, jurisdiction key, plus hand-authored fields
# that make the page genuinely differentiated: vintage/character overview,
# a real financing angle (what lenders like/dislike, typical deal profile),
# and 2-3 watch items specific to that submarket.
RAW_HOODS = [
    # ── Central LA & Downtown ──
    {
        "name": "Downtown LA (DTLA)",
        "slug": "downtown-la",
        "region": "Central LA & Downtown",
        "jurisdiction": "la",
        "extra_note": (
            "DTLA also sits inside the Adaptive Reuse Ordinance (ARO) footprint, which lets older "
            "commercial and industrial buildings convert to residential with reduced parking, no "
            "density limit, and expedited plan check -- a distinct, exempt-from-RSO product line "
            "alongside the historic core's pre-1978 stock."
        ),
        "overview": (
            "Downtown LA runs two very different apartment products side by side: pre-1978 RSO "
            "buildings in the historic core and Old Bank District, and adaptive-reuse conversions of "
            "old office and industrial stock into loft-style units under the ARO. Density is the "
            "highest in the city, and several TOC-eligible parcels sit within a few blocks of Metro "
            "Rail's 7th/Metro and Pershing Square stations.\n\nInvestor interest splits between "
            "value-add plays on the RSO stock and ground-up or conversion deals riding the ARO's "
            "relaxed parking and density rules. Basis and rent growth expectations differ sharply "
            "between the two products, so lenders want to know which one they are underwriting before "
            "they price a deal."
        ),
        "financing_playbook": (
            "ARO conversions and TOC-eligible construction draw construction and bridge-to-perm capital "
            "comfortable with entitlement nuance; agency and life-company lenders take the stabilized "
            "exit once lease-up is done. RSO value-add deals in the historic core get financed against "
            "a credible turnover schedule, with local banks and bridge funds most active on smaller "
            "(20-80 unit) assets."
        ),
        "watch_items": [
            "Confirm whether a specific building qualifies for ARO before underwriting reduced parking or density.",
            "TOC affordable-unit set-asides (8-25% depending on tier) affect proceeds on new construction.",
            "Soft-story and non-ductile concrete retrofit status on older stock is a first diligence question.",
        ],
    },
    {
        "name": "Koreatown",
        "slug": "koreatown",
        "region": "Central LA & Downtown",
        "jurisdiction": "la",
        "overview": (
            "Koreatown is the densest residential submarket in Los Angeles: block after block of "
            "pre-1978 dingbat and courtyard apartment buildings, most of them under RSO, layered with "
            "newer TOC-bonused construction along the Wilshire and Vermont corridors near the Purple "
            "Line extension. It is a classic value-add hunting ground for investors comfortable with "
            "regulated rolls.\n\nThe combination of high unit counts per parcel, strong rental demand, "
            "and a steady stream of turnover makes Koreatown one of the most actively traded RSO "
            "submarkets in the city, with cap rates that reflect both the regulatory overlay and the "
            "density."
        ),
        "financing_playbook": (
            "Bridge lenders are comfortable here financing renovate-at-turnover business plans against "
            "a large, granular rent roll; agency and bank debt take the stabilized refinance once "
            "unit-by-unit turns are complete. TOC construction along the Purple Line extension corridor "
            "is a distinct, higher-leverage product that draws construction lenders separately from the "
            "RSO value-add crowd."
        ),
        "watch_items": [
            "Soft-story retrofit exposure is high on 1960s-70s dingbat stock -- verify completion before pricing.",
            "Turnover-based underwriting needs a realistic, unit-by-unit renovation and re-lease schedule.",
            "TOC density bonus parcels require affordable set-asides that change the pro forma.",
        ],
    },
    {
        "name": "Westlake / Pico-Union",
        "slug": "westlake-pico-union",
        "region": "Central LA & Downtown",
        "jurisdiction": "la",
        "overview": (
            "Westlake and Pico-Union carry some of the oldest and densest RSO apartment stock in the "
            "city, much of it built in the early-to-mid 20th century for a working-class, immigrant-"
            "serving tenant base near Downtown and USC. Basis per unit is among the lowest in central "
            "LA, and building conditions vary widely.\n\nThe investor base here skews toward "
            "experienced regulated-housing operators rather than first-time buyers: managing an RSO "
            "roll, relocation obligations, and deferred maintenance in the same building takes a "
            "specific skill set, and lenders underwrite accordingly."
        ),
        "financing_playbook": (
            "Local banks and credit unions with deep RSO experience are the most active lenders here, "
            "typically underwriting to in-place regulated rents with conservative expense assumptions "
            "given older building conditions. Bridge capital funds capital-improvement plans, but wants "
            "a sponsor with a track record managing regulated tenancies, not a first-time investor."
        ),
        "watch_items": [
            "Deferred maintenance and code compliance history should be part of underwriting, not an afterthought.",
            "Relocation cost exposure on any unit-vacate plan is meaningful; budget $10K-$25K per household.",
            "Building vintage skews pre-1960s in pockets -- confirm soft-story and URM retrofit status.",
        ],
    },
    {
        "name": "Mid-Wilshire",
        "slug": "mid-wilshire",
        "region": "Central LA & Downtown",
        "jurisdiction": "la",
        "overview": (
            "Mid-Wilshire's apartment stock is dominated by 1920s-1960s courtyard and garden-style "
            "buildings under RSO, clustered around the Miracle Mile and the museum row corridor. It is "
            "a more architecturally distinctive submarket than its Koreatown neighbor, and several "
            "older office buildings along Wilshire have been floated as adaptive-reuse or conversion "
            "candidates.\n\nBuyers here range from long-hold family owners to value-add investors "
            "targeting the courtyard product for light renovation and re-lease, with an increasing "
            "number of 1031 exchange buyers drawn to the location's proximity to Koreatown and DTLA "
            "employment."
        ),
        "financing_playbook": (
            "Bank and credit union debt is the default for stabilized courtyard buildings; bridge "
            "lenders fund the renovate-and-turn plan on properties with older finishes and below-market "
            "in-place rents. Office-to-residential conversion candidates along Wilshire need a lender "
            "comfortable underwriting entitlement risk rather than a straightforward rent roll."
        ),
        "watch_items": [
            "Confirm RSO cutoff (10/1/1978) status before assuming a building is regulated or exempt.",
            "Historic Preservation Overlay Zones (HPOZ) exist in pockets and can affect renovation scope.",
            "Soft-story retrofit status on pre-1978 wood-frame buildings is a standard diligence item.",
        ],
    },
    {
        "name": "Mid-City",
        "slug": "mid-city",
        "region": "Central LA & Downtown",
        "jurisdiction": "la",
        "overview": (
            "Mid-City is a transitional RSO submarket between Koreatown, West Adams, and the Fairfax "
            "district, with a mix of older dingbat and courtyard apartments alongside newer infill "
            "along transit corridors served by Metro's D Line and Rapid bus routes. Rents sit below "
            "the westside but above the deepest-value South LA submarkets.\n\nIt has become a favored "
            "target for value-add investors priced out of Koreatown and Mid-Wilshire, looking for "
            "similar regulated-roll fundamentals at a lower basis with comparable turnover upside."
        ),
        "financing_playbook": (
            "Bridge lenders active in Koreatown and Mid-Wilshire extend into Mid-City on the same "
            "renovate-at-turnover thesis, typically at a lower basis per unit. Community banks and "
            "credit unions compete for stabilized refinances once a turnover plan is executed."
        ),
        "watch_items": [
            "Confirm exact RSO vs. AB 1482 status; building vintage varies block to block.",
            "TOC-eligible parcels along transit corridors carry affordable set-aside requirements.",
            "Verify soft-story retrofit completion on older wood-frame buildings.",
        ],
    },
    # ── Eastside ──
    {
        "name": "Silver Lake / Echo Park",
        "slug": "silver-lake-echo-park",
        "region": "Eastside",
        "jurisdiction": "la",
        "overview": (
            "Silver Lake and Echo Park pair small-scale 1920s-1960s courtyard and dingbat apartment "
            "buildings, mostly under RSO, with a hillside topography that constrains new construction "
            "in pockets. The submarket has gentrified steadily, and rents now sit well above the "
            "eastside average even as the regulated-roll stock underneath has not changed.\n\nMost "
            "trades are small (6-24 unit) buildings bought by local operators and family offices "
            "executing light-touch renovation programs rather than large institutional value-add "
            "plans, given the granularity of the stock."
        ),
        "financing_playbook": (
            "Local and regional banks are the most natural fit for the smaller regulated buildings "
            "that dominate this submarket; bridge debt funds the light-renovation, unit-turn business "
            "plan. Hillside Ordinance restrictions apply to any ground-up or ADU addition on sloped "
            "parcels and should be flagged early in underwriting."
        ),
        "watch_items": [
            "Hillside Ordinance parcels face FAR, grading, and fire-access (26-foot road) restrictions.",
            "Small unit counts mean per-unit renovation cost assumptions matter more than in larger assets.",
            "Verify RSO cutoff and any HPOZ overlay before assuming renovation scope.",
        ],
    },
    {
        "name": "Northeast LA (Highland Park, Eagle Rock, Mount Washington)",
        "slug": "northeast-la",
        "region": "Eastside",
        "jurisdiction": "la",
        "overview": (
            "Northeast LA's bungalow courts and small multifamily buildings, most built before 1978 and "
            "under RSO, have seen some of the fastest rent growth on the eastside over the past decade "
            "as the corridor gentrified along the Gold Line. Building stock is smaller-scale than "
            "Koreatown or Mid-Wilshire, with fewer large apartment complexes and more 4-16 unit "
            "buildings.\n\nHistoric Preservation Overlay Zones are common in pockets of Highland Park "
            "and Mount Washington, which constrains renovation and demolition scope on older buildings "
            "even where RSO relocation rules would otherwise allow it."
        ),
        "financing_playbook": (
            "Community banks and credit unions dominate lending on the smaller regulated buildings "
            "typical of this submarket; bridge capital is available but sized conservatively given "
            "granular unit counts. Buyers are frequently local operators and first-time syndicators "
            "rather than institutional funds."
        ),
        "watch_items": [
            "HPOZ overlays in pockets of Highland Park and Mount Washington can block or limit renovation scope.",
            "Hillside topography in Mount Washington triggers the Hillside Ordinance on some parcels.",
            "Soft-story retrofit status on pre-1978 wood-frame buildings should be confirmed early.",
        ],
    },
    {
        "name": "Boyle Heights / East LA",
        "slug": "boyle-heights-east-la",
        "region": "Eastside",
        "jurisdiction": "la",
        "extra_note": (
            "Boyle Heights sits inside the City of LA and is governed by RSO; East LA immediately east "
            "of the Boyle Heights line is unincorporated Los Angeles County and falls under the "
            "county's own rent stabilization ordinance and permitting authority instead. Confirm which "
            "jurisdiction a specific parcel sits in before underwriting."
        ),
        "overview": (
            "Boyle Heights and East LA together form one of the lowest-basis apartment submarkets "
            "close to Downtown LA, dominated by older RSO (City) and county-regulated (unincorporated) "
            "multifamily stock serving a long-established, largely Latino renter base. Redevelopment "
            "pressure and tenant-protection sensitivity are both high here, and community opposition to "
            "displacement has shaped several recent projects.\n\nInvestors here tend to be long-hold "
            "local owners or value-add buyers with genuine experience in regulated, tenant-protection-"
            "sensitive submarkets; this is not a straightforward market-rate underwriting exercise."
        ),
        "financing_playbook": (
            "Community banks and CDFIs with local relationships are the most common lenders; bridge "
            "capital is selective and wants a sponsor with a credible, respectful relocation and "
            "renovation plan rather than an aggressive turnover assumption. Basis is low enough that "
            "even modest rent growth can produce attractive yield on cost for patient capital."
        ),
        "watch_items": [
            "Confirm City of LA (RSO) vs. unincorporated LA County jurisdiction before underwriting a specific parcel.",
            "Relocation and just-cause obligations are actively enforced; budget realistically, not optimistically.",
            "Community and tenant-advocacy scrutiny on redevelopment projects can extend entitlement timelines.",
        ],
    },
    # ── South LA ──
    {
        "name": "South LA (West Adams, Leimert Park, Historic South-Central)",
        "slug": "south-la",
        "region": "South LA",
        "jurisdiction": "la",
        "overview": (
            "South LA carries the lowest apartment basis per unit inside the City of LA, with a large "
            "stock of older RSO courtyard and dingbat buildings and steady renter demand from a "
            "long-established community. Metro's Crenshaw/K Line has brought new TOC-eligible "
            "construction interest to West Adams and Leimert Park specifically, alongside the "
            "value-add trade in older regulated buildings.\n\nThis is one of the more active "
            "renovate-at-turnover submarkets in the city precisely because the basis-to-rent-growth "
            "math works: modest capital improvements on a low-basis acquisition can produce outsized "
            "yield when units turn over into a strengthening rental market."
        ),
        "financing_playbook": (
            "Bridge lenders are highly active on the renovate-at-turnover thesis given the basis "
            "advantage; agency and bank debt take the stabilized refinance. TOC construction near "
            "Crenshaw/K Line stations is a distinct, growing product line that draws construction "
            "lenders comfortable with a still-emerging submarket."
        ),
        "watch_items": [
            "Verify RSO cutoff and relocation obligations before underwriting any unit-vacate renovation plan.",
            "TOC affordable set-asides apply to new construction near Metro Crenshaw/K Line stations.",
            "Soft-story retrofit status on older wood-frame stock is a standard first diligence item.",
        ],
    },
    {
        "name": "Exposition Park / University Park (USC-adjacent)",
        "slug": "exposition-park-university-park",
        "region": "South LA",
        "jurisdiction": "la",
        "overview": (
            "The USC-adjacent submarket blends older RSO apartment stock with student and "
            "workforce-housing demand that keeps occupancy unusually steady regardless of broader "
            "market cycles. Several blocks have seen newer, larger student-oriented developments "
            "alongside legacy regulated buildings that predate the university's most recent growth.\n\n"
            "Investors here are often drawn less by rent growth potential and more by occupancy "
            "stability: a captive student and staff renter base provides a floor that is harder to "
            "find in more cyclical LA submarkets."
        ),
        "financing_playbook": (
            "Lenders underwrite the steady, semester-driven occupancy pattern favorably, and bank debt "
            "is comfortable on stabilized regulated buildings here. Bridge capital funds renovation "
            "plans aimed at repositioning older units for student or young-professional tenants."
        ),
        "watch_items": [
            "Confirm RSO status and any exemptions tied to university-affiliated housing arrangements.",
            "Academic-calendar-driven leasing patterns should inform turnover and vacancy assumptions.",
            "Verify soft-story retrofit completion on older wood-frame buildings near campus.",
        ],
    },
    # ── Westside ──
    {
        "name": "Venice",
        "slug": "venice",
        "region": "Westside",
        "jurisdiction": "la",
        "extra_note": (
            "Venice sits within the California Coastal Zone, which layers Coastal Development Permit "
            "(CDP) review and Mello Act affordable-unit replacement requirements on top of City of LA "
            "RSO/AB 1482 rent regulation -- a materially different entitlement process than inland LA."
        ),
        "overview": (
            "Venice combines the highest rents on the LA coastline with an older RSO apartment stock on "
            "small, often narrow lots, plus Coastal Zone jurisdiction that adds Coastal Development "
            "Permit review to nearly any redevelopment or major renovation. Demolishing regulated units "
            "here also triggers the Mello Act's 1:1 affordable-replacement requirement.\n\nThe result "
            "is a submarket where the underlying real estate value is exceptional but the entitlement "
            "and regulatory path is unusually complex, favoring sponsors with coastal development "
            "experience over first-time value-add buyers."
        ),
        "financing_playbook": (
            "Bridge and private capital that understand coastal entitlement timelines (6-18 months "
            "longer than inland projects) are the natural fit for redevelopment plays; banks and life "
            "companies compete aggressively for stabilized, already-entitled product given the location. "
            "Mello Act replacement-housing obligations should be priced into any acquisition involving "
            "existing regulated units."
        ),
        "watch_items": [
            "Coastal Development Permit review adds 6-18 months and real uncertainty to any major project.",
            "Mello Act 1:1 affordable-unit replacement applies to demolition of existing regulated units.",
            "Small, narrow lot sizes constrain unit-count expansion relative to inland submarkets.",
        ],
    },
    {
        "name": "Mar Vista / Palms",
        "slug": "mar-vista-palms",
        "region": "Westside",
        "jurisdiction": "la",
        "overview": (
            "Mar Vista and Palms sit in the transitional zone between the westside's high-cost core and "
            "more affordable inland submarkets, with a mix of RSO-regulated older buildings and newer "
            "construction along the Metro E (Expo) Line corridor. TOC density bonuses have driven "
            "several construction projects near Expo stations in recent years.\n\nThe buyer pool skews "
            "toward 1031 exchange investors and family offices seeking westside-adjacent stability "
            "without Santa Monica or Venice pricing, alongside developers targeting the TOC corridor "
            "for ground-up product."
        ),
        "financing_playbook": (
            "Agency and bank debt are readily available for stabilized RSO buildings here; construction "
            "and bridge-to-perm capital fund the growing TOC pipeline along the Expo Line. This is a "
            "comparatively liquid westside-adjacent submarket for both loan types."
        ),
        "watch_items": [
            "TOC density bonus parcels near Expo Line stations carry affordable set-aside obligations.",
            "Confirm RSO cutoff status; building vintage is more mixed here than in Venice or Santa Monica.",
            "Verify soft-story retrofit completion on pre-1978 wood-frame buildings.",
        ],
    },
    {
        "name": "Santa Monica",
        "slug": "santa-monica",
        "region": "Westside",
        "jurisdiction": "santa_monica",
        "overview": (
            "Santa Monica is its own incorporated city with the strictest rent control regime in Los "
            "Angeles County, applied to a large stock of pre-1979 apartment buildings alongside newer, "
            "exempt construction closer to the beach and downtown core. It is also one of the most "
            "institutionally owned apartment submarkets on the westside.\n\nMeasure GS, the city's own "
            "transfer tax on sales above roughly $8 million, reshapes hold-versus-sell decisions "
            "independent of the rent-control question, and is a standard part of exit underwriting here."
        ),
        "financing_playbook": (
            "Life companies, agency lenders, and large regional banks compete for stabilized institutional "
            "product; smaller regulated buildings are financed by local banks and credit unions fluent in "
            "Santa Monica's specific rent board rules. Measure GS should be modeled into any sale-exit "
            "analysis above the $8 million threshold."
        ),
        "watch_items": [
            "Measure GS transfer tax (5.6%) applies to sales above roughly $8 million -- model it into exit math.",
            "Santa Monica's rent board rules and registration requirements are stricter than City of LA RSO.",
            "Verify soft-story and non-ductile concrete retrofit status on older beachside stock.",
        ],
    },
    {
        "name": "West Hollywood",
        "slug": "west-hollywood",
        "region": "Westside",
        "jurisdiction": "west_hollywood",
        "overview": (
            "West Hollywood is a small, dense, independently incorporated city with its own rent "
            "stabilization ordinance covering pre-1979 buildings, packed onto small lots along "
            "commercial corridors like Santa Monica Boulevard and Sunset Strip. Redevelopment and lot "
            "assemblage plays are common given the city's small footprint and high land values.\n\n"
            "The tenant base and commercial character here are distinct from the rest of the westside, "
            "and buyers range from long-hold owners of small regulated buildings to developers "
            "assembling parcels for larger mixed-use redevelopment."
        ),
        "financing_playbook": (
            "Smaller regulated assets route well to local banks and credit unions with West Hollywood "
            "experience; bridge and construction capital fund lot-assemblage and redevelopment plays "
            "where entitlement risk, not rent-roll underwriting, is the central question."
        ),
        "watch_items": [
            "Confirm the city's own July 1979 rent-ordinance cutoff, distinct from City of LA's 1978 line.",
            "Small lot sizes make assemblage economics, not per-parcel value, the key underwriting question.",
            "Verify soft-story retrofit status on older wood-frame buildings along commercial corridors.",
        ],
    },
    {
        "name": "Beverly Hills",
        "slug": "beverly-hills",
        "region": "Westside",
        "jurisdiction": "beverly_hills",
        "overview": (
            "Beverly Hills' apartment stock is smaller and more luxury-oriented than most LA "
            "submarkets, with a limited supply of regulated multifamily buildings mixed among condos "
            "and single-family product. What multifamily stock exists commands premium rents even "
            "where rent stabilization applies.\n\nThis is a lower-volume, higher-basis submarket where "
            "deals are infrequent but well-capitalized, and buyers are typically long-hold private "
            "capital or family offices rather than value-add syndicators."
        ),
        "financing_playbook": (
            "Life companies and private banks are natural fits for the high-basis, low-leverage profile "
            "typical of Beverly Hills multifamily; deal volume is low enough that most financing is "
            "relationship-driven rather than programmatic."
        ),
        "watch_items": [
            "Confirm Beverly Hills' own rent stabilization cap formula, distinct from City of LA RSO.",
            "Limited regulated multifamily supply means comps are thin; appraisal support matters more.",
            "Verify building-specific retrofit status given the age of much of the city's older stock.",
        ],
    },
    {
        "name": "Century City / West LA",
        "slug": "century-city-west-la",
        "region": "Westside",
        "jurisdiction": "la",
        "overview": (
            "Century City and the surrounding West LA corridor are dominated by newer, larger apartment "
            "towers and mid-rise buildings, most built well after the RSO cutoff and therefore exempt "
            "from local rent control entirely. This is the most institutional, market-rate-oriented "
            "apartment submarket in the City of LA.\n\nInvestors here are typically institutional funds, "
            "REITs, and life companies rather than local value-add operators, and deal underwriting "
            "looks far more like a conventional market-rate apartment analysis than the regulated-roll "
            "underwriting common elsewhere in the city."
        ),
        "financing_playbook": (
            "Life-company and agency debt dominate this submarket given the newer, larger, exempt stock; "
            "underwriting is to market rents with standard growth assumptions rather than a regulated "
            "roll. Measure ULA still applies to any City of LA sale above the transfer-tax thresholds, "
            "which shapes exit timing even for exempt, newer product."
        ),
        "watch_items": [
            "Confirm building age; even in this corridor, pockets of older RSO stock exist on side streets.",
            "Measure ULA transfer tax thresholds ($5M and $10M) apply on exit regardless of rent-control status.",
            "Larger assets may carry more complex reciprocal easement or condo-map considerations.",
        ],
    },
    {
        "name": "Culver City",
        "slug": "culver-city",
        "region": "Westside",
        "jurisdiction": "culver_city",
        "overview": (
            "Culver City is an independently incorporated city that has become a tech and media hub "
            "(Apple, Amazon Studios, HBO among the anchor tenants), with a mix of older regulated "
            "apartment buildings and new TOC-eligible construction along the Expo Line corridor. Rent "
            "growth has outpaced much of the westside as employment has grown.\n\nInvestor demand is "
            "strong for both the value-add regulated stock and ground-up TOC product, driven by the "
            "employment growth story as much as by the rent-control mechanics."
        ),
        "financing_playbook": (
            "Bank and bridge debt are both active on the regulated stock; construction lenders have "
            "grown more comfortable with the TOC pipeline as the employment thesis has proven out. "
            "Culver City's Measure RE transfer tax (tiered, up to 4% on sales of $10 million or more) "
            "should be modeled into exit underwriting."
        ),
        "watch_items": [
            "Measure RE transfer tax (up to 4% at $10M+ sales) affects exit math independent of rent control.",
            "Confirm the city's own 1995 Costa-Hawkins cutoff and CPI-tied cap band before underwriting.",
            "TOC density bonus parcels near Expo Line stations carry affordable set-aside obligations.",
        ],
    },
    # ── San Fernando Valley ──
    {
        "name": "Sherman Oaks / Valley Village",
        "slug": "sherman-oaks-valley-village",
        "region": "San Fernando Valley",
        "jurisdiction": "la",
        "overview": (
            "Sherman Oaks and Valley Village anchor the Valley's Ventura Boulevard dingbat corridor: "
            "block after block of 1960s-1970s two- and three-story RSO apartment buildings with carport "
            "parking underneath, the classic soft-story building type. It is one of the most actively "
            "traded value-add submarkets in the Valley.\n\nBuyers here range from 1031 exchange "
            "investors seeking a stable regulated income stream to family offices executing multi-"
            "building renovation programs across a portfolio of similar-vintage dingbats."
        ),
        "financing_playbook": (
            "Bridge lenders are highly active on the classic renovate-at-turnover dingbat play; agency "
            "and bank debt take the stabilized refinance. Soft-story retrofit status is the single most "
            "important diligence item in this submarket given how much of the stock is exactly the "
            "wood-frame-over-parking type the ordinance targets."
        ),
        "watch_items": [
            "Soft-story retrofit status (Ordinance 183893) is the top diligence item -- much of the stock is exactly this building type.",
            "Confirm RSO cutoff before assuming a building is regulated or exempt.",
            "Relocation cost exposure on any unit-vacate renovation plan should be budgeted conservatively.",
        ],
    },
    {
        "name": "North Hollywood / NoHo Arts District",
        "slug": "north-hollywood-noho",
        "region": "San Fernando Valley",
        "jurisdiction": "la",
        "extra_note": (
            "NoHo also has Adaptive Reuse Ordinance eligibility on some older commercial and industrial "
            "buildings, alongside its Metro Red/Orange Line TOC construction pipeline."
        ),
        "overview": (
            "North Hollywood has transformed around its Metro Red Line and Orange Line hub, combining "
            "older RSO apartment stock with a fast-growing TOC-eligible construction pipeline in the "
            "NoHo Arts District. It is one of the Valley's clearest transit-oriented growth stories, "
            "with density bonuses driving several recent ground-up projects.\n\nOlder warehouse and "
            "commercial buildings in the district are also candidates for adaptive-reuse conversion, "
            "adding a third product type alongside the regulated apartment stock and new TOC "
            "construction."
        ),
        "financing_playbook": (
            "Construction and bridge-to-perm lenders are active on the TOC and adaptive-reuse pipeline; "
            "bank and bridge debt handle the older RSO stock on a more conventional renovate-at-turnover "
            "basis. This is one of the more liquid Valley submarkets for construction financing "
            "specifically."
        ),
        "watch_items": [
            "TOC density bonus parcels near the Red/Orange Line hub carry affordable set-aside obligations.",
            "Confirm ARO eligibility before underwriting reduced parking on any conversion candidate.",
            "Soft-story retrofit status on older wood-frame RSO stock is a standard diligence item.",
        ],
    },
    {
        "name": "Van Nuys / Panorama City",
        "slug": "van-nuys-panorama-city",
        "region": "San Fernando Valley",
        "jurisdiction": "la",
        "overview": (
            "Van Nuys and Panorama City sit in the Valley's industrial-adjacent core, with an older RSO "
            "apartment stock and one of the lowest per-unit basis points in the western San Fernando "
            "Valley. Proximity to Van Nuys Airport and a deep industrial employment base support steady "
            "workforce rental demand.\n\nValue-add investors are drawn here for the basis advantage "
            "relative to Sherman Oaks or Studio City, executing similar renovate-at-turnover plans on "
            "comparable-vintage dingbat and garden-apartment stock at a meaningfully lower entry price."
        ),
        "financing_playbook": (
            "Bridge lenders active in Sherman Oaks extend into Van Nuys and Panorama City at a lower "
            "basis; community banks compete for the stabilized refinance. This is a value-oriented "
            "submarket where basis discipline matters as much as rent growth assumptions."
        ),
        "watch_items": [
            "Soft-story retrofit status is a top diligence item given the prevalence of 1960s-70s dingbat stock.",
            "Confirm RSO cutoff and relocation obligations before underwriting any unit-vacate plan.",
            "Industrial-adjacent parcels should be checked for any use or noise-overlay considerations.",
        ],
    },
    {
        "name": "Reseda / Canoga Park / West Valley",
        "slug": "reseda-canoga-park-west-valley",
        "region": "San Fernando Valley",
        "jurisdiction": "la",
        "overview": (
            "The west Valley submarket spanning Reseda, Canoga Park, Winnetka, and Woodland Hills carries "
            "the lowest apartment basis in the RSO-covered San Fernando Valley, with a large stock of "
            "1960s-70s dingbat and garden apartments similar in vintage to Sherman Oaks but priced well "
            "below it. The Warner Center Specific Plan overlays parts of the Woodland Hills end of the "
            "corridor with its own density and traffic-management rules.\n\nThis is a basis-driven "
            "value-add submarket: investors here are underwriting to the renovate-at-turnover math more "
            "than to any near-term rent-growth story."
        ),
        "financing_playbook": (
            "Bridge and community bank debt dominate; this is a value-oriented submarket where basis "
            "discipline and realistic renovation budgets matter more than aggressive rent growth "
            "assumptions. Parcels inside the Warner Center Specific Plan footprint need entitlement "
            "review specific to that plan, not just base zoning."
        ),
        "watch_items": [
            "Soft-story retrofit status is the top diligence item given the density of 1960s-70s dingbat stock.",
            "Confirm whether a parcel falls inside the Warner Center Specific Plan before assuming base zoning applies.",
            "Basis discipline matters more here than in the east Valley; underwrite renovation costs conservatively.",
        ],
    },
    {
        "name": "Studio City / Toluca Lake",
        "slug": "studio-city-toluca-lake",
        "region": "San Fernando Valley",
        "jurisdiction": "la",
        "overview": (
            "Studio City and Toluca Lake host smaller, boutique RSO apartment buildings serving an "
            "entertainment-industry tenant base close to the major studio lots. Basis runs higher than "
            "the rest of the Valley, closer to westside pricing, reflecting the location and tenant "
            "quality.\n\nInvestors here tend to hold smaller, well-maintained buildings for steady "
            "income rather than aggressive value-add repositioning, though light renovation-at-turnover "
            "programs are still common on older units."
        ),
        "financing_playbook": (
            "Local and regional banks are comfortable with the smaller, well-located regulated buildings "
            "typical here; bridge debt is available for renovation programs but sized to a more modest, "
            "boutique scale than the larger dingbat portfolios traded elsewhere in the Valley."
        ),
        "watch_items": [
            "Confirm RSO cutoff status before assuming a building is regulated or exempt.",
            "Smaller unit counts mean per-unit renovation costs matter more than portfolio-scale assumptions.",
            "Verify soft-story retrofit status on pre-1978 wood-frame buildings.",
        ],
    },
    {
        "name": "Burbank / Glendale",
        "slug": "burbank-glendale",
        "region": "San Fernando Valley",
        "jurisdiction": "none_local",
        "extra_note": (
            "Glendale adds its own right-to-lease ordinance on top of statewide AB 1482, and both cities "
            "have a media and entertainment employment base (studio lots, Disney, Nickelodeon, "
            "aerospace-adjacent Glendale employers) that supports steady rental demand."
        ),
        "overview": (
            "Burbank and Glendale are independently incorporated cities with no local rent-control "
            "ordinance of their own, making them two of the cleanest AB-1482-only apartment submarkets "
            "in the county. Both benefit from a deep media and entertainment employment base anchoring "
            "steady rental demand.\n\nWithout a local rent-stabilization overlay to underwrite around, "
            "these submarkets attract the broadest lender competition of anywhere covered in this guide, "
            "closer to a conventional market-rate apartment underwriting exercise."
        ),
        "financing_playbook": (
            "Agency, bank, and life-company debt all compete aggressively here given the market-rate, "
            "AB-1482-only regulatory profile and stable employment base. This is one of the most "
            "conventionally financeable apartment submarkets in Los Angeles County."
        ),
        "watch_items": [
            "Glendale's right-to-lease ordinance adds tenant protections beyond AB 1482 -- confirm current rules.",
            "Confirm building age against the AB 1482 15-year exemption window for newer construction.",
            "Verify soft-story retrofit status on older wood-frame buildings in both cities.",
        ],
    },
    # ── South Bay & Harbor ──
    {
        "name": "San Pedro / Harbor Area",
        "slug": "san-pedro-harbor-area",
        "region": "South Bay & Harbor",
        "jurisdiction": "la",
        "overview": (
            "San Pedro anchors the Port of LA harbor area with an older RSO apartment stock serving a "
            "longshoreman and port-industry workforce, at a basis well below the rest of the City of "
            "LA. Waterfront redevelopment around the LA Waterfront and downtown San Pedro has begun to "
            "draw fresh investor attention to a historically overlooked submarket.\n\nValue-add "
            "investors are attracted by the basis discount relative to comparable RSO stock elsewhere "
            "in the city, betting on the harbor area's ongoing revitalization to support rent growth "
            "over the hold period."
        ),
        "financing_playbook": (
            "Community banks with harbor-area relationships and bridge lenders comfortable with an "
            "emerging-submarket thesis are the most active here. Underwriting should be conservative on "
            "rent growth assumptions given the area's slower historical appreciation relative to central "
            "LA and the westside."
        ),
        "watch_items": [
            "Confirm RSO cutoff and relocation obligations before underwriting any unit-vacate plan.",
            "Port-adjacent industrial use and noise overlays should be checked for any given parcel.",
            "Soft-story retrofit status on older wood-frame stock is a standard diligence item.",
        ],
    },
    {
        "name": "Long Beach",
        "slug": "long-beach",
        "region": "South Bay & Harbor",
        "jurisdiction": "none_local",
        "extra_note": (
            "Long Beach has no blanket rent-cap ordinance but does have its own tenant-protection and "
            "relocation rules layered on top of statewide AB 1482 -- distinct from a true no-local-rules "
            "city like Torrance or El Segundo."
        ),
        "overview": (
            "Long Beach is a large, independently incorporated city with a port and aerospace economy, "
            "a more institutional apartment stock than most LA-adjacent submarkets, and its own tenant-"
            "protection and relocation ordinance layered on top of statewide AB 1482 rather than a "
            "blanket local rent cap. It functions almost as its own metro rather than an LA submarket.\n\n"
            "Institutional buyers, REITs, and regional operators are all active here, drawn by scale, "
            "port and aerospace-anchored employment, and a regulatory profile that is more "
            "conventional than the City of LA's RSO overlay."
        ),
        "financing_playbook": (
            "Agency, bank, and life-company debt all compete actively given the larger asset sizes and "
            "more conventional regulatory profile relative to City of LA RSO buildings. Long Beach's "
            "own tenant-protection ordinance should still be confirmed before underwriting any "
            "unit-turnover plan."
        ),
        "watch_items": [
            "Confirm Long Beach's own tenant-protection/relocation rules, distinct from a blanket rent cap.",
            "Verify building age against the AB 1482 15-year exemption window.",
            "Port and aerospace employment concentration should inform demand-durability assumptions.",
        ],
    },
    {
        "name": "Inglewood",
        "slug": "inglewood",
        "region": "South Bay & Harbor",
        "jurisdiction": "inglewood",
        "overview": (
            "Inglewood has been transformed by the SoFi Stadium and Intuit Dome redevelopment corridor, "
            "bringing new investor attention to a historically lower-basis apartment submarket now "
            "covered by the city's own 2019 rent control ordinance. Older regulated stock sits alongside "
            "growing interest in nearby redevelopment-adjacent parcels.\n\nThe basis discount relative to "
            "the westside, combined with the stadium-district catalyst, has made Inglewood one of the "
            "more actively watched value-add and long-term-hold submarkets in the county."
        ),
        "financing_playbook": (
            "Bridge and community bank debt fund the value-add and turnover thesis on older regulated "
            "buildings; interest from institutional and construction capital has grown alongside the "
            "stadium-district redevelopment story, though execution risk on that broader thesis should "
            "be underwritten conservatively."
        ),
        "watch_items": [
            "Confirm Inglewood's own 2019 rent control ordinance terms before underwriting a specific building.",
            "Stadium-district redevelopment momentum is a real catalyst but should not be over-assumed in rent growth.",
            "Verify soft-story retrofit status on older wood-frame stock.",
        ],
    },
    {
        "name": "Torrance / El Segundo / South Bay Beach Cities",
        "slug": "torrance-el-segundo-south-bay",
        "region": "South Bay & Harbor",
        "jurisdiction": "none_local",
        "extra_note": (
            "El Segundo and the broader South Bay aerospace corridor (SpaceX, major aerospace "
            "contractors) anchor a stable, well-paid employment base that supports the apartment stock "
            "in this submarket."
        ),
        "overview": (
            "Torrance, El Segundo, and the South Bay beach cities have no local rent-control ordinance, "
            "making this one of the cleanest AB-1482-only submarkets in the county, anchored by a stable "
            "aerospace and tech employment base. Coastal-adjacent pricing runs meaningfully higher than "
            "inland South Bay, but the regulatory profile is uniform across the corridor.\n\nInstitutional "
            "and private capital both compete here for a market-rate apartment product with steady, "
            "well-paid tenant demand and minimal regulatory overlay relative to City of LA submarkets."
        ),
        "financing_playbook": (
            "Agency, bank, and life-company debt all compete aggressively given the market-rate profile "
            "and stable aerospace/tech-anchored employment base. This is one of the most conventionally "
            "financeable, lowest-friction apartment submarkets covered in this guide."
        ),
        "watch_items": [
            "Confirm building age against the AB 1482 15-year exemption window for newer construction.",
            "Coastal-adjacent parcels closer to the beach cities may carry Coastal Zone considerations.",
            "Verify soft-story retrofit status on older wood-frame stock inland from the coast.",
        ],
    },
    # ── Pasadena & San Gabriel Valley ──
    {
        "name": "Pasadena",
        "slug": "pasadena",
        "region": "Pasadena & San Gabriel Valley",
        "jurisdiction": "pasadena",
        "overview": (
            "Pasadena is an independently incorporated city with its own Measure H rent control "
            "(adopted 2024), applied to an older apartment stock clustered around Old Town and the "
            "Playhouse District. JPL and Caltech anchor a stable, well-educated employment base that "
            "supports steady rental demand.\n\nInvestor interest spans long-hold regulated-building "
            "owners and newer buyers underwriting the impact of Measure H's 75%-of-CPI cap on future "
            "rent growth assumptions, a meaningfully tighter cap than City of LA RSO's formula."
        ),
        "financing_playbook": (
            "Local and regional banks are comfortable with Pasadena's regulated stock; the 75%-of-CPI "
            "cap under Measure H should be modeled conservatively into any rent-growth assumption, "
            "tighter than the CPI-plus formulas used in several neighboring jurisdictions."
        ),
        "watch_items": [
            "Measure H caps annual increases at 75% of CPI -- tighter than most other LA-area ordinances.",
            "Confirm the city's own rental board process, distinct from City of LA RSO administration.",
            "Verify soft-story retrofit status on older stock near Old Town and the Playhouse District.",
        ],
    },
    {
        "name": "Alhambra / San Gabriel Valley",
        "slug": "alhambra-san-gabriel-valley",
        "region": "Pasadena & San Gabriel Valley",
        "jurisdiction": "none_local",
        "extra_note": (
            "Most San Gabriel Valley cities (Alhambra, San Gabriel, Monterey Park, Rosemead, and "
            "similar) have no local rent-stabilization ordinance, so AB 1482 governs; this submarket "
            "also draws a distinct, active Chinese-American and broader Asian-American investor buyer "
            "pool relative to the rest of the county."
        ),
        "overview": (
            "The San Gabriel Valley's core cities generally have no local rent-control ordinance, so "
            "statewide AB 1482 governs a stock of smaller, often family-owned apartment buildings. The "
            "submarket draws a distinct, highly active investor pool, with strong participation from "
            "Chinese-American and broader Asian-American buyers relative to the rest of the county.\n\n"
            "Basis remains lower than the westside or central LA, and deals tend to be smaller, family-"
            "owned buildings changing hands directly between local investors rather than institutional "
            "portfolios."
        ),
        "financing_playbook": (
            "Community and regional banks with SGV relationships are the most natural lenders; DSCR and "
            "conventional bank debt both compete well given the market-rate, AB-1482-only regulatory "
            "profile and typically smaller deal sizes."
        ),
        "watch_items": [
            "Confirm no local ordinance applies in the specific city; a handful of SGV cities have considered adopting one.",
            "Verify building age against the AB 1482 15-year exemption window.",
            "Smaller, family-owned buildings may have less formal financial recordkeeping -- plan diligence accordingly.",
        ],
    },
    # ── Unincorporated LA County ──
    {
        "name": "Unincorporated LA County (Marina del Rey, Altadena, East LA)",
        "slug": "unincorporated-la-county",
        "region": "Unincorporated LA County",
        "jurisdiction": "county",
        "overview": (
            "Unincorporated Los Angeles County pockets span an unusually wide range, from high-value "
            "Marina del Rey to more modest Altadena and East LA, all sharing county (not City of LA) "
            "planning, permitting, and rent-stabilization jurisdiction. This is a genuinely mixed "
            "submarket where basis and building character depend heavily on the specific pocket.\n\n"
            "What unites these areas for financing purposes is jurisdictional: entitlements, permits, "
            "and rent-regulation questions all run through the county rather than the City of Los "
            "Angeles, which changes which offices and timelines a lender's diligence team should expect."
        ),
        "financing_playbook": (
            "Lenders active across City of LA submarkets can generally underwrite unincorporated county "
            "parcels similarly, but diligence teams need to confirm they are working with county "
            "planning and the county's rent stabilization ordinance rather than assuming City of LA "
            "processes apply."
        ),
        "watch_items": [
            "Confirm county (not City of LA) jurisdiction for planning, permitting, and rent stabilization.",
            "Basis and building character vary widely by specific unincorporated pocket -- do not generalize.",
            "Verify soft-story or other retrofit obligations, which may follow county rather than LA city code.",
        ],
    },
]


def _rent_regulation_text(raw: dict) -> str:
    text = JURISDICTIONS[raw["jurisdiction"]]["text"]
    extra = raw.get("extra_note")
    if extra:
        text = f"{text} {extra}"
    return f"{text} {DISCLAIMER}"


def _watch_items_text(raw: dict) -> str:
    return " ".join(raw["watch_items"])


def _hood_faqs(name: str, jurisdiction_label: str, financing_playbook: str) -> list:
    return [
        {
            "q": f"Is a {name} apartment building rent-controlled?",
            "a": (
                f"Most {name} apartment buildings fall under {jurisdiction_label}, though coverage "
                f"depends on the building's certificate-of-occupancy date and unit count. Use the free "
                f"LA Rent Control Checker tool for a specific building, and confirm edge cases with the "
                f"applicable rent board or counsel before underwriting."
            ),
        },
        {
            "q": f"How does rent regulation affect financing for {name} apartments?",
            "a": financing_playbook,
        },
        {
            "q": f"What loan programs work best for {name} apartment deals?",
            "a": (
                f"Commercial Lending Solutions places {name} apartment loans across agency (Fannie Mae / "
                f"Freddie Mac), bank and credit union, bridge, HUD/FHA, and construction debt, matched to "
                f"whether the building is stabilized, turning over units, or being built new. Most "
                f"borrowers see term sheets within 48-72 hours of a complete submission."
            ),
        },
    ]


def build_hoods() -> list:
    """Expand RAW_HOODS into full hood dicts matching what la_apartment_page.html
    and la_apartments_index.html expect."""
    hoods = []
    for raw in RAW_HOODS:
        name = raw["name"]
        jurisdiction_label = JURISDICTIONS[raw["jurisdiction"]]["label"]
        financing_playbook = raw["financing_playbook"]
        hood = {
            "name": name,
            "slug": raw["slug"],
            "region": raw["region"],
            "jurisdiction": jurisdiction_label,
            "rent_regulation": _rent_regulation_text(raw),
            "financing_playbook": financing_playbook,
            "watch_items": _watch_items_text(raw),
            "overview": raw["overview"],
            "faqs": _hood_faqs(name, jurisdiction_label, financing_playbook),
            "seo": {
                "h1": f"{name} Apartment Financing",
                "title": f"{name} Apartment Loans | Commercial Lending Solutions",
                "meta_description": (
                    f"Apartment loans in {name}, Los Angeles: {jurisdiction_label} rent regulation. "
                    f"Bridge, agency, bank, and construction financing from a Los Angeles-based broker. "
                    f"Free quote, response within 24 hours."
                ),
            },
        }
        hoods.append(hood)
    return hoods


def build_hood_groups(hoods: list) -> list:
    """Group hoods by region, ordered per REGION_ORDER."""
    by_region = {}
    for h in hoods:
        by_region.setdefault(h["region"], []).append(h)
    groups = []
    for region in REGION_ORDER:
        if region in by_region:
            groups.append({"region": region, "hoods": by_region[region]})
    return groups


def nearby_hoods(hoods: list, current_slug: str, current_region: str, n: int = 4) -> list:
    """Up to n other hoods in the same region, excluding current; falls back
    to the next hoods in list order if the region is small."""
    same_region = [h for h in hoods if h["region"] == current_region and h["slug"] != current_slug]
    if len(same_region) >= n:
        return same_region[:n]
    others = [h for h in hoods if h["region"] != current_region and h["slug"] != current_slug]
    return (same_region + others)[:n]


# ── Guide content (6 deep guides) ────────────────────────────────────────
# Slugs for the first 4 guides match hardcoded cross-links already baked
# into la_apartment_page.html and tool_la_rentcontrol.html -- do not rename.
RAW_GUIDES = [
    {
        "slug": "la-rent-control-apartment-financing",
        "title": "Rent-Controlled Apartment Financing in Los Angeles",
        "category": "Rent Regulation",
        "seo": {
            "h1": "Financing Rent-Controlled Apartments in Los Angeles",
            "title": "LA Rent Control & Apartment Financing Guide | Commercial Lending Solutions",
            "meta_description": (
                "How RSO, AB 1482, and LA County's patchwork of municipal rent ordinances affect "
                "apartment loan underwriting, proceeds, and lender selection. A working broker's guide."
            ),
        },
        "hero_intro": (
            "Los Angeles County is not one rent-control regime, it is at least nine: City of LA RSO, "
            "seven-plus separate municipal ordinances, unincorporated county rules, and statewide AB "
            "1482 layered on top of all of it. Getting the jurisdiction and cutoff date right changes "
            "how a lender sizes an apartment loan, sometimes by a meaningful margin. This guide covers "
            "how each regime actually works and what it means for financing."
        ),
        "key_facts": [
            {"label": "City of LA RSO cutoff", "value": "10/1/1978 certificate of occupancy"},
            {"label": "AB 1482 statewide cap", "value": "5% + CPI, 10% max"},
            {"label": "Costa-Hawkins local-control cutoff", "value": "2/1995 construction"},
            {"label": "Separate municipal ordinances", "value": "7+ cities in LA County"},
        ],
        "sections": [
            {
                "heading": "The Patchwork, in Plain English",
                "body": (
                    "Inside the City of Los Angeles, the Rent Stabilization Ordinance (RSO) covers "
                    "residential buildings with two or more units that received a certificate of "
                    "occupancy on or before October 1, 1978. RSO sets a CPI-based annual increase "
                    "formula, requires relocation assistance for certain unit removals, and layers on "
                    "SCEP seismic inspection and just-cause eviction rules.\n\n"
                    "Buildings built after that date, once they turn 15 years old, generally fall under "
                    "statewide AB 1482 instead: a simpler cap of 5% plus local CPI with a 10% absolute "
                    "ceiling, plus its own just-cause eviction requirements. New construction is exempt "
                    "from both regimes for its first 15 years.\n\n"
                    "Then there is the rest of the county. Santa Monica, West Hollywood, Beverly Hills, "
                    "Culver City, Inglewood, and Pasadena all run their own, separately administered rent "
                    "ordinances with different cutoff dates and cap formulas. Unincorporated LA County has "
                    "its own ordinance too. And a meaningful list of incorporated cities, including "
                    "Glendale, Burbank, Long Beach, Torrance, and El Segundo, have no local rent cap at "
                    "all, leaving AB 1482 as the only regulation."
                ),
            },
            {
                "heading": "Costa-Hawkins and Vacancy Decontrol",
                "body": (
                    "The one rule that runs through nearly every local ordinance in the county is "
                    "Costa-Hawkins vacancy decontrol: when a regulated unit turns over to a new tenant, "
                    "the landlord can reset the rent to market. That single mechanism is the foundation "
                    "of nearly every value-add apartment business plan in LA. A sponsor buying a "
                    "regulated building at a discount to market rents is usually betting on turning over "
                    "units over a hold period, not on rent-cap increases alone getting them to market.\n\n"
                    "Costa-Hawkins also draws the line for local rent control eligibility in several "
                    "cities: buildings built after February 1995 are generally exempt from local "
                    "ordinances statewide (though they may still fall under AB 1482 once they age past "
                    "15 years)."
                ),
            },
            {
                "heading": "How Lenders Actually Underwrite This",
                "body": (
                    "Lenders size regulated buildings to the in-place, regulated rent roll, not to a "
                    "blanket market-rent assumption. That is the single biggest difference between "
                    "underwriting a Sherman Oaks dingbat and a comparable exempt building in Century "
                    "City. A credible, unit-by-unit turnover schedule, showing which units are likely to "
                    "turn over and when, is what lets a bridge lender price in future rent growth without "
                    "overstating it.\n\n"
                    "Different lender types gravitate toward different parts of this trade. Bridge funds "
                    "underwrite the renovate-at-turnover business plan directly. Banks and credit unions "
                    "with deep local knowledge are comfortable financing stabilized regulated buildings "
                    "at conservative leverage. Agency lenders (Fannie Mae and Freddie Mac) will finance "
                    "stabilized regulated rolls too, provided the rent roll and expense history support "
                    "the debt service coverage they require.\n\n"
                    "Matching the right lender to the specific regulatory regime and business plan, "
                    "rather than treating every LA apartment building the same, is what separates full "
                    "proceeds from a retrade at the term sheet stage."
                ),
            },
        ],
        "faqs": [
            {
                "q": "How many different rent control ordinances exist in LA County?",
                "a": (
                    "At least nine distinct regimes affect LA County apartment buildings: City of LA "
                    "RSO, separate municipal ordinances in Santa Monica, West Hollywood, Beverly Hills, "
                    "Culver City, Inglewood, and Pasadena, an unincorporated LA County ordinance, and "
                    "statewide AB 1482 as the backstop everywhere else. Each has its own cutoff date and "
                    "cap formula."
                ),
            },
            {
                "q": "Does rent control reduce how much I can borrow?",
                "a": (
                    "It changes the basis for underwriting, not necessarily the leverage available. "
                    "Lenders size proceeds to actual in-place rents (regulated) rather than pro forma "
                    "market rents, so a building with significant upside from vacancy decontrol may "
                    "still support strong leverage once the turnover plan is credible and documented."
                ),
            },
            {
                "q": "Is new construction ever subject to rent control in LA?",
                "a": (
                    "No, new construction is exempt from both local rent control ordinances and "
                    "statewide AB 1482 for its first 15 years under state law. After 15 years, it "
                    "generally falls under AB 1482 unless a specific local ordinance applies differently."
                ),
            },
        ],
    },
    {
        "slug": "measure-ula-commercial-real-estate",
        "title": "Measure ULA and Your LA Exit Strategy",
        "category": "Tax & Exit Planning",
        "seo": {
            "h1": "Measure ULA: What LA's Transfer Tax Means for Your Exit",
            "title": "Measure ULA Commercial Real Estate Guide | Commercial Lending Solutions",
            "meta_description": (
                "Measure ULA's transfer tax tiers, what they cost on a sale, and financing strategies "
                "(refinance, hold, structure) that change the exit math for LA apartment owners."
            ),
        },
        "hero_intro": (
            "Measure ULA, the City of Los Angeles's 'mansion tax' on high-value property transfers, "
            "took effect April 1, 2023 and has reshaped exit planning for anyone who owns commercial "
            "or multifamily real estate inside city limits. It does not touch financing directly, but "
            "it changes which financing strategy makes sense: sell, refinance, or hold."
        ),
        "key_facts": [
            {"label": "Effective date", "value": "April 1, 2023"},
            {"label": "Tier 1 (up to ~$5M)", "value": "0.56% standard city + county transfer tax"},
            {"label": "Tier 2 (~$5M-$10M)", "value": "roughly 4.56% combined rate"},
            {"label": "Tier 3 (over ~$10M)", "value": "roughly 6.06% combined rate"},
        ],
        "sections": [
            {
                "heading": "The Tax Tiers",
                "body": (
                    "Measure ULA applies only to property sales within the City of Los Angeles, not "
                    "countywide. Every sale already pays the standard combined city and county "
                    "documentary transfer tax of roughly 0.56% (0.45% city plus 0.11% county). On top of "
                    "that base tax, Measure ULA adds 4% for the portion of a sale in its middle tier and "
                    "5.5% for its top tier, for an all-in combined rate of roughly 4.56% and 6.06% "
                    "respectively.\n\n"
                    "The original 2023 tier breakpoints were $5,000,000 and $10,000,000, and the ordinance "
                    "indexes those thresholds for inflation each year, so the current breakpoints run "
                    "somewhat higher than the original figures. Sellers should confirm the exact "
                    "current-year thresholds and combined rate with escrow or counsel before relying on a "
                    "specific number.\n\n"
                    "On a $30 million sale at the roughly 6.06% top-tier combined rate, transfer tax runs "
                    "in the neighborhood of $1,800,000, due at closing regardless of the seller's basis or "
                    "gain. For a leveraged apartment building, that is real money coming off the top of "
                    "proceeds before the loan is paid off and equity is returned.\n\n"
                    "The tax has been challenged in court multiple times since it passed. It remains in "
                    "effect as of this writing, but sellers should confirm current status and exact "
                    "thresholds with escrow or counsel before finalizing a sale, since litigation and "
                    "any future amendments could change the mechanics."
                ),
            },
            {
                "heading": "Strategies That Change the Financing Conversation",
                "body": (
                    "Several strategies have emerged in response to ULA, and each has a different "
                    "financing implication. Hold-for-income rather than sell avoids the tax entirely, "
                    "which is why owners of stabilized City of LA apartment buildings are increasingly "
                    "asking about long-term fixed-rate agency or life-company debt rather than planning "
                    "an exit.\n\n"
                    "Refinance-and-return-equity is the other common play: a cash-out refinance lets an "
                    "owner extract a meaningful share of appreciated value without triggering a sale (and "
                    "therefore without triggering ULA), while retaining the asset and its financing in "
                    "place. This has increased demand for bridge and bank cash-out refinance products on "
                    "stabilized City of LA multifamily specifically.\n\n"
                    "Some owners and advisors have explored selling entity interests (an LLC that owns "
                    "the property) rather than the property itself, on the theory that ULA taxes real "
                    "property transfers rather than entity transfers. The legal status of that approach "
                    "is genuinely uncertain and being tested; anyone considering it needs dedicated tax "
                    "and real estate counsel, not general guidance."
                ),
            },
            {
                "heading": "What This Means for Buyers, Not Just Sellers",
                "body": (
                    "Buyers underwriting a City of LA acquisition above the $5 million threshold should "
                    "model ULA into their own eventual exit, not just focus on the immediate purchase. A "
                    "deal that pencils on a 5-year hold with a sale exit needs to account for the tax tier "
                    "the sale price will land in; a deal underwritten with a refinance-and-hold exit "
                    "strategy from day one avoids that math entirely.\n\n"
                    "This is one of the clearest examples of a purely local regulation changing capital "
                    "markets behavior: financing structures that avoid a taxable sale event have become "
                    "measurably more attractive for City of LA assets above the ULA thresholds since 2023."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Does Measure ULA apply outside the City of Los Angeles?",
                "a": (
                    "No. Measure ULA is a City of Los Angeles ordinance and applies only to transfers of "
                    "real property located within city limits. Santa Monica and Culver City have their "
                    "own separate transfer taxes (Measure GS and Measure RE respectively) with different "
                    "thresholds and rates; unincorporated county and other incorporated cities are not "
                    "subject to ULA at all."
                ),
            },
            {
                "q": "Can refinancing help avoid Measure ULA?",
                "a": (
                    "Yes, in the sense that a refinance is not a sale and does not trigger the transfer "
                    "tax. A cash-out refinance lets an owner access built-up equity while retaining "
                    "ownership, which is why refinance-and-hold has become a more common strategy for "
                    "City of LA properties above the ULA thresholds since 2023."
                ),
            },
            {
                "q": "Is Measure ULA still in effect?",
                "a": (
                    "As of this writing, yes, though it has faced multiple legal challenges since "
                    "passage. Given ongoing litigation, sellers and buyers should confirm the current "
                    "status and exact rate tiers with escrow or counsel before relying on any specific "
                    "number in a closing analysis."
                ),
            },
        ],
    },
    {
        "slug": "soft-story-retrofit-financing-la",
        "title": "Soft-Story Retrofit Financing in Los Angeles",
        "category": "Seismic & Capex",
        "seo": {
            "h1": "Financing Soft-Story Retrofits on LA Apartment Buildings",
            "title": "Soft-Story Retrofit Financing Guide | Commercial Lending Solutions",
            "meta_description": (
                "How LA's soft-story and non-ductile concrete (Ordinance 183893) "
                "seismic retrofit rules affect apartment underwriting, and how to finance the work."
            ),
        },
        "hero_intro": (
            "A large share of Los Angeles's older wood-frame apartment stock, the classic 1960s-70s "
            "dingbat with parking underneath, is exactly the building type LA's soft-story retrofit "
            "ordinance targets. Retrofit status is one of the first questions a lender asks about an "
            "older building, and financing the work itself is its own conversation."
        ),
        "key_facts": [
            {"label": "Soft-story ordinance", "value": "183893, pre-1978 wood-frame"},
            {"label": "Typical soft-story retrofit cost", "value": "$60,000-$130,000+ per building"},
            {"label": "Non-ductile concrete ordinance", "value": "183893 (separate division), pre-1977 concrete"},
            {"label": "Non-ductile retrofit cost", "value": "$80-$120 per square foot"},
        ],
        "sections": [
            {
                "heading": "What the Ordinances Actually Require",
                "body": (
                    "Ordinance 183893 targets wood-frame buildings with a 'soft' ground floor, typically "
                    "tuck-under parking or ground-floor commercial space, built before January 1, 1978. "
                    "The city set retrofit deadlines that have mostly passed at this point, meaning any "
                    "building still non-compliant is a real, present diligence flag rather than a future "
                    "deadline to plan around. Typical retrofit cost runs $60,000 to $130,000 or more "
                    "depending on building size and configuration.\n\n"
                    "A separate division of the same ordinance targets non-ductile concrete buildings "
                    "built before 1977, which are structurally distinct from wood-frame soft-story buildings and "
                    "generally far more expensive to fix: retrofit costs can run $80 to $120 per square "
                    "foot, and on some buildings that number can exceed the value of the building itself.\n\n"
                    "A third category, unreinforced masonry (URM) buildings under the city's Division 88 "
                    "program, has mostly already been retrofitted or demolished, but any surviving "
                    "example should be checked against LADBS compliance records before acquisition."
                ),
            },
            {
                "heading": "Financing the Retrofit Itself",
                "body": (
                    "Retrofit costs are commonly financed three ways: as part of an acquisition loan (the "
                    "lender underwrites the retrofit as a required capital item and may hold back "
                    "proceeds until it is complete), as a standalone renovation or PACE-style loan against "
                    "an already-owned building, or as a negotiated price reduction where the seller "
                    "effectively finances it through a lower purchase price.\n\n"
                    "Bridge lenders are generally the most comfortable underwriting a building with "
                    "pending soft-story work, provided the scope and cost estimate come from a licensed "
                    "structural engineer and are reasonable relative to the building's value. Banks and "
                    "agency lenders typically want the retrofit substantially complete, or at minimum "
                    "well underway with a hard completion date, before committing to permanent financing."
                ),
            },
            {
                "heading": "Non-Ductile Concrete: A Different Conversation",
                "body": (
                    "Because non-ductile concrete retrofit costs can rival or exceed a building's value, "
                    "these properties are sometimes better underwritten as land or redevelopment plays "
                    "rather than renovation candidates. A lender evaluating a non-ductile concrete "
                    "acquisition should model both the retrofit cost and a demolition-and-rebuild "
                    "alternative side by side before assuming renovation is the right business plan.\n\n"
                    "This distinction, soft-story wood-frame versus non-ductile concrete, is one of the "
                    "most consequential underwriting questions on any pre-1978 LA apartment building, and "
                    "it should be confirmed with a structural engineer's report, not assumed from "
                    "building age alone."
                ),
            },
        ],
        "faqs": [
            {
                "q": "How do I know if a building needs a soft-story retrofit?",
                "a": (
                    "Check the building's LADBS compliance record for its soft-story or non-ductile "
                    "concrete program status; most buildings subject to the ordinances have already been "
                    "screened and assigned a compliance status. A structural engineer can confirm current "
                    "status and scope of any remaining work before you close on a building."
                ),
            },
            {
                "q": "Can I get a loan on a building that still needs a soft-story retrofit?",
                "a": (
                    "Yes, bridge lenders regularly finance buildings with pending soft-story work, "
                    "typically underwriting the retrofit cost as a required capital item with a holdback "
                    "or completion timeline. Banks and agency lenders generally prefer the work "
                    "substantially complete before committing to permanent financing."
                ),
            },
            {
                "q": "Is a non-ductile concrete retrofit always worth doing?",
                "a": (
                    "Not always. Retrofit costs on non-ductile concrete buildings can run $80 to $120 "
                    "per square foot and sometimes exceed the building's value, which is why some of "
                    "these properties are better underwritten as demolition and rebuild candidates. Model "
                    "both paths before committing to a renovation plan."
                ),
            },
        ],
    },
    {
        "slug": "adu-portfolio-financing-la",
        "title": "ADU and SB 9 Financing for LA Apartment Owners",
        "category": "Development & ADU",
        "seo": {
            "h1": "ADU and SB 9 Financing for Los Angeles Apartment Owners",
            "title": "ADU Portfolio Financing Guide | Commercial Lending Solutions",
            "meta_description": (
                "How LA apartment owners finance ADU additions and SB 9 lot splits to grow NOI, "
                "and what BMO and hillside rules mean for scope on existing multifamily parcels."
            ),
        },
        "hero_intro": (
            "Adding units to an existing apartment parcel, through an accessory dwelling unit (ADU) or "
            "an SB 9 lot split and duplex, has become one of the more accessible ways to grow NOI on "
            "already-owned LA real estate without a ground-up development project. Financing it "
            "correctly means understanding both the opportunity and its real constraints."
        ),
        "key_facts": [
            {"label": "ADU parking requirement", "value": "Often waived near transit"},
            {"label": "SB 9 applicability", "value": "Most single-family (R1) zoned lots"},
            {"label": "Baseline Mansionization Ordinance", "value": "Limits size in R1 zones"},
            {"label": "Hillside Ordinance overlay", "value": "Restricts grading, FAR, access"},
        ],
        "sections": [
            {
                "heading": "Where ADUs Fit on an Apartment Parcel",
                "body": (
                    "State ADU law has made it dramatically easier to add one or more accessory units to "
                    "an existing residential parcel, including many multifamily lots, often with reduced "
                    "parking requirements and a streamlined, largely ministerial approval process. For an "
                    "owner of a smaller existing apartment building with unused yard or parking area, an "
                    "ADU addition can add rentable NOI without the cost and risk of a full ground-up "
                    "project.\n\n"
                    "SB 9 operates differently: it primarily applies to single-family (R1) zoned lots, "
                    "allowing a qualifying lot to be split and up to two units built on each resulting "
                    "parcel. It is more relevant to a value-add investor assembling or repositioning R1 "
                    "lots adjacent to an existing multifamily holding than to an owner of an already-"
                    "built apartment building."
                ),
            },
            {
                "heading": "The Constraints That Actually Bind",
                "body": (
                    "The Baseline Mansionization Ordinance (BMO) limits total floor area, height, and "
                    "grading on R1-zoned lots, and SB 9 projects on those lots generally must still comply "
                    "with BMO unless a specific exemption applies. This caps how much square footage an "
                    "SB 9 lot split can realistically add, and should be modeled conservatively rather than "
                    "assuming maximum theoretical density.\n\n"
                    "Parcels in a mapped Hillside Area face a separate, more restrictive set of rules: "
                    "reduced floor-area ratio, grading limits, retaining wall height caps, and fire-access "
                    "requirements (a 26-foot road width standard) that can make ADU or SB 9 additions "
                    "impossible on some hillside lots regardless of zoning. Silver Lake, Echo Park, Mount "
                    "Washington, and other hillside-adjacent LA submarkets should always be checked against "
                    "the Hillside Ordinance map before assuming additional-unit potential."
                ),
            },
            {
                "heading": "Financing the Addition",
                "body": (
                    "ADU construction on an existing apartment parcel is commonly financed through a "
                    "renovation or construction-style loan sized to the incremental NOI the new unit will "
                    "generate, sometimes paired with a refinance of the underlying property once the ADU "
                    "is complete and leased. Bridge and bank lenders active in a given submarket are "
                    "usually the first call, since they already understand the base property's rent roll "
                    "and can evaluate the ADU as an addition to it.\n\n"
                    "SB 9 lot-split projects look more like small-scale ground-up development and are "
                    "typically financed with construction debt sized to the entitled unit count, followed "
                    "by a takeout loan (agency, bank, or DSCR) once the new units are built and leased. "
                    "Either way, a realistic, permit-confirmed scope, not a theoretical maximum, is what a "
                    "lender will underwrite to."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Can I add an ADU to an existing apartment building's parcel?",
                "a": (
                    "Often yes, subject to the specific lot's zoning, existing unit count, and available "
                    "yard or parking area. State ADU law has made approval more predictable, but hillside "
                    "topography, historic overlays, or an already-maxed-out lot can still constrain or "
                    "block an addition. Confirm feasibility with a local architect or zoning consultant "
                    "before underwriting the NOI upside."
                ),
            },
            {
                "q": "Does SB 9 apply to my existing multifamily property?",
                "a": (
                    "SB 9 primarily applies to single-family (R1) zoned lots, not existing multifamily "
                    "parcels. It is more relevant if you are assembling or considering adjacent R1 lots "
                    "near a multifamily holding than for adding units directly to an already-built "
                    "apartment building."
                ),
            },
            {
                "q": "What financing works for an ADU addition on an income property?",
                "a": (
                    "Renovation or construction-style loans sized to the incremental NOI the ADU will "
                    "generate are the most common approach, often through the same bank or bridge lender "
                    "already familiar with the base property. Some owners pair this with a refinance once "
                    "the ADU is complete and leased to roll the cost into permanent financing."
                ),
            },
        ],
    },
    {
        "slug": "costa-hawkins-vacancy-decontrol-financing",
        "title": "Costa-Hawkins, Vacancy Decontrol, and Underwriting Turnover",
        "category": "Underwriting",
        "seo": {
            "h1": "Costa-Hawkins and Vacancy Decontrol Underwriting in LA",
            "title": "Costa-Hawkins Vacancy Decontrol Financing Guide | Commercial Lending Solutions",
            "meta_description": (
                "How Costa-Hawkins vacancy decontrol drives value-add apartment underwriting in LA, "
                "and how lenders size proceeds against a realistic unit-turnover schedule."
            ),
        },
        "hero_intro": (
            "Costa-Hawkins is the single state law that makes value-add apartment investing possible in "
            "regulated Los Angeles submarkets. Understanding exactly what it does, and does not, allow "
            "is the difference between a turnover plan a lender will finance and one that gets retraded "
            "at term sheet."
        ),
        "key_facts": [
            {"label": "State law", "value": "Costa-Hawkins Rental Housing Act (1995)"},
            {"label": "Core mechanism", "value": "Vacancy decontrol at unit turnover"},
            {"label": "Local-control exemption", "value": "Buildings built after Feb 1995"},
            {"label": "Ellis Act interaction", "value": "Separate law, different mechanism"},
        ],
        "sections": [
            {
                "heading": "What Costa-Hawkins Actually Does",
                "body": (
                    "Costa-Hawkins is a 1995 California state law with two distinct effects that matter "
                    "for LA apartment financing. First, it exempts single-family homes and condos, and "
                    "buildings built after February 1995, from local rent control ordinances statewide "
                    "(though newer buildings may still fall under AB 1482 once they age past 15 years). "
                    "Second, and more consequentially for value-add investing, it establishes vacancy "
                    "decontrol: when a tenant in a rent-controlled unit voluntarily vacates, the landlord "
                    "can reset that unit's rent to market for the next tenant.\n\n"
                    "That second provision is the entire foundation of the classic LA value-add apartment "
                    "trade: buy a regulated building with below-market in-place rents, and as units turn "
                    "over naturally (or through a legally executed renovation and re-lease program), reset "
                    "each one to market. The rent-cap formula that governs a stabilized, non-turning unit "
                    "barely matters to this thesis; the turnover rate does."
                ),
            },
            {
                "heading": "Underwriting the Turnover Schedule",
                "body": (
                    "A credible turnover schedule starts with the actual rent roll: how far below market "
                    "is each unit, how long has the current tenant been in place, and what is a realistic, "
                    "conservative estimate of annual turnover for this specific building and submarket. "
                    "Lenders are skeptical of turnover assumptions that look more like a business plan "
                    "than a data-driven forecast.\n\n"
                    "Sponsors who overstate turnover speed to inflate projected proceeds are the most "
                    "common reason a bridge loan gets re-traded mid-process. The stronger approach "
                    "documents historical turnover at the specific property (or comparable buildings under "
                    "the same sponsor's management) and builds a phased projection from that baseline "
                    "rather than an aspirational one.\n\n"
                    "Ellis Act withdrawals are a separate, distinct mechanism, not a form of vacancy "
                    "decontrol: an owner can remove an entire building from the rental market with proper "
                    "notice and relocation payments, but that is a withdrawal-and-often-redevelop strategy, "
                    "not a unit-by-unit turnover plan, and it carries its own deed-restriction consequences "
                    "if the site is later redeveloped."
                ),
            },
            {
                "heading": "Matching the Lender to the Plan",
                "body": (
                    "Bridge lenders are built for exactly this kind of business plan: a value-add "
                    "acquisition with a defined capital improvement and turnover program, underwritten to "
                    "a projected stabilized rent roll at takeout. The best-fit bridge lenders for this "
                    "trade want to see a realistic timeline (often 24-36 months), a specific renovation "
                    "budget per unit, and evidence the sponsor has executed a similar plan before.\n\n"
                    "Once turnover and renovation are substantially complete, the takeout is typically "
                    "agency or bank debt sized to the new, largely market-rate rent roll. Structuring the "
                    "acquisition loan with the eventual takeout already in mind, rather than treating "
                    "bridge and permanent financing as two unrelated transactions, produces the smoothest "
                    "execution and the best combined proceeds."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Does Costa-Hawkins eliminate rent control in LA?",
                "a": (
                    "No. It exempts certain buildings (post-February-1995 construction, single-family "
                    "homes, condos) from local rent control ordinances, and it allows rents on remaining "
                    "regulated units to reset to market when a unit turns over. Buildings still covered "
                    "by local ordinances or AB 1482 remain subject to those caps between turnovers."
                ),
            },
            {
                "q": "How do lenders verify a turnover-based business plan?",
                "a": (
                    "By reviewing the actual rent roll against market comps to quantify the gap, checking "
                    "tenant tenure and historical turnover at the property, and evaluating the sponsor's "
                    "track record executing similar renovate-and-turn programs elsewhere. A realistic, "
                    "documented projection gets financed; an aspirational one gets retraded."
                ),
            },
            {
                "q": "Is the Ellis Act the same thing as vacancy decontrol?",
                "a": (
                    "No, they are different mechanisms. Vacancy decontrol under Costa-Hawkins resets an "
                    "individual unit's rent to market when that tenant leaves voluntarily. The Ellis Act "
                    "lets an owner withdraw an entire building from the rental market with proper notice "
                    "and relocation payments, a fundamentally different, whole-building strategy with its "
                    "own deed-restriction consequences on redevelopment."
                ),
            },
        ],
    },
    {
        "slug": "toc-density-bonus-construction-financing",
        "title": "TOC Density Bonus Construction Financing in LA",
        "category": "Development & Density",
        "seo": {
            "h1": "Financing TOC Density Bonus Construction in Los Angeles",
            "title": "TOC Density Bonus Construction Financing | Commercial Lending Solutions",
            "meta_description": (
                "How LA's Transit Oriented Communities (TOC) density bonus program affects ground-up "
                "apartment construction financing, affordable set-asides, and lender selection."
            ),
        },
        "hero_intro": (
            "The Transit Oriented Communities (TOC) program has become the default density bonus tool "
            "for ground-up apartment construction near LA's Metro Rail stations, trading affordable "
            "units for meaningfully more density, height, and parking relief. It has also become one of "
            "the more financeable construction products in the city, provided the affordable set-aside "
            "is underwritten correctly from day one."
            ),
        "key_facts": [
            {"label": "Density increase", "value": "Up to 80% near transit"},
            {"label": "Height bonus", "value": "+11 to +33 feet"},
            {"label": "Affordable set-aside", "value": "8-25% depending on tier"},
            {"label": "Parking relief", "value": "Reductions, sometimes to zero"},
        ],
        "sections": [
            {
                "heading": "What TOC Actually Grants",
                "body": (
                    "TOC (LAMC 12.22.A.31) grants density increases of up to 80% above base zoning, "
                    "height bonuses ranging from an additional 11 to 33 feet, parking reductions "
                    "(sometimes to zero in the highest tiers), and FAR increases, in exchange for setting "
                    "aside a percentage of units as affordable housing, typically ranging from 8% to 25% "
                    "depending on the tier and the income level served.\n\n"
                    "The program is calibrated by proximity to Metro Rail stations and major bus "
                    "corridors, meaning the exact tier, and therefore the exact density bonus and "
                    "affordable requirement, depends on a specific parcel's transit proximity rather than "
                    "a citywide flat rule. Confirming a parcel's TOC tier through the city's zoning "
                    "information system, not assuming it from a nearby example, is a required first step "
                    "on any TOC construction pro forma."
                ),
            },
            {
                "heading": "Where TOC Construction Is Most Active in LA",
                "body": (
                    "TOC construction has clustered most heavily around the Wilshire/Vermont and Purple "
                    "Line extension corridor in Koreatown, the Expo Line stations serving Culver City and "
                    "Mar Vista/Palms, and the Metro Red/Orange Line hub in North Hollywood, all covered "
                    "elsewhere in this guide's neighborhood pages. Each of these corridors combines strong "
                    "rental demand with genuine density upside, which is why construction lenders have "
                    "grown comfortable financing TOC projects there specifically.\n\n"
                    "Less-established corridors carry more lease-up risk even with the same TOC density "
                    "bonus available, and lenders will underwrite accordingly, often requiring a more "
                    "conservative stabilized rent assumption until a corridor has a track record of "
                    "successful comparable projects."
                ),
            },
            {
                "heading": "Financing the Construction and the Takeout",
                "body": (
                    "TOC construction is financed like any ground-up multifamily project, but with the "
                    "affordable set-aside built into the pro forma from the start: those units typically "
                    "rent well below market, and a construction lender will want to see the blended NOI "
                    "impact modeled explicitly rather than glossed over. Construction lenders comfortable "
                    "with LA's specific affordable-compliance and monitoring requirements (income "
                    "certification, ongoing reporting) are the right fit, not a generalist construction "
                    "shop unfamiliar with the program.\n\n"
                    "Takeout financing once the project is built and leased typically comes from agency "
                    "debt (Fannie Mae and Freddie Mac both have specific affordable and mixed-income "
                    "execution paths that work well with a TOC unit mix) or HUD/FHA for the highest-"
                    "leverage, longest-term outcome. Structuring the construction loan with a clear line "
                    "of sight to one of these takeout paths, rather than assuming a generic refinance will "
                    "materialize, is the key to a smooth transition out of construction debt."
                ),
            },
        ],
        "faqs": [
            {
                "q": "How much density can TOC actually add to a project?",
                "a": (
                    "Up to 80% above the base zoning density, plus a height bonus of 11 to 33 additional "
                    "feet and parking reductions that can reach zero in the highest tiers, depending on "
                    "the parcel's specific proximity to Metro Rail or qualifying bus corridors."
                ),
            },
            {
                "q": "What percentage of units have to be affordable under TOC?",
                "a": (
                    "Typically 8% to 25% of units, depending on the TOC tier and the income level served. "
                    "The exact requirement should be confirmed for the specific parcel and tier before "
                    "finalizing a pro forma, since it directly drives the project's blended NOI."
                ),
            },
            {
                "q": "What financing is available for TOC construction projects?",
                "a": (
                    "Construction and bridge-to-perm lenders familiar with LA's affordable-compliance "
                    "requirements finance the build; takeout typically comes from agency debt (Fannie Mae "
                    "or Freddie Mac programs suited to mixed-income properties) or HUD/FHA once the "
                    "project is stabilized and leased."
                ),
            },
        ],
    },
]


def build_guides() -> list:
    """Return guide dicts as-is (already fully shaped); attach related_guides
    map separately via related_guides_for()."""
    return RAW_GUIDES


def related_guides_for(guides: list, current_slug: str, n: int = 3) -> list:
    others = [g for g in guides if g["slug"] != current_slug]
    return others[:n]
