# Minimal offline selector test:
# Place two files in tests/fixtures/:
#  - SAMPLE_LISTING_PAGE.html
#  - SAMPLE_DETAIL_PAGE.html
from bs4 import BeautifulSoup
import re, json, pathlib

FIX = pathlib.Path(__file__).parent / "fixtures"

def test_listing_links():
    html = (FIX / "SAMPLE_LISTING_PAGE.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href","")
        if re.search(r"/viewdetails/(new|used)/", href, re.I):
            links.append(href.split("?")[0])
    assert len(links) > 0

def test_detail_jsonld():
    html = (FIX / "SAMPLE_DETAIL_PAGE.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    blocks = [json.loads(s.text) for s in soup.select('script[type="application/ld+json"]')]
    assert any("Product" in json.dumps(b) or "Vehicle" in json.dumps(b) for b in blocks)