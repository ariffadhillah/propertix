from bs4 import BeautifulSoup

def parse_listing(html, url):
    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("h1")
    price = soup.select_one(".price")

    return {
        "listing_url": url,
        "title": title.get_text(strip=True) if title else None,
        "price": price.get_text(strip=True) if price else None,
        "location": None,
        "beds": None,
        "baths": None,
        "land_size": None,
        "building_size": None,
        "description": None,
        "images": []
    }