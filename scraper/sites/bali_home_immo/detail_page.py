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
from urllib.parse import urljoin
from urllib.parse import urlsplit
# image parsing helpers

BASE = "https://bali-home-immo.com"


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


def parse_footer_broker(soup: BeautifulSoup, page_url: str) -> dict:
    """
    Extract agency identity + contacts from footer.
    Returns:
      { agency_name, broker_email, broker_phone_raw, contact_links_raw }
    """
    footer = soup.select_one("footer") or soup.select_one("section.site-footer")
    if not footer:
        return {
            "agency_name": None,
            "broker_email": None,
            "broker_phone_raw": None,
            "contact_links_raw": {
                "mailto": [], "tel": [], "whatsapp": [], "messenger": [], "form": [], "other": []
            },
        }

    contact_links_raw = {
        "mailto": [], "tel": [], "whatsapp": [], "messenger": [], "form": [], "other": []
    }

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

    footer_email = extract_email_from_soup(footer)

    # prefer phone from whatsapp link
    footer_phone_raw = None
    for wa in contact_links_raw["whatsapp"]:
        m = re.search(r"(?:wa\.me/|phone=)(\+?\d{8,15})", wa)
        if m:
            footer_phone_raw = m.group(1)
            break
    if not footer_phone_raw:
        footer_phone_raw = extract_phone_from_soup(footer)

    # agency name heuristic: copyright
    agency_name = None
    text = footer.get_text(" ", strip=True)
    m = re.search(r"Copyright\s*©\s*\d{4}\.?\s*([A-Za-z0-9\s]+?)\s*All Rights Reserved", text, re.I)
    if m:
        agency_name = m.group(1).strip()

    # fallback: detect brand from social
    if not agency_name:
        if footer.select_one('a[href*="facebook.com/BaliHomeImmo"]') or "bali home immo" in text.lower():
            agency_name = "Bali Home Immo"

    # dedupe lists
    for k in contact_links_raw.keys():
        contact_links_raw[k] = _dedupe_preserve_order(contact_links_raw[k])

    return {
        "agency_name": agency_name,
        "broker_email": footer_email.lower() if footer_email else None,
        "broker_phone_raw": footer_phone_raw,
        "contact_links_raw": contact_links_raw,
    }



