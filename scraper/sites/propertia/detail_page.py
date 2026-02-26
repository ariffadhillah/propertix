from scraper.core.schema import (
    coerce_offer_category,
    coerce_tenure_type,
    coerce_rent_period,
    map_subtype_and_asset_class,
)

from typing import Any, Dict
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit, urlunsplit

BASE = "https://propertia.com"


# -------------------------
# small utils
# -------------------------
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


def _norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _strip_query(url: str) -> str:
    if not url:
        return url
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc, u.path, "", ""))


def _parse_number(val: str) -> float | None:
    if not val:
        return None
    s = str(val).strip()
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None


def _parse_sqm(val: str) -> float | None:
    # Propertia: "200 M2" / "200 m²"
    if not val:
        return None
    s = str(val).replace("\xa0", " ").strip().lower()
    s = s.replace("m²", "").replace("sqm", "").replace("m2", "").replace("m 2", "")
    s = re.sub(r"[^\d.,]", "", s).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None


def _parse_are(val: str) -> float | None:
    # Propertia: "3.5 ARE" (1 are = 100 sqm)
    if not val:
        return None
    s = str(val).strip().lower()
    s = s.replace("are", "").strip()
    s = re.sub(r"[^\d.,]", "", s).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None


# -------------------------
# CONTACT / BROKER (Propertia)
# -------------------------
def extract_email_from_soup(soup: BeautifulSoup) -> str | None:
    a = soup.select_one('a[href^="mailto:"]')
    if a and a.get("href"):
        email = a["href"].split("mailto:", 1)[1].split("?", 1)[0].strip()
        return email.lower() if email else None

    text = soup.get_text(" ", strip=True)
    m = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, re.I)
    return m.group(1).lower() if m else None


def extract_phone_from_soup(soup: BeautifulSoup) -> str | None:
    # only trust explicit tel: for Propertia (footer contains NIB numbers)
    a = soup.select_one('a[href^="tel:"]')
    if a and a.get("href"):
        raw = a["href"].split("tel:", 1)[1].strip()
        return raw or None
    return None


