import asyncio, csv, json, re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

BASE = "https://www.toyotagallatin.com"
LIST_START_URLS = [
    f"{BASE}/inventory/new",
    f"{BASE}/inventory/used",
]

DETAIL_HREF = re.compile(r"/viewdetails/(new|used)/", re.I)

def parse_jsonld(txt):
    try:
        data = json.loads(txt)
        return data if isinstance(data, list) else [data]
    except:
        return []

async def gather_detail_links(page, list_url):
    links = set()
    async def collect():
        for a in await page.query_selector_all("a[href]"):
            href = await a.get_attribute("href")
            if href and DETAIL_HREF.search(href):
                links.add(urljoin(BASE, href.split("?")[0]))

    await page.goto(list_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(800)
    await collect()

    # UI-driven pagination (Load/Show more, Next)
    while True:
        btn = await page.query_selector("button:has-text('Load More'), button:has-text('Show More'), .pagination a[rel='next'], a[aria-label='Next']")
        if not btn:
            break
        try:
            await btn.click()
            await page.wait_for_timeout(1200)
            await collect()
        except:
            break

    # Numeric ?page=2,3,... fallback
    if "/inventory/" in list_url:
        page_num = 2
        while True:
            sep = "&" if "?" in list_url else "?"
            paged = f"{list_url}{sep}page={page_num}"
            try:
                prev = len(links)
                await page.goto(paged, wait_until="domcontentloaded")
                await page.wait_for_timeout(800)
                await collect()
                if len(links) == prev:
                    break
                page_num += 1
                await page.wait_for_timeout(400)
            except:
                break
    return sorted(links)

async def parse_vehicle_detail(page, url):
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(600)

    out = {"url": url, "vin": None, "year": None, "make": None, "model": None, "trim": None,
           "price": None, "mileage": None, "stock_number": None, "exterior_color": None,
           "interior_color": None, "drivetrain": None, "transmission": None, "engine": None,
           "images": None, "condition": "new" if "/viewdetails/new/" in url else "used"}

    # JSON-LD first
    for node in await page.query_selector_all('script[type="application/ld+json"]'):
        txt = (await node.text_content()) or ""
        for blob in parse_jsonld(txt):
            t = (blob.get("@type") or "").lower()
            if "product" in t or "vehicle" in t:
                veh = blob.get("vehicle", blob)
                out["vin"] = out["vin"] or veh.get("vehicleIdentificationNumber") or veh.get("vin")
                out["year"] = out["year"] or veh.get("modelDate") or veh.get("productionDate")
                brand = veh.get("brand")
                out["make"] = out["make"] or (brand.get("name") if isinstance(brand, dict) else brand)
                out["model"] = out["model"] or veh.get("model")
                out["trim"] = out["trim"] or veh.get("trim")
                m = veh.get("mileage")
                out["mileage"] = out["mileage"] or (m.get("value") if isinstance(m, dict) else m)
                offers = blob.get("offers") or {}
                if isinstance(offers, dict):
                    out["price"] = out["price"] or offers.get("price") or (offers.get("priceSpecification") or {}).get("price")
                imgs = blob.get("image")
                if isinstance(imgs, list):
                    out["images"] = "|".join(imgs)
                elif isinstance(imgs, str):
                    out["images"] = imgs

    # DOM fallbacks (label scan)
    details = {}
    for el in await page.query_selector_all("li, .spec-item, .vehicle-detail, .vdp-specs *"):
        t = (await el.text_content()) or ""
        t = re.sub(r"\s+", " ", t).strip()
        if ":" in t and len(t) < 120:
            k, v = [s.strip() for s in t.split(":", 1)]
            details[k.lower()] = v

    def take(*keys):
        for k in keys:
            v = details.get(k.lower())
            if v: return v

    out["stock_number"]   = out["stock_number"]   or take("stock", "stock #", "stock number")
    out["exterior_color"] = out["exterior_color"] or take("exterior", "exterior color", "ext. color")
    out["interior_color"] = out["interior_color"] or take("interior", "interior color", "int. color")
    out["engine"]         = out["engine"]         or take("engine")
    out["transmission"]   = out["transmission"]   or take("transmission")
    out["drivetrain"]     = out["drivetrain"]     or take("drivetrain", "drive type", "driveline")

    # Normalize numerics
    if isinstance(out["price"], str):
        m = re.search(r"[\d,]+(\.\d{2})?", out["price"]); out["price"] = float(m.group(0).replace(",", "")) if m else out["price"]
    if isinstance(out["mileage"], str):
        m = re.search(r"[\d,]+", out["mileage"]); out["mileage"] = int(m.group(0).replace(",", "")) if m else out["mileage"]

    return out

async def main():
    out_csv = Path("toyota_gallatin_inventory.csv")
    fields = ["url","vin","condition","year","make","model","trim","price","mileage",
              "stock_number","exterior_color","interior_color","drivetrain","transmission","engine","images"]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (compatible; ScraperAgent/1.0)")
        page = await context.new_page()

        # collect detail links
        detail_links = set()
        for url in LIST_START_URLS:
            try:
                for u in await gather_detail_links(page, url):
                    if DETAIL_HREF.search(urlparse(u).path):
                        detail_links.add(u)
            except Exception as e:
                print("[WARN] gather failed:", url, e)

        # extract details
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
            for i, url in enumerate(sorted(detail_links)):
                try:
                    row = await parse_vehicle_detail(page, url)
                    w.writerow(row)
                    if (i+1) % 5 == 0:
                        await page.wait_for_timeout(500)
                except Exception as e:
                    print("[WARN] parse failed:", url, e)

        await browser.close()
    print("Saved ->", out_csv.resolve())

if __name__ == "__main__":
    asyncio.run(main())