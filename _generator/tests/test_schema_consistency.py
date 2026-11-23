import json
import re
import sys
from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GENERATOR_DIR))

import schema_consistency as sc  # noqa: E402

LD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)

PAGE = """<!doctype html><html><head><title>t</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Commercial Lending Solutions","url":"https://clscre.com","telephone":"+13107080690","address":{"@type":"PostalAddress","streetAddress":"7951 Blackburn Ave"},"sameAs":["https://www.facebook.com/mycommercialloanbroker/"]}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"h","author":{"@type":"Person","name":"Trevor Damyan","jobTitle":"President"},"publisher":{"@type":"Organization","name":"Commercial Lending Solutions","url":"https://clscre.com"}}</script>
</head><body><h1>Title</h1><p>Visit 7951 Blackburn Ave, Los Angeles.</p>
<div class="faq-list">
<div class="faq-item"><button class="faq-question">What is it?<span class="faq-icon">+</span></button><div class="faq-answer"><div class="faq-answer-inner"><p>A loan.</p></div></div></div>
<div class="faq-item"><h3>Why use us?</h3><p>We know lenders.</p></div>
</div><h1>Second</h1></body></html>"""


def blocks(text):
    return [json.loads(b) for b in LD.findall(text)]


def test_entity_nodes_share_ids_address_same_as_and_title():
    out = sc.process(PAGE, "x.html")
    org, art, *_ = blocks(out)
    assert org["@id"] == sc.ORG_ID
    assert org["address"] == sc.ADDRESS
    assert org["sameAs"] == sc.SAME_AS
    assert art["publisher"]["@id"] == sc.ORG_ID
    assert art["author"]["@id"] == sc.PERSON_ID
    assert art["author"]["jobTitle"] == sc.FOUNDER_TITLE


def test_visible_address_and_second_h1_are_fixed():
    out = sc.process(PAGE, "x.html")
    assert "7951 Blackburn Avenue, Los Angeles." in out
    assert "Blackburn Ave," not in out
    assert out.lower().count("<h1") == 1


def test_faq_markup_is_built_from_the_visible_block():
    out = sc.process(PAGE, "x.html")
    faq = [b for b in blocks(out) if b.get("@type") == "FAQPage"][0]
    got = [(q["name"], q["acceptedAnswer"]["text"]) for q in faq["mainEntity"]]
    assert got == [("What is it?", "A loan."), ("Why use us?", "We know lenders.")]


def test_pass_is_idempotent_and_never_duplicates_faq():
    once = sc.process(PAGE, "x.html")
    assert sc.process(once, "x.html") == once
    assert once.count('"FAQPage"') == 1
