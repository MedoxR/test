import csv, json, re, time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

BASE = "https://www.athome.lu/srp/?tr=rent&bedrooms_min=2&price_min=1200&sort=price_asc&q=faee1a4a&loc=L2-luxembourg&ptypes=house,flat,new-property,build"
HISTORY = Path("previous_private_listings.json")
MARKER = "Particulier opposé au démarchage commercial"
options = Options()
for flag in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage"):
    options.add_argument(flag)
driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(45)

def visit(url, attempts=3):
    for n in range(attempts):
        try:
            driver.get(url)
            WebDriverWait(driver, 20).until(lambda d: d.find_elements(By.TAG_NAME, "body"))
            time.sleep(3)
            return True
        except Exception as exc:
            print(f"Load failure {n+1}/{attempts}: {url}: {exc}", flush=True)
            time.sleep(3 * (n+1))
    return False

def find_cards():
    found = {}
    for article in driver.find_elements(By.CSS_SELECTOR, "article.property-article"):
        for link in article.find_elements(By.CSS_SELECTOR, 'a[href*="/location/"][href*="/id-"]'):
            href = link.get_attribute("href")
            if href:
                found[href.split("?")[0]] = link.text.strip()
    return found

def inspect(url, fallback):
    for attempt in range(3):
        if not visit(url, 1):
            continue
        text = driver.find_element(By.TAG_NAME, "body").text
        if MARKER in text:
            headings = driver.find_elements(By.TAG_NAME, "h1")
            title = headings[0].text.strip() if headings and headings[0].text.strip() else fallback
            price = re.search(r"\b[\d\s.,]+\s*€", text)
            return {"title": title, "price": price.group(0).strip() if price else "N/A", "url": url}
        time.sleep(2 * (attempt+1))
    return None

try:
    previous = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {}
    discovered, failed_pages = {}, []
    for page in range(1, 41):
        url = f"{BASE}&page={page}"
        cards = {}
        for attempt in range(3):
            if visit(url, 1):
                cards = find_cards()
            if cards:
                break
            time.sleep(3)
        if not cards:
            failed_pages.append(page)
        discovered.update(cards)
        print(f"Page {page}: {len(cards)} cards; total {len(discovered)}", flush=True)

    # Recheck all previously confirmed private listings even when search misses them.
    targets = {**{url: row.get("title", "") for url, row in previous.items()}, **discovered}
    confirmed, uncertain = {}, {}
    for index, (url, title) in enumerate(targets.items(), 1):
        result = inspect(url, title)
        if result:
            confirmed[url] = result
        elif url in previous:
            # A missing marker is inconclusive; preserve the last known result.
            uncertain[url] = previous[url]
        print(f"Checked {index}/{len(targets)}: {'private' if result else 'unconfirmed'} {url}", flush=True)

    results = {**uncertain, **confirmed}
    with open("private_listings.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["title", "price", "url"])
        writer.writeheader()
        writer.writerows(results.values())
    HISTORY.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Confirmed {len(confirmed)}; retained for recheck {len(uncertain)}; CSV total {len(results)}", flush=True)
    print(f"Empty/failed search pages: {failed_pages}", flush=True)
finally:
    driver.quit()
