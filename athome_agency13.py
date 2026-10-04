import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException

# -------------------------------
# USER CONFIGURATION
# -------------------------------
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)

# Base URL without the page parameter
base_url = "https://www.athome.lu/srp/?tr=rent&bedrooms_min=2&price_min=1200&sort=price_asc&q=faee1a4a&loc=L2-luxembourg&ptypes=house,flat,new-property,build"

private_listings = []

# Load the base URL to determine the max page number.
driver.get(base_url)
time.sleep(3)

max_page = 1
try:
    pagination_links = driver.find_elements(By.CSS_SELECTOR, "ul.pagination li a")
    for link in pagination_links:
        text = link.text.strip()
        if text.isdigit():
            page_num = int(text)
            if page_num > max_page:
                max_page = page_num
except Exception as e:
    print("Error detecting pagination:", e)

print(f"Detected max page number: {max_page}")
if max_page == 1:
    max_page = 40
    print("Fallback: setting max page to 40.")

print(f"Starting scraping from page {max_page} to 1...")

for page in range(max_page, 0, -1):
    print(f"Scraping page {page}...")
    url = base_url + f"&page={page}"
    driver.get(url)
    time.sleep(3)

    listings = driver.find_elements(By.CSS_SELECTOR, "article.property-article")
    if not listings:
        print(f"No listings found on page {page}. Skipping.")
        continue

    for listing in listings:
        try:
            title_elem = listing.find_element(By.CSS_SELECTOR, "a.property-title")
            detail_link = title_elem.get_attribute("href")
            fallback_title = title_elem.text.strip()
        except Exception as e:
            print("Skipping listing; couldn't extract title/detail link:", e)
            continue

        driver.execute_script("window.open('{}');".format(detail_link))
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(5)

        # Detect private-owner listings from the rendered page text instead of
        # relying on atHome's CSS classes, which can change without notice.
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
        except Exception as e:
            print("Could not read detail page body:", e)
            page_text = ""

        is_private = "Particulier opposé au démarchage commercial" in page_text

        if is_private:
            print("Private listing found:", detail_link)
            try:
                title_text = driver.find_element(By.CSS_SELECTOR, "h1.property-title").text.strip()
            except NoSuchElementException:
                print("Title not found on detail page, using fallback from search page.")
                title_text = fallback_title
            try:
                price_text = driver.find_element(By.CSS_SELECTOR, "span.property-price").text.strip()
            except NoSuchElementException:
                print("Price not found on detail page.")
                price_text = "N/A"

            private_listings.append({
                "title": title_text,
                "price": price_text,
                "url": detail_link
            })
        else:
            print("Not a private listing:", detail_link)

        driver.close()
        driver.switch_to.window(driver.window_handles[0])

driver.quit()

with open("private_listings.csv", mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "price", "url"])
    writer.writeheader()
    writer.writerows(private_listings)

print(f"Scraping complete. Found {len(private_listings)} private listings.")
print("Results saved to private_listings.csv")