def normalize_phone_id(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None

    s = re.sub(r"[^\d+]", "", s)

    # guard: reject junk like 000..., very short, etc.
    digits_only = re.sub(r"[^\d]", "", s)
    if len(digits_only) < 9:
        return None
    if digits_only.startswith("000"):
        return None

    if s.startswith("+62"):
        return "+" + re.sub(r"[^\d]", "", s)
    if s.startswith("62"):
        return "+" + re.sub(r"[^\d]", "", s)
    if s.startswith("0"):
        return "+62" + re.sub(r"[^\d]", "", s)[1:]

    # fallback: assume already national significant number
    return "+62" + digits_only


def parse_footer_broker(soup: BeautifulSoup, page_url: str) -> dict:
    footer = soup.select_one("footer")
    contact_links_raw = {"mailto": [], "tel": [], "whatsapp": [], "messenger": [], "form": [], "other": []}

    if footer:
        for a in footer.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            low = href.lower()
            if low.startswith("mailto:"):
                contact_links_raw["mailto"].append(href)
            elif low.startswith("tel:"):
                contact_links_raw["tel"].append(href)
            elif "wa.me" in low or "api.whatsapp.com" in low or "whatsapp" in low:
                contact_links_raw["whatsapp"].append(href)
            elif "m.me/" in low or "facebook.com/messages" in low or "messenger.com" in low:
                contact_links_raw["messenger"].append(href)
            else:
                contact_links_raw["other"].append(href)

    for k in contact_links_raw:
        contact_links_raw[k] = _dedupe_preserve_order(contact_links_raw[k])

    # Propertia agency hard-default (stable)
    agency_name = "Propertia"

    footer_email = extract_email_from_soup(footer) if footer else None
    footer_phone_raw = extract_phone_from_soup(footer) if footer else None

    return {
        "agency_name": agency_name,
        "broker_email": footer_email.lower() if footer_email else None,
        "broker_phone_raw": footer_phone_raw,
        "contact_links_raw": contact_links_raw,
    }


def parse_broker_block(soup: BeautifulSoup, page_url: str) -> dict:
    """
    Propertia: agent block exists (e.g. "Arya") but often no phone/email.
    We keep schema same, but make phone robust (avoid NIB).
    """
    broker_name = None
    broker_profile_url = None
    broker_email = None
    broker_phone_raw = None

    contact_links_raw = {"mailto": [], "tel": [], "whatsapp": [], "messenger": [], "form": [], "other": []}

    # try: agent/enquiry area
    # (selector heuristik; aman kalau tidak ketemu)
    candidates = []
    candidates += soup.select("[class*='agent']")
    candidates += soup.select("[class*='enquiry']")
    candidates += soup.select("form")
    candidates = candidates or [soup]

    # pick node with agent name image/text
    best = None
    best_score = -1
    for c in candidates:
        score = 0
        if c.find(string=re.compile(r"contact me", re.I)):
            score += 2
        if c.select_one("img[alt]"):
            score += 1
        if c.select_one('a[href^="tel:"]'):
            score += 2
        if c.select_one('a[href^="mailto:"]'):
            score += 2
        if score > best_score:
            best_score = score
            best = c
    node = best or soup

    # name: from image alt "Arya" or heading near block
    img = node.select_one("img[alt]")
    if img:
        alt = (img.get("alt") or "").strip()
        if alt and len(alt) <= 80 and "image" not in alt.lower():
            broker_name = alt

    if not broker_name:
        for sel in ["h3", "h4", "h5", "strong"]:
            el = node.select_one(sel)
            if el:
                t = el.get_text(" ", strip=True)
                if t and len(t) <= 80 and "property enquiry" not in t.lower():
                    broker_name = t
                    break

    # collect explicit links (avoid NIB parsing)
    for a in node.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        low = href.lower()
        if low.startswith("mailto:"):
            contact_links_raw["mailto"].append(href)
        elif low.startswith("tel:"):
            contact_links_raw["tel"].append(href)
        elif "wa.me" in low or "api.whatsapp.com" in low or "whatsapp" in low:
            contact_links_raw["whatsapp"].append(href)
        elif "m.me/" in low or "facebook.com/messages" in low or "messenger.com" in low:
            contact_links_raw["messenger"].append(href)
        else:
            contact_links_raw["other"].append(href)

    broker_email = extract_email_from_soup(node) or extract_email_from_soup(soup)
    broker_phone_raw = extract_phone_from_soup(node) or extract_phone_from_soup(soup)

    footer = parse_footer_broker(soup, page_url)
    # merge footer links
    for k in contact_links_raw:
        contact_links_raw[k].extend((footer.get("contact_links_raw") or {}).get(k, []))
        contact_links_raw[k] = _dedupe_preserve_order(contact_links_raw[k])

    broker_phone = normalize_phone_id(broker_phone_raw)

    return {
        "broker_name": broker_name,
        "broker_phone_raw": broker_phone_raw,
        "broker_phone": broker_phone,
        "broker_email": broker_email.lower() if broker_email else None,
        "broker_profile_url": broker_profile_url,
        "agency_name": footer.get("agency_name") or "Propertia",
        "contact_links_raw": contact_links_raw,
    }


# -------------------------
# BREADCRUMB / TAXONOMY (Propertia)
# -------------------------
def extract_breadcrumb_texts(soup: BeautifulSoup) -> list[str]:
    # Propertia breadcrumb biasanya sederhana; fallback: ambil "Home" + category + title kalau ada
    items = []
    # try common breadcrumb patterns
    for li in soup.select("nav.breadcrumb, ol.breadcrumb, .breadcrumbs"):
        t = li.get_text(" ", strip=True)
        if t:
            # terlalu noisy; mending parse per link/span kalau ada
            break

    # simple heuristic:
    # ambil semua anchor yang kelihatan kayak breadcrumb
    for a in soup.select("a[href]"):
        txt = a.get_text(" ", strip=True)
        if txt in ("Home",) and txt not in items:
            items.append(txt)
            break

    # add location/category from page headings/taxonomy later (optional)
    title = extract_title(soup)
    if title:
        # sometimes category is shown near title as location (e.g. Canggu)
        # we won’t overfit; keep it minimal
        items.append(title)

    # if empty, just return []
    return _dedupe_preserve_order(items)


def parse_taxonomy_from_url(url: str) -> dict:
    # Propertia URL doesn’t encode sale/rent/tenure like BHI.
    return {"intent": None, "property_type": None, "tenure": None, "rent_period": None}


# -------------------------
# FACTS section (key part for Propertia)
# -------------------------
def extract_facts_kv(soup: BeautifulSoup) -> dict[str, str]:
    """
    Parse the "FACTS" section:
      Bedrooms 4
      Bathrooms 4
      Land Size 3.5 ARE
      Building Size 200 M2
      Property Type Leasehold Villa
      Lease Years 25 years
      Property Status For sale villa
    Approach: find header containing 'FACTS', then read nearest list items.
    """
    facts: dict[str, str] = {}

    # find a heading with FACTS
    header = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        txt = (tag.get_text(" ", strip=True) or "").strip().lower()
        if txt == "facts":
            header = tag
            break

    scope = None
    if header:
        # typically facts list is in next siblings
        scope = header.find_parent() or header

    # collect candidates for li rows
    lis = []
    if scope:
        lis = scope.find_all("li")
    if not lis:
        # fallback: scan all li but only ones that look like "Key Value"
        lis = soup.find_all("li")

    for li in lis:
        t = li.get_text(" ", strip=True)
        if not t:
            continue

        # Only accept known keys to avoid noise
        # (prevents capturing random footer/sidebar li)
        m = re.match(
            r"^(Bedrooms|Bathrooms|Land Size|Building Size|Property Type|Lease Years|Property Status)\s+(.+)$",
            t,
            re.I,
        )
        if not m:
            continue

        key = _norm_key(m.group(1))
        val = (m.group(2) or "").strip()
        if val:
            facts[key] = val

    return facts


def infer_client_taxonomy(taxonomy_from_url: dict, price_categories: list[str], facts: dict[str, str]) -> dict:
    """
    Propertia: use FACTS as strongest signal.
    Keep same output keys as BHI version.
    """
    offer = coerce_offer_category(taxonomy_from_url.get("intent"))
    tenure = coerce_tenure_type(taxonomy_from_url.get("tenure"))
    rent_period = coerce_rent_period(taxonomy_from_url.get("rent_period"))

    # FACTS: "Property Status For sale villa"
    status = (facts.get("property status") or "").lower()
    if "for sale" in status:
        offer = "sale"
    elif "for rent" in status or "rent" in status:
        offer = "rent"

    # FACTS: "Property Type Leasehold Villa" or "Freehold Villa"
    ptype = (facts.get("property type") or "").lower()
    if "leasehold" in ptype:
        tenure = "leasehold"
    elif "freehold" in ptype:
        tenure = "freehold"

    # rent_period: Propertia biasanya tidak eksplisit; keep unknown unless detected
    # (bisa kita tambah nanti kalau ada "per year/month" di facts/price label)

    return {"offer_category": offer, "tenure_type": tenure, "rent_period": rent_period}


# -------------------------
# DESCRIPTION / IMAGES / PRICE (Propertia)
# -------------------------
def extract_title(soup: BeautifulSoup) -> str | None:
    # Propertia title appears as page title/h1
    el = soup.select_one("h1")
    if not el:
        return None
    t = el.get_text(" ", strip=True)
    return t or None


def extract_description(soup: BeautifulSoup) -> str | None:
    # heuristic: pick main content area, avoid forms/sidebars
    # try common WP blocks
    candidates = []
    candidates += soup.select(".property-description")
    candidates += soup.select(".elementor-widget-container")
    candidates += soup.select("article .entry-content")
    candidates = [c for c in candidates if c]

    for c in candidates:
        text = c.get_text("\n", strip=True)
        if not text:
            continue
        # filter out noisy blocks
        if "property enquiry form" in text.lower():
            continue
        # keep a reasonable minimum length
        if len(text) >= 80:
            # normalize line breaks
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            return text or None

    return None


def _parse_amount_idr(raw: str) -> float | None:
    if not raw:
        return None
    s = str(raw).strip()

    # handle "Price On Request"
    if "request" in s.lower():
        return None

    # remove currency text
    s = s.replace("IDR", "").replace("Rp", "")
    s = s.split("/")[0].strip()

    # thousands separators
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except:
        return None


def extract_prices(soup: BeautifulSoup) -> list[dict]:
    """
    Propertia page shows IDR price (single most of the time).
    We keep same output shape as BHI: list[{currency, amount, period, category}]
    """
    out = []

    # try patterns: anything that looks like IDR + digits
    text = soup.get_text(" ", strip=True)
    m = re.search(r"\bIDR\s*[\d\.,]+", text, re.I)
    if m:
        amount = _parse_amount_idr(m.group(0))
        if amount is not None:
            out.append({"currency": "IDR", "amount": amount, "period": "one_time", "category": "one_time"})

    # dedupe
    seen = set()
    deduped = []
    for p in out:
        k = (p["amount"], p.get("period"))
        if k in seen:
            continue
        seen.add(k)
        deduped.append(p)

    return deduped


def choose_primary_price(prices: list[dict], source_url: str) -> dict | None:
    if not prices:
        return None
    return prices[0]


def extract_price_categories(soup: BeautifulSoup) -> list[str]:
    # Propertia doesn't have BHI's side-info categories.
    return []


def extract_images(soup: BeautifulSoup) -> list[str]:
    """
    Propertia: images appear as multiple <a> Image: PPV... entries / gallery.
    Safer approach:
      - collect from <img src> and <a href> that point to wp-content/uploads
      - dedupe
    """
    urls: list[str] = []

    # from img tags
    for img in soup.select("img[src], img[data-src]"):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src:
            continue
        if "wp-content/uploads" not in src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        urls.append(src)

    # from anchors (full-size images)
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        if "wp-content/uploads" not in href:
            continue
        if not re.search(r"\.(jpg|jpeg|png|webp)(\?.*)?$", href, re.I):
            continue
        urls.append(href)

    return _dedupe_preserve_order(urls)


def choose_primary_category(source_url: str) -> str:
    # keep same behavior; Propertia doesn’t use it much
    return "freehold"


def extract_section_by_category(soup: BeautifulSoup, section_prefix: str) -> dict[str, dict[str, str]]:
    # Propertia doesn't have BHI tables by category.
    return {}


def pick_category_dict(all_by_cat: dict[str, dict[str, str]], preferred: str) -> tuple[str | None, dict[str, str]]:
    return None, {}


def parse_side_location(soup: BeautifulSoup) -> dict | None:
    # We can later parse location from breadcrumb/taxonomy.
    return None


# =========================================================
# !!! DO NOT CHANGE THIS STRUCTURE (per your requirement) !!!
# =========================================================

def parse_detail_page(item: Dict[str, Any]) -> Dict[str, Any]:
    url = item["url"]

    r = requests.get(url, timeout=30)
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
