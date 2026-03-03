from scraper.core.schema import (
    coerce_offer_category,
    coerce_tenure_type,
    coerce_rent_period,
    map_subtype_and_asset_class,
)

from scraper.core.reso_mapper import to_reso_listing
from typing import Any, Dict
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit

BASE = "https://propertia.com"


# -------------------------
# Session helper
# -------------------------
def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://propertia.com/",
    })
    return s



# -------------------------
# Generic helpers
# -------------------------

def _extract_numbers_from_description(desc: str | None) -> dict[str, str]:
    if not desc:
        return {}

    text = desc.lower()

    # bedrooms: "3-bedroom", "3 bedroom", "3 bedrooms"
    m_bed = re.search(r"\b(\d+(?:\.\d+)?)\s*[- ]?\s*bed(room)?s?\b", text)
    # bathrooms: "2 bathrooms", "2 bath"
    m_bath = re.search(r"\b(\d+(?:\.\d+)?)\s*[- ]?\s*bath(room)?s?\b", text)

    # building size: "142 sqm", "142 m2", "142 m²"
    m_bld = re.search(r"\b(\d{2,5}(?:[.,]\d+)?)\s*(sqm|m2|m²)\b", text)

    out = {}
    if m_bed:
        out["bedroom"] = m_bed.group(1)
    if m_bath:
        out["bathroom"] = m_bath.group(1)
    if m_bld:
        # simpan raw angka, _parse_sqm akan handle
        out["building size"] = m_bld.group(1) + " sqm"
    return out


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for x in items:
        if not x:
            continue
        x = x.strip()
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _norm_label(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace(":", "")
    return s


def get_search_siblings(
    soup: BeautifulSoup,
    label: str,
    *,
    container_css: str | None = "ul.list-2-cols",
    label_tag: str = "strong",
    value_tag: str = "span",
) -> str | None:
    """
    1 helper generik:
    PropertyID = get_search_siblings(soup, "Property ID") -> "PPL3089"
    Cocok untuk pola:
      <li><strong>Property ID</strong><span>PPL3089</span></li>
    """
    root = soup.select_one(container_css) if container_css else soup
    if not root:
        root = soup

    target = _norm_label(label)

    for lab in root.select(label_tag):
        if _norm_label(lab.get_text(" ", strip=True)) != target:
            continue

        sib = lab.find_next_sibling(value_tag)
        if sib:
            v = sib.get_text(" ", strip=True)
            return v or None

        li = lab.find_parent("li")
        if li:
            v = li.select_one(value_tag)
            if v:
                vv = v.get_text(" ", strip=True)
                return vv or None

        return None

    return None


def extract_facts_list2cols(soup: BeautifulSoup) -> dict[str, str]:
    """
    Ambil facts dari <ul class="list-2-cols"> menggunakan get_search_siblings().
    """
    labels = [
        "Property ID",
        "Property Status",
        "Property Type",
        "Price",
        "Lease Years",
        "Price per Are per year",
        "Land Size",
        "Area",
    ]
    out: dict[str, str] = {}
    for lab in labels:
        v = get_search_siblings(soup, lab, container_css="ul.list-2-cols")
        if v:
            out[lab] = v
    return out


# -------------------------
# Parsing helpers (numbers)
# -------------------------
def parse_idr_amount(raw: str | None) -> float | None:
    if not raw:
        return None
    s = raw.strip()
    s = s.replace("IDR", "").replace("idr", "").strip()
    s = s.split("/")[0].strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except:
        return None


def parse_int(raw: str | None) -> int | None:
    if not raw:
        return None
    s = re.sub(r"[^\d]", "", raw)
    if not s:
        return None
    try:
        return int(s)
    except:
        return None


# -------------------------
# Required by parse_detail_page
# -------------------------
def extract_price_categories(soup: BeautifulSoup) -> list[str]:
    """
    Dipakai oleh parse_detail_page -> infer_client_taxonomy()
    Kita isi minimal sinyal tenure/rent-period dari facts.
    """
    facts = extract_facts_list2cols(soup)
    cats: list[str] = []

    ptype = (facts.get("Property Type") or "").lower()
    status = (facts.get("Property Status") or "").lower()

    # tenure
    if "leasehold" in ptype:
        cats.append("leasehold")
    if "freehold" in ptype:
        cats.append("freehold")

    # rent period (kalau suatu saat muncul)
    if "monthly" in ptype or "monthly" in status:
        cats.append("monthly")
    if "yearly" in ptype or "yearly" in status:
        cats.append("yearly")

    return _dedupe_preserve_order(cats)


def _map_period(category: str) -> str | None:
    c = (category or "").lower()
    if c in ("freehold", "leasehold"):
        return "one_time"
    if c == "yearly":
        return "year"
    if c == "monthly":
        return "month"
    return None


def extract_prices(soup: BeautifulSoup) -> list[dict]:
    """
    Dipakai oleh parse_detail_page -> choose_primary_price()
    Menghasilkan format internal prices[] yang nanti diubah to_money().
    """
    facts = extract_facts_list2cols(soup)
    amount = parse_idr_amount(facts.get("Price"))
    if amount is None:
        return []

    ptype = (facts.get("Property Type") or "").lower()
    if "leasehold" in ptype:
        category = "leasehold"
    elif "freehold" in ptype:
        category = "freehold"
    else:
        category = "freehold"

    return [{
        "currency": "IDR",
        "amount": amount,
        "period": _map_period(category),
        "category": category,
    }]


def parse_side_location(soup: BeautifulSoup) -> dict | None:
    """
    Dipakai oleh parse_detail_page untuk mengisi listing["location"].
    """
    facts = extract_facts_list2cols(soup)
    area = facts.get("Area")
    if not area:
        return None
    return {"area": area.strip(), "sub_area": None}





def _parse_sqm(val: str) -> float | None:
    """
    Dipakai parse_detail_page:
      land_size = _parse_sqm(general.get("land size", ""))
    Kita tambah support 'Are' -> sqm (1 are = 100 sqm)
    """
    if not val:
        return None
    s = val.replace("\xa0", " ").strip().lower()

    # handle are
    m = re.search(r"([\d.,]+)\s*are\b", s)
    if m:
        num = m.group(1).replace(".", "").replace(",", ".")
        try:
            return float(num) * 100.0
        except:
            return None

    # handle sqm / m2 / m²
    s = s.replace("m²", "").replace("sqm", "").replace("m2", "")
    s = re.sub(r"[^\d.,]", "", s).strip()
    if not s:
        return None
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
    for cat in ["freehold", "leasehold", "yearly", "monthly"]:
        if cat in all_by_cat:
            return cat, all_by_cat[cat]
    k = next(iter(all_by_cat.keys()))
    return k, all_by_cat[k]


def choose_primary_price(prices: list[dict], source_url: str) -> dict | None:
    if not prices:
        return None

    url = (source_url or "").lower()

    def find_cat(cat: str):
        for p in prices:
            if p.get("category") == cat:
                return p
        return None

    if "/for-sale/" in url or "/sale/" in url:
        return find_cat("freehold") or find_cat("leasehold") or prices[0]

    if "/for-rent/" in url or "/rent/" in url:
        return find_cat("yearly") or find_cat("monthly") or prices[0]

    return find_cat("freehold") or find_cat("leasehold") or find_cat("yearly") or find_cat("monthly") or prices[0]


# -------------------------
# Taxonomy / description / title
# -------------------------
def parse_taxonomy_from_url(url: str) -> dict:
    """
    URL Propertia biasanya tidak punya /for-sale/ seperti BHI,
    jadi ini kemungkinan banyak None (tidak masalah).
    """
    if not url:
        return {}

    path = urlsplit(url).path.lower().strip("/")
    parts = path.split("/")

    out = {"intent": None, "property_type": None, "tenure": None, "rent_period": None}

    for p in parts:
        if p == "for-sale":
            out["intent"] = "sale"
        elif p == "for-rent":
            out["intent"] = "rent"

    try:
        idx = parts.index("for-sale")
    except ValueError:
        try:
            idx = parts.index("for-rent")
        except ValueError:
            return out

    if idx + 1 < len(parts):
        out["property_type"] = parts[idx + 1]

    if idx + 2 < len(parts):
        token = parts[idx + 2]
        if token in ("freehold", "leasehold"):
            out["tenure"] = token
        if token in ("daily", "nightly"):
            out["rent_period"] = "night"
        elif token in ("weekly", "week"):
            out["rent_period"] = "week"
        elif token in ("monthly", "month"):
            out["rent_period"] = "month"
        elif token in ("yearly", "annual", "year"):
            out["rent_period"] = "year"

    if out["tenure"] is None:
        for t in ("freehold", "leasehold"):
            if t in parts:
                out["tenure"] = t

    return out


def extract_title(soup: BeautifulSoup) -> str | None:
    el = soup.select_one(".property-title-wrap .page-title h1") or soup.select_one("h1")
    if not el:
        return None
    t = el.get_text(" ", strip=True)
    return t or None


def extract_description(soup: BeautifulSoup) -> str | None:
    box = soup.select_one(".property-description-content .description-content")
    if not box:
        return None

    parts: list[str] = []
    for p in box.select("p"):
        txt = p.get_text(" ", strip=True)
        if txt:
            parts.append(txt)

    parts = _dedupe_preserve_order(parts)
    desc = "\n\n".join(parts).strip()
    return desc or None


def extract_images(soup: BeautifulSoup) -> list[str]:
    # placeholder, isi nanti
    return []


def extract_breadcrumb_texts(soup: BeautifulSoup) -> list[str]:
    # placeholder, isi nanti
    return []


# -------------------------
# Broker placeholders (isi nanti)
# -------------------------
def parse_footer_broker(soup: BeautifulSoup, page_url: str) -> dict:
    return {
        "agency_name": None,
        "broker_email": None,
        "broker_phone_raw": None,
        "contact_links_raw": {
            "mailto": [],
            "tel": [],
            "whatsapp": [],
            "messenger": [],
            "form": [],
            "other": [],
        },
    }


def normalize_phone_id(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("++"):
        s = "+" + s.lstrip("+")
    if s.startswith("+62"):
        digits = re.sub(r"[^\d]", "", s)
        return "+" + digits
    if s.startswith("62"):
        digits = re.sub(r"[^\d]", "", s)
        return "+" + digits
    if s.startswith("0"):
        digits = re.sub(r"[^\d]", "", s)
        return "+62" + digits[1:]
    digits = re.sub(r"[^\d]", "", s)
    if len(digits) >= 9:
        return "+62" + digits
    return None


def extract_email_from_soup(soup: BeautifulSoup) -> str | None:
    return None


def extract_phone_from_soup(soup: BeautifulSoup) -> str | None:
    return None


def parse_broker_block(soup: BeautifulSoup, page_url: str) -> dict:
    footer = parse_footer_broker(soup, page_url)
    broker_phone_raw = footer.get("broker_phone_raw")
    return {
        "broker_name": None,
        "broker_phone_raw": broker_phone_raw,
        "broker_phone": normalize_phone_id(broker_phone_raw),
        "broker_email": footer.get("broker_email"),
        "broker_profile_url": None,
        "agency_name": footer.get("agency_name"),
        "contact_links_raw": footer.get("contact_links_raw") or {
            "mailto": [],
            "tel": [],
            "whatsapp": [],
            "messenger": [],
            "form": [],
            "other": [],
        },
    }


def infer_client_taxonomy(taxonomy_from_url: dict, price_categories: list[str]) -> dict:
    offer = coerce_offer_category(taxonomy_from_url.get("intent"))
    tenure = coerce_tenure_type(taxonomy_from_url.get("tenure"))
    rent_period = coerce_rent_period(taxonomy_from_url.get("rent_period"))

    cats = set(price_categories or [])

    if "yearly" in cats or "monthly" in cats:
        offer = "rent"
    if "freehold" in cats or "leasehold" in cats:
        offer = "sale" if offer != "rent" else offer

    if "freehold" in cats:
        tenure = "freehold"
    elif "leasehold" in cats:
        tenure = "leasehold"

    if "monthly" in cats:
        rent_period = "month"
    elif "yearly" in cats:
        rent_period = "year"

    return {"offer_category": offer, "tenure_type": tenure, "rent_period": rent_period}


def extract_section_by_category(soup: BeautifulSoup, section_prefix: str) -> dict[str, dict[str, str]]:
    facts = extract_facts_list2cols(soup)

    # ambil fallback dari description
    desc = extract_description(soup)
    desc_kv = _extract_numbers_from_description(desc)

    if section_prefix == "list-general-information":
        land = facts.get("Land Size")
        building = (
            facts.get("Building Size")
            or facts.get("Building size")
            or desc_kv.get("building size")
        )

        row: dict[str, str] = {}
        if land:
            row["land size"] = land
        if building:
            row["building size"] = building

        return {"freehold": row} if row else {}

    if section_prefix == "list-indoor":
        # dari facts dulu, fallback description
        bed = facts.get("Bedroom") or facts.get("Bedrooms") or desc_kv.get("bedroom")
        bath = facts.get("Bathroom") or facts.get("Bathrooms") or desc_kv.get("bathroom")

        row: dict[str, str] = {}
        if bed:
            row["bedroom"] = bed
        if bath:
            row["bathroom"] = bath

        return {"freehold": row} if row else {}

    return {}

# ============================================================
# !!! WARNING !!!
# JANGAN UBAH APA PUN DI DALAM parse_detail_page()
# ============================================================
def parse_detail_page(item: Dict[str, Any]) -> Dict[str, Any]:
    url = item["url"]

    session = _make_session()
    r = session.get(url, timeout=30, allow_redirects=True)
    # kadang perlu coba 1x lagi dengan referer = url sendiri
    if r.status_code == 403:
        session.headers["Referer"] = url
        r = session.get(url, timeout=30, allow_redirects=True)

    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")


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
    broker = parse_broker_block(soup, url)

    def to_money(p: dict) -> dict:
        return {"currency": p["currency"], "amount": p["amount"], "period": p.get("period")}

    # ---- NEW: strongest taxonomy from side-info + url fallback
    price_categories = extract_price_categories(soup)
    client_tax = infer_client_taxonomy(taxonomy, price_categories)

    # ---- NEW: map subtype/asset_class from raw property type (URL segment for now)
    raw_type = taxonomy.get("property_type")
    asset_class, property_subtype = map_subtype_and_asset_class(raw_type)

    listing = {
        "source_listing_id": item["source_listing_id"],
        "source_url": url,
        "title": title,
        "description": description,

        # ✅ Client fields
        "offer_category": client_tax["offer_category"],
        "tenure_type": client_tax["tenure_type"],
        "rent_period": client_tax["rent_period"],
        "asset_class": asset_class,
        "property_subtype": property_subtype,

        # (optional) legacy fields sementara
        "intent": taxonomy.get("intent") or "unknown",
        "property_type": taxonomy.get("property_type") or "unknown",
        "tenure": taxonomy.get("tenure") or "unknown",

        "price": to_money(primary) if primary else None,
        "prices": [to_money(p) for p in prices],

        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "land_size_sqm": land_size,
        "building_size_sqm": building_size,

        "location": None,
        "images": images,

        # "broker_name": None,
        # "broker_phone": None,
        # "broker_email": None,

        "broker_name": broker.get("broker_name"),
        "broker_phone": broker.get("broker_phone"),   # normalized
        "broker_email": broker.get("broker_email"),
        "broker_profile_url": broker.get("broker_profile_url"),
        "agency_name": broker.get("agency_name"),
        
        "broker_phone_raw": broker.get("broker_phone_raw"),
        "contact_links_raw": broker.get("contact_links_raw"),

        "raw": {
            "debug": {"fetched_url": url},
            "url_taxonomy": taxonomy,
            "price_categories": price_categories,
            "breadcrumb": extract_breadcrumb_texts(soup),
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
            },
            "contact": {
                "broker_phone_raw": broker.get("broker_phone_raw"),
                "contact_links_raw": broker.get("contact_links_raw"),
            }
        }
    }

    side_loc = parse_side_location(soup)
    if side_loc:
        loc = listing.get("location") or {}
        if not isinstance(loc, dict):
            loc = {}
        if not loc.get("area") and side_loc.get("area"):
            loc["area"] = side_loc["area"]
        if not loc.get("sub_area") and side_loc.get("sub_area"):
            loc["sub_area"] = side_loc["sub_area"]
        listing["location"] = loc or None

    return listing