def normalize_phone_id(raw: str | None) -> str | None:
    """
    Normalize Indonesian phone numbers to E.164-like format.
    Examples:
      0812xxxx -> +62812xxxx
      62812xxxx -> +62812xxxx
      +62812xxxx -> +62812xxxx
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # keep leading +
    s = re.sub(r"[^\d+]", "", s)

    # remove multiple leading +
    if s.startswith("++"):
        s = "+" + s.lstrip("+")

    if s.startswith("+62"):
        digits = re.sub(r"[^\d]", "", s)
        return "+" + digits

    # if starts with 62 (no plus)
    if s.startswith("62"):
        digits = re.sub(r"[^\d]", "", s)
        return "+"+digits

    # if starts with 0 -> +62
    if s.startswith("0"):
        digits = re.sub(r"[^\d]", "", s)
        return "+62" + digits[1:]

    # fallback: if looks like ID mobile without 0/62
    digits = re.sub(r"[^\d]", "", s)
    if len(digits) >= 9:
        # assume already national significant number
        return "+62" + digits

    return None


def extract_email_from_soup(soup: BeautifulSoup) -> str | None:
    # mailto first
    a = soup.select_one('a[href^="mailto:"]')
    if a and a.get("href"):
        email = a["href"].split("mailto:", 1)[1].split("?", 1)[0].strip()
        return email.lower() if email else None

    # fallback regex in text
    text = soup.get_text(" ", strip=True)
    m = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, re.I)
    return m.group(1).lower() if m else None


def extract_phone_from_soup(soup: BeautifulSoup) -> str | None:
    # tel: first
    a = soup.select_one('a[href^="tel:"]')
    if a and a.get("href"):
        phone = a["href"].split("tel:", 1)[1].strip()
        return phone or None

    # whatsapp links sometimes contain phone
    wa = soup.select_one('a[href*="wa.me/"], a[href*="api.whatsapp.com"], a[href*="whatsapp"]')
    if wa and wa.get("href"):
        href = wa["href"]
        m = re.search(r"(?:wa\.me/|phone=)(\+?\d{8,15})", href)
        if m:
            return m.group(1)

    # fallback regex (rough)
    text = soup.get_text(" ", strip=True)
    m = re.search(r"(\+?62|0)\d[\d\-\s]{7,}\d", text)
    return m.group(0) if m else None

def parse_broker_block(soup: BeautifulSoup, page_url: str) -> dict:
    """
    Heuristic extraction for BHI contact/agent block + footer fallback.

    Returns:
      {
        broker_name, broker_phone_raw, broker_phone, broker_email,
        broker_profile_url, agency_name, contact_links_raw
      }
    """
    # likely contact containers
    containers = []
    containers += soup.select(".btn-contact__container")
    containers += soup.select("[class*='contact']")
    containers += soup.select("[id*='contact']")
    containers = containers or [soup]  # fallback full doc

    broker_name = None
    agency_name = None
    broker_profile_url = None

    broker_email = None
    broker_phone_raw = None

    contact_links_raw = {
        "mailto": [],
        "tel": [],
        "whatsapp": [],
        "messenger": [],
        "form": [],
        "other": [],
    }

    # pick best container by link signals
    best = None
    best_score = -1
    for c in containers:
        score = 0
        if c.select_one('a[href^="mailto:"]'):
            score += 2
        if c.select_one('a[href^="tel:"]'):
            score += 2
        if c.select_one('a[href*="wa.me/"], a[href*="api.whatsapp.com"], a[href*="whatsapp"]'):
            score += 2
        if c.select_one('a[href*="m.me/"], a[href*="facebook.com/messages"], a[href*="messenger.com"]'):
            score += 2
        if c.select_one("button[data-url]"):
            score += 1
        if score > best_score:
            best_score = score
            best = c

    node = best or soup

    # links (a[href])
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

    # contact form URL is in modal button[data-url]
    for btn in node.select("button[data-url]"):
        u = (btn.get("data-url") or "").strip()
        if not u:
            continue
        contact_links_raw["form"].append(urljoin(page_url, u))

    # extract email + phone from node then fallback document
    broker_email = extract_email_from_soup(node) or extract_email_from_soup(soup)
    broker_phone_raw = extract_phone_from_soup(node) or extract_phone_from_soup(soup)

    # name heuristics (BHI usually doesn't have person name)
    for sel in ["h3", "h4", "h5", ".agent-name", ".contact-name", "strong"]:
        el = node.select_one(sel)
        if el:
            t = el.get_text(" ", strip=True)
            if t and len(t) <= 80 and "contact" not in t.lower() and "email" not in t.lower():
                broker_name = t
                break

    # profile URL heuristics (rare on BHI)
    for a in node.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        low = href.lower()
        if "agent" in low or "broker" in low:
            broker_profile_url = urljoin(page_url, href)
            break

    # agency name heuristics from image alt/title (rare)
    img = node.select_one("img[alt], img[title]")
    if img:
        alt = (img.get("alt") or img.get("title") or "").strip()
        if alt and len(alt) <= 80:
            agency_name = alt

    # --- footer fallback / augmentation
    footer = parse_footer_broker(soup, page_url)

    if not agency_name and footer.get("agency_name"):
        agency_name = footer["agency_name"]
    if not broker_email and footer.get("broker_email"):
        broker_email = footer["broker_email"]
    if not broker_phone_raw and footer.get("broker_phone_raw"):
        broker_phone_raw = footer["broker_phone_raw"]

    # merge contact links
    footer_links = footer.get("contact_links_raw") or {}
    for k in ["mailto", "tel", "whatsapp", "messenger", "form", "other"]:
        contact_links_raw[k].extend(footer_links.get(k, []))

    # dedupe everything for stability
    for k in contact_links_raw.keys():
        contact_links_raw[k] = _dedupe_preserve_order(contact_links_raw[k])

    # hard default for BHI (last resort)
    if not agency_name:
        agency_name = "Bali Home Immo"

    # normalize phone (after footer fallback)
    broker_phone = normalize_phone_id(broker_phone_raw)

    return {
        "broker_name": broker_name,
        "broker_phone_raw": broker_phone_raw,
        "broker_phone": broker_phone,
        "broker_email": broker_email.lower() if broker_email else None,
        "broker_profile_url": broker_profile_url,
        "agency_name": agency_name,
        "contact_links_raw": contact_links_raw,
    }


def extract_price_categories(soup: BeautifulSoup) -> list[str]:
    """
    Read available price categories from the side-info buttons:
    freehold, leasehold, yearly, monthly (sometimes only one exists).
    """
    cats: list[str] = []
    for sp in soup.select("div.side-info span[data-price-category]"):
        c = (sp.get("data-price-category") or "").strip().lower()
        if not c:
            continue
        cats.append(c)

    # dedupe preserve order
    seen = set()
    out: list[str] = []
    for c in cats:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def infer_client_taxonomy(taxonomy_from_url: dict, price_categories: list[str]) -> dict:
    """
    Decide offer_category / tenure_type / rent_period using strongest signals.
    Priority:
      1) price_categories (side-info)  -> strongest
      2) URL taxonomy (fallback)
    """
    # default from URL
    offer = coerce_offer_category(taxonomy_from_url.get("intent"))
    tenure = coerce_tenure_type(taxonomy_from_url.get("tenure"))
    rent_period = coerce_rent_period(taxonomy_from_url.get("rent_period"))

    cats = set(price_categories or [])

    # if any rent categories exist -> offer_category rent
    if "yearly" in cats or "monthly" in cats:
        offer = "rent"

    # if any sale categories exist -> offer_category sale
    if "freehold" in cats or "leasehold" in cats:
        offer = "sale" if offer != "rent" else offer  # keep rent if mixed; we still store prices[] anyway

    # tenure only meaningful from freehold/leasehold categories
    if "freehold" in cats:
        tenure = "freehold"
    elif "leasehold" in cats:
        tenure = "leasehold"

    # rent_period from monthly/yearly categories
    if "monthly" in cats:
        rent_period = "month"
    elif "yearly" in cats:
        rent_period = "year"

    return {
        "offer_category": offer,
        "tenure_type": tenure,
        "rent_period": rent_period,
    }

def extract_breadcrumb_texts(soup: BeautifulSoup) -> list[str]:
    items = []
    for li in soup.select("ol.breadcrumb li.breadcrumb-item"):
        t = li.get_text(" ", strip=True)
        if t:
            items.append(t)
    return items



def parse_side_location(soup: BeautifulSoup) -> dict | None:
    """
    Extract location from <div class="side-location">:
      area from <span> (upper text)
      sub_area from remaining text
    """
    box = soup.select_one("div.side-location div.ml-10")
    if not box:
        return None

    span = box.select_one("span")
    area = span.get_text(strip=True) if span else None

    # Get text content without the span text
    full_text = box.get_text(" ", strip=True)  # ex: "Pererenan North Side"
    sub_area = None
    if area:
        # remove leading area from full_text
        sub_area = full_text.replace(area, "", 1).strip()
        if not sub_area:
            sub_area = None

    # Normalize whitespace
    def norm(x: str | None) -> str | None:
        if not x:
            return None
        x = re.sub(r"\s+", " ", x).strip()
        return x or None

    return {
        "area": norm(area),
        "sub_area": norm(sub_area),
    }



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

        # rent period mapping (enum client)
        if token in ("daily", "nightly"):
            out["rent_period"] = "night"
        elif token in ("weekly", "week"):
            out["rent_period"] = "week"
        elif token in ("monthly", "month"):
            out["rent_period"] = "month"
        elif token in ("yearly", "annual", "year"):
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

    # # rent page → prefer yearly, then monthly
    # if "/rent/" in url:
    #     return find_cat("yearly") or find_cat("monthly") or prices[0]
    
    # rent page → prefer yearly, then monthly
    if "/for-rent/" in url or "/rent/" in url:
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
