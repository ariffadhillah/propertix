from scraper.core.reso_mapper import to_reso_listing
from typing import Any, Dict
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from urllib.parse import urlsplit
# image parsing helpers

BASE = "https://bali-home-immo.com"





def parse_taxonomy_from_url(url: str) -> dict:
    """
    Extract intent / property_type / tenure / rent_period from BHI URL.
    Example:
    /for-sale/villa/leasehold/...
    /for-rent/villa/monthly/...
    """
    if not url:
        return {}

    path = urlsplit(url).path.lower().strip("/")
    parts = path.split("/")

    out = {
        "intent": None,
        "property_type": None,
        "tenure": None,
        "rent_period": None,
    }

    for i, p in enumerate(parts):
        if p == "for-sale":
            out["intent"] = "sale"
        elif p == "for-rent":
            out["intent"] = "rent"

    # find position of for-sale / for-rent
    try:
        idx = parts.index("for-sale")
    except ValueError:
        try:
            idx = parts.index("for-rent")
        except ValueError:
            return out

    # property type (usually next segment)
    if idx + 1 < len(parts):
        out["property_type"] = parts[idx + 1]

    # next segment could be tenure OR rent period
    if idx + 2 < len(parts):
        token = parts[idx + 2]

        if token in ("freehold", "leasehold"):
            out["tenure"] = token

        if token in ("daily", "nightly"):
            out["rent_period"] = "day"
        elif token in ("weekly", "week"):
            out["rent_period"] = "week"
        elif token in ("monthly", "month"):
            out["rent_period"] = "month"
        elif token in ("yearly", "year"):
            out["rent_period"] = "year"

    # sometimes tenure is next after subtype and area
    if out["tenure"] is None:
        for t in ("freehold", "leasehold"):
            if t in parts:
                out["tenure"] = t

    return out


# deskripsion
def extract_description(soup: BeautifulSoup) -> str | None:
    box = soup.select_one("div.property-info-desc")
    if not box:
        return None

    # ambil per paragraf supaya rapi
    parts: list[str] = []
    for p in box.select("p"):
        text = p.get_text(" ", strip=True)  # strong + br jadi teks biasa
        if text:
            parts.append(text)

    desc = "\n\n".join(parts).strip()
    return desc or None

# end deskripsion

def extract_images(soup: BeautifulSoup) -> list[str]:
    """
    Extract image URLs from main swiper (primary gallery).
    Handles src + data-src (lazy).
    Dedupes while preserving order.
    """
    urls: list[str] = []

    # Ambil dari swiper utama saja (menghindari duplikat modal/thumbs)
    for img in soup.select("div.swiper.main-swiper img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue

        src = src.strip()
        if not src:
            continue

        # ensure absolute
        if src.startswith("/"):
            src = urljoin(BASE, src)

        # filter hanya image properti
        if "/images/properties/" not in src:
            continue

        urls.append(src)

    # dedupe preserve order
    seen = set()
    out = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)

    return out
# end image parsing helpers

# tabel generik
def _norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _parse_sqm(val: str) -> float | None:
    if not val:
        return None
    # contoh "100 m²" -> 100
    s = val.replace("\xa0", " ").strip().lower()
    s = s.replace("m²", "").replace("sqm", "").replace("m2", "")
    s = re.sub(r"[^\d.,]", "", s).strip()
    if not s:
        return None
    # "1.200" (ID style thousand sep) -> 1200
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None

def _parse_number(val: str) -> float | None:
    if not val:
        return None
    s = val.strip()
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None

