import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =====================
# HELPERS
# =====================

def fetch(url, retries=3, delay=2):
    for _ in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r
        except Exception:
            time.sleep(delay)
    print("Failed:", url)
    return None


def extract_measure(text):
    """
    Extract numeric value + unit
    '85 m²' -> (85.0, 'm²')
    '1.69 Are' -> (1.69, 'Are')
    """
    if not text:
        return None, None

    cleaned = text.replace(",", "").strip()

    num_match = re.search(r"[\d.]+", cleaned)
    value = float(num_match.group()) if num_match else None

    unit = re.sub(r"[\d.,\s]", "", cleaned)
    unit = unit or None

    return value, unit


def extract_description(soup):
    container = soup.select_one(".description-content")
    if not container:
        return None

    # remove read-more button if exists
    for btn in container.select(".houzez-read-more-link"):
        btn.decompose()

    texts = [
        p.get_text(" ", strip=True)
        for p in container.select("p")
        if p.get_text(strip=True)
    ]

    if not texts:
        return None

    # normalize whitespace
    return " ".join(" ".join(texts).split())


# =====================
# MAIN SCRAPER
# =====================

def extract_features(soup):

    container = soup.select_one("#property-features-wrap")
    if not container:
        return [], {}

    all_features = []
    grouped = {}

    current_group = None

    for el in container.select(".block-content-wrap > *"):
        
        if "group_name" in el.get("class", []):
            current_group = el.get_text(strip=True)
            grouped[current_group] = []
       
        elif el.name == "ul" and current_group:
            for a in el.select("li a"):
                txt = a.get_text(strip=True)
                if txt:
                    grouped[current_group].append(txt)
                    all_features.append(txt)

    return all_features, grouped


# image
def extract_images(soup):
    images = []    
    for img in soup.select(".hs-gallery-v4-grid img"):
        src = img.get("src")
        if src and "wp-content/uploads" in src:
            images.append(src)    
    images = list(dict.fromkeys(images))
    return images if images else None


def scrape_property_detail(url):

    print("Scraping:", url)
    

    r = fetch(url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # TITLE
    title_tag = soup.select_one(".page-title h1")
    title = title_tag.get_text(strip=True) if title_tag else None

    # ADDRESS
    address_tag = soup.select_one("address.item-address")
    address = address_tag.get_text(strip=True) if address_tag else None

    # PRICE
    price_tag = soup.select_one(".item-price .price")
    price = price_tag.get_text(strip=True) if price_tag else None

    # LABELS (remove duplicates keep order)
    labels = []
    for a in soup.select(".property-labels-wrap a"):
        txt = a.get_text(strip=True)
        if txt:
            labels.append(txt)
    labels = list(dict.fromkeys(labels))

    # FACTS
    facts = {}

    for li in soup.select("#property-detail-wrap li"):
        key_tag = li.find("strong")
        val_tag = li.find("span")

        if key_tag and val_tag:
            key = key_tag.get_text(strip=True).lower().replace(" ", "_")
            value = val_tag.get_text(strip=True)
            facts[key] = value

    # ---- extract fields
    property_id = facts.get("property_id")
    property_status = facts.get("property_status")
    property_type = facts.get("property_type")
    bedrooms = facts.get("bedrooms")
    bathrooms = facts.get("bathrooms")
    building_size_text = facts.get("building_size")
    land_size_text = facts.get("land_size")
    year_built = facts.get("year_built")
    area = facts.get("area")
    years = facts.get("years")

    # year built -> int
    if year_built and str(year_built).isdigit():
        year_built = int(year_built)

    # building size
    building_size_value, building_size_unit = extract_measure(building_size_text)

    # land size
    land_size_value, land_size_unit = extract_measure(land_size_text)

    #features
    features, feature_groups = extract_features(soup)
    
    # Image
    images = extract_images(soup)

    # =====================
    # FINAL RESULT
    # =====================

    return {

        "title": title,
        "url": url,

        "property_id": property_id,
        "property_status": property_status,
        "property_type": property_type,

        "price": price,
        "years": years,

        "bedrooms": bedrooms,
        "bathrooms": bathrooms,

        # --- SIZE (TEXT + VALUE)  ⭐ PRO STRUCTURE
        "building_size": building_size_text,
        "building_size_value": building_size_value,
        "building_size_unit": building_size_unit,

        "land_size": land_size_text,
        "land_size_value": land_size_value,
        "land_size_unit": land_size_unit,

        "year_built": year_built,
        "area": area,
        "address": address,

        "labels": labels,
        "description": extract_description(soup),
        "features": features,
        "feature_groups": feature_groups,
        "images": images,
    }


# =====================
# TEST
# =====================

# if __name__ == "__main__":
#     test_url = "https://propertia.com/property/ready-to-move-in-2-bedroom-villa-in-prime-pererenan/"
#     data = scrape_property_detail(test_url)

#     from pprint import pprint
#     pprint(data)