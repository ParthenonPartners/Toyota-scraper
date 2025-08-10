# Toyota Scraper (Python + Playwright)

## Setup (local/server)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

## Run
python scrape.py

## Test selectors (offline)
# Upload two files into tests/fixtures:
#  - SAMPLE_LISTING_PAGE.html
#  - SAMPLE_DETAIL_PAGE.html
python tests/test_parse_saved_html.py