def extract_table_kv(container) -> dict[str, str]:
    """
    container: element div#list-xxx-{cat}
    supports 2 formats:
    - 3 td: key, ':', value
    - 2 td: key, ': value' (outdoor)
    """
    out: dict[str, str] = {}
    if not container:
        return out

    for tr in container.select("table.table tbody tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        if len(tds) >= 3:
            key = tds[0].get_text(" ", strip=True)
            val = tds[2].get_text(" ", strip=True)
        else:
            # format outdoor: <td>Swimming Pool</td><td>: Yes</td>
            key = tds[0].get_text(" ", strip=True)
            val = tds[1].get_text(" ", strip=True) if len(tds) > 1 else ""
            val = val.lstrip(":").strip()

        if key:
            out[_norm_key(key)] = (val or "").strip()

    return out

    # end tabel generik


# categotory
def extract_section_by_category(soup: BeautifulSoup, section_prefix: str) -> dict[str, dict[str, str]]:
    """
    section_prefix contoh:
    - "list-general-information"
    - "list-indoor"
    - "list-outdoor"
    - "list-facilities"
    return: {category: {key: value}}
    """
    out: dict[str, dict[str, str]] = {}
    for cat in ["freehold", "leasehold", "yearly", "monthly"]:
        el = soup.select_one(f"#{section_prefix}-{cat}")
        kv = extract_table_kv(el)
        if kv:
            out[cat] = kv
    return out

# def choose_primary_category(source_url: str) -> str:
#     url = (source_url or "").lower()
#     if "/for-sale/" in url or "/sale/" in url:
#         return "freehold"  # fallback kalau freehold tidak ada, nanti kita fallback di code
#     if "/rent/" in url:
#         return "yearly"
#     return "freehold"

def choose_primary_category(source_url: str) -> str:
    url = (source_url or "").lower()
    if "/for-sale/" in url or "/sale/" in url:
        return "freehold"
    if "/for-rent/" in url or "/rent/" in url:
        return "yearly"
    return "freehold"


def pick_category_dict(all_by_cat: dict[str, dict[str, str]], preferred: str) -> tuple[str | None, dict[str, str]]:
    if not all_by_cat:
        return None, {}
    if preferred in all_by_cat:
        return preferred, all_by_cat[preferred]
    # fallback urutan
    for cat in ["freehold", "leasehold", "yearly", "monthly"]:
        if cat in all_by_cat:
            return cat, all_by_cat[cat]
    # fallback first
    k = next(iter(all_by_cat.keys()))
    return k, all_by_cat[k]

# end categotory




# price parsing helpers
def _parse_amount(raw: str) -> float | None:
    if not raw:
        return None
    s = raw.strip()

    # handle "Price On Request"
    if "request" in s.lower():
        return None

    # ambil sebelum "/year" atau "/month"
    s = s.split("/")[0].strip()

    # "1.800.000.000" -> "1800000000"
    s = s.replace(".", "").replace(",", "")
    # sisakan digit saja
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except:
        return None

def _map_period(category: str) -> str | None:
    c = (category or "").lower()
    if c in ("freehold", "leasehold"):
        return "one_time"
    if c == "yearly":
        return "year"
    if c == "monthly":
        return "month"
    return None

# price
def clean_price_number(raw: str) -> float | None:
    if not raw:
        return None
    
    raw = raw.replace(" ", "")
    raw = raw.split("/")[0]  
    raw = raw.replace(".", "")

    try:
        return float(raw)
    except:
        return None

def extract_prices(soup: BeautifulSoup) -> list[dict]:
    spans = soup.select("span[data-price][data-price-category]")
    out = []

    for sp in spans:
        raw_price = sp.get("data-price", "").strip()
        category = sp.get("data-price-category", "").strip().lower()

        amount = _parse_amount(raw_price)
        if amount is None:
            continue

        out.append({
            "currency": "IDR",
            "amount": amount,
            "period": _map_period(category),
            # simpan category di raw/debug kalau mau
            "category": category,
        })

    # dedupe by (amount, period, category)
    seen = set()
    deduped = []
    for p in out:
        k = (p["amount"], p["period"], p["category"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(p)

    return deduped

def choose_primary_price(prices: list[dict], source_url: str) -> dict | None:
    if not prices:
        return None

    url = (source_url or "").lower()

    # helper cari by category
    def find_cat(cat: str):
        for p in prices:
            if p.get("category") == cat:
                return p
        return None

    # sale page → prefer freehold/leasehold
    if "/for-sale/" in url or "/sale/" in url:
        return find_cat("freehold") or find_cat("leasehold") or prices[0]

    # rent page → prefer yearly, then monthly
    if "/rent/" in url:
        return find_cat("yearly") or find_cat("monthly") or prices[0]

    # fallback umum
    return find_cat("freehold") or find_cat("leasehold") or find_cat("yearly") or find_cat("monthly") or prices[0]


# end price


def extract_title(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("h1.title")
    if not el:
        return None
    # get_text akan mengubah &amp; menjadi &
    title = el.get_text(" ", strip=True)
    return title or None


def parse_detail_page(item: Dict[str, Any]) -> Dict[str, Any]:
    url = item["url"]

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # --- taxonomy from URL (intent, property_type, tenure, rent_period)
    taxonomy = parse_taxonomy_from_url(url)

    title = extract_title(soup)
    prices = extract_prices(soup)
    primary = choose_primary_price(prices, url)

    preferred_cat = choose_primary_category(url)

    general_all = extract_section_by_category(soup, "list-general-information")
    indoor_all  = extract_section_by_category(soup, "list-indoor")
    outdoor_all = extract_section_by_category(soup, "list-outdoor")
    fac_all     = extract_section_by_category(soup, "list-facilities")

    gen_cat, general = pick_category_dict(general_all, preferred_cat)
    in_cat, indoor   = pick_category_dict(indoor_all, preferred_cat)

    land_size = _parse_sqm(general.get("land size", ""))
    building_size = _parse_sqm(general.get("building size", ""))

    bedrooms = _parse_number(indoor.get("bedroom", ""))
    bathrooms = _parse_number(indoor.get("bathroom", ""))

    images = extract_images(soup)
    description = extract_description(soup)

    def to_money(p: dict) -> dict:
        return {"currency": p["currency"], "amount": p["amount"], "period": p.get("period")}

    listing = {
        "source_listing_id": item["source_listing_id"],
        "source_url": url,
        "title": title,
        "description": description,

        # ✅ ambil dari taxonomy, fallback ke unknown
        "intent": taxonomy.get("intent") or "unknown",
        "property_type": taxonomy.get("property_type") or "unknown",
        "tenure": taxonomy.get("tenure"),
        "rent_period": taxonomy.get("rent_period"),

        "price": to_money(primary) if primary else None,
        "prices": [to_money(p) for p in prices],

        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "land_size_sqm": land_size,
        "building_size_sqm": building_size,

        "location": None,   # (nanti kita isi dari side-location / map embed)
        "images": images,

        "broker_name": None,
        "broker_phone": None,
        "broker_email": None,

        "raw": {
            "debug": {"fetched_url": url},
            "url_taxonomy": taxonomy,
            "bhi_sections": {
                "general_information": general_all,
                "indoor": indoor_all,
                "outdoor": outdoor_all,
                "facilities": fac_all,
                "primary_category_used": {
                    "preferred": preferred_cat,
                    "general": gen_cat,
                    "indoor": in_cat,
                }
            }
        }
    }

    return listing


# def parse_detail_page(item: Dict[str, Any]) -> Dict[str, Any]:


#     taxonomy = parse_taxonomy_from_url(listing.get("source_url"))
#     if taxonomy.get("intent"):
#         listing["intent"] = taxonomy["intent"]
#     if taxonomy.get("property_type"):
#         listing["property_type"] = taxonomy["property_type"]
#     if taxonomy.get("tenure"):
#         listing["tenure"] = taxonomy["tenure"]
#     if taxonomy.get("rent_period"):
#         listing["rent_period"] = taxonomy["rent_period"]
#     # save raw breadcrumb for audit
#     raw = listing.get("raw") or {}
#     raw["url_taxonomy"] = taxonomy
#     listing["raw"] = raw


#     url = item["url"]
#     r = requests.get(url, timeout=30)
#     r.raise_for_status()
#     soup = BeautifulSoup(r.text, "lxml")

#     title = extract_title(soup)
#     prices = extract_prices(soup)
#     primary = choose_primary_price(prices, url)


#     preferred_cat = choose_primary_category(url)

#     general_all = extract_section_by_category(soup, "list-general-information")
#     indoor_all  = extract_section_by_category(soup, "list-indoor")
#     outdoor_all = extract_section_by_category(soup, "list-outdoor")
#     fac_all     = extract_section_by_category(soup, "list-facilities")

#     gen_cat, general = pick_category_dict(general_all, preferred_cat)
#     in_cat, indoor   = pick_category_dict(indoor_all, preferred_cat)

#     land_size = _parse_sqm(general.get("land size", ""))
#     building_size = _parse_sqm(general.get("building size", ""))

#     bedrooms = _parse_number(indoor.get("bedroom", ""))
#     bathrooms = _parse_number(indoor.get("bathroom", ""))
    
#     images = extract_images(soup)
    
#     description = extract_description(soup)


#     def to_money(p: dict) -> dict:
#         return {"currency": p["currency"], "amount": p["amount"], "period": p.get("period")}
    
#     print(listing["intent"], listing["property_type"], listing.get("tenure"), listing.get("rent_period"))
    
#     listing = {
#         "source_listing_id": item["source_listing_id"],
#         "source_url": url,
#         "title": title,
#         "description": description,
#         "intent": "unknown",
#         "property_type": "unknown",
#         "price": to_money(primary) if primary else None,
#         "prices": [to_money(p) for p in prices],
#         "bedrooms": bedrooms,
#         "bathrooms": bathrooms,
#         "land_size_sqm": land_size,
#         "building_size_sqm": building_size,
#         "location": None,
#         "images": images,
#         "broker_name": None,
#         "broker_phone": None,
#         "broker_email": None,
#         "raw": {
#             "debug": {"fetched_url": url},
#             "bhi_sections": {
#                 "general_information": general_all,
#                 "indoor": indoor_all,
#                 "outdoor": outdoor_all,
#                 "facilities": fac_all,
#                 "primary_category_used": {
#                     "preferred": preferred_cat,
#                     "general": gen_cat,
#                     "indoor": in_cat,
#                 }
#             }
#         }
#     }

#     # source_key untuk site ini
#     # listing["reso"] = to_reso_listing(listing, source_key="bali-home-immo")
#     return listing








#    # return {
#     #     "source_listing_id": item["source_listing_id"],
#     #     "source_url": url,
#     #     "title": title,
#     #     "description": None,
#     #     "intent": "unknown",
#     #     "property_type": "unknown",
#     #     "price": to_money(primary) if primary else None,
#     #     "prices": [to_money(p) for p in prices],
#     #     "bedrooms": bedrooms,
#     #     "bathrooms": bathrooms,
#     #     "land_size_sqm": land_size,
#     #     "building_size_sqm": building_size,
#     #     "location": None,
#     #     "images": [],
#     #     "broker_name": None,
#     #     "broker_phone": None,
#     #     "broker_email": None,
#     #     "raw": {
#     #         "debug": {"fetched_url": url},
#     #         "bhi_sections": {
#     #             "general_information": general_all,
#     #             "indoor": indoor_all,
#     #             "outdoor": outdoor_all,
#     #             "facilities": fac_all,
#     #             "primary_category_used": {
#     #                 "preferred": preferred_cat,
#     #                 "general": gen_cat,
#     #                 "indoor": in_cat,
#     #             }
#     #         }
#     #     }
#     # }


