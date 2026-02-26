from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlsplit, urlunsplit


def _detect_intent_and_tenure(url: str) -> Tuple[str, Optional[str]]:

    u = url.lower()

    if "/for-sale" in u:
        intent_preview = "sale"
    elif "/for-rent" in u or "/rent" in u:
        intent_preview = "rent"
    else:
        intent_preview = "other"

    if "leasehold" in u:
        tenure_preview = "leasehold"
    elif "freehold" in u:
        tenure_preview = "freehold"
    else:
        tenure_preview = "unknown"

    return intent_preview, tenure_preview


def _strip_query(url: str) -> str:
    if not url:
        return url
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc, u.path, "", ""))


def _clean_amount(raw: str) -> Optional[float]:
    if not raw:
        return None
    s = raw.strip()
    s = s.split("/")[0].strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except:
        return None


def _get_thumb_img(card: BeautifulSoup) -> Optional[str]:
    img = card.select_one("a.property-thumbnail-img-container img")
    if not img:
        return None
    src = img.get("src") or img.get("data-src")
    if not src:
        return None
    src = src.strip()
    if src.startswith("data:image"):
        src = (img.get("data-src") or "").strip()
    return src or None


def _extract_info_box(card: BeautifulSoup, listing_id: str) -> Dict[str, str]:
    out: Dict[str, str] = {}

    lid = listing_id.lower()
    info = card.select_one(f"div[id^='info-box-thumb-{lid}-']")
    if not info:
        return out

    for p in info.select("p"):
        sp = p.select_one("span")
        if not sp:
            continue
        key = sp.get_text(" ", strip=True).strip().lower()
        txt = p.get_text(" ", strip=True)
        val = txt.split(":", 1)[1].strip() if ":" in txt else ""
        if key and val:
            out[key] = val

    return out


def parse_list_page(url: str, timeout: int = 30) -> List[Dict[str, Any]]:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items: List[Dict[str, Any]] = []

    for card in soup.select("div.property-item div.blog[id]"):
        listing_id = (card.get("id") or "").strip()
        if not listing_id:
            continue

        a_detail = card.select_one("a.btn.btn-standard.property-special-btn")
        if not a_detail:
            a_detail = card.select_one("h3.home-property-headline")
            if a_detail:
                a_detail = a_detail.find_parent("a")

        href = (a_detail.get("href") if a_detail else "") or ""
        href = href.strip()
        if not href:
            continue
        href = _strip_query(href)

        intent, tenure = _detect_intent_and_tenure(href)

        title_el = card.select_one("h3.home-property-headline")
        title = title_el.get_text(" ", strip=True) if title_el else None

        thumb = _get_thumb_img(card)

        # status preview
        status_preview = None
        sold_badge = card.select_one("div.sold_item")
        if sold_badge:
            txt = sold_badge.get_text(" ", strip=True).lower()
            if "off-plan" in txt:
                status_preview = "off_plan"
            elif "sold" in txt:
                status_preview = "sold"

        # lat/lon
        lat = lon = None
        map_a = card.select_one("a.property-map-icon[data-latitude][data-longitude]")
        if map_a:
            try:
                lat = float(map_a.get("data-latitude"))
            except:
                pass
            try:
                lon = float(map_a.get("data-longitude"))
            except:
                pass

        # price
        price = None
        price_category = None
        li_price = card.select_one("li.trigger-tab-thumbnail[data-price][data-category]")
        if li_price:
            price = _clean_amount(li_price.get("data-price", ""))
            price_category = (li_price.get("data-category") or "").strip().lower() or None

        # bedrooms (lebih stabil)
        bedrooms = None
        bed_el = card.select_one(".grid-property span.property-block")
        if bed_el:
            m = re.search(r"(\d+)", bed_el.get_text(" ", strip=True))
            if m:
                bedrooms = float(m.group(1))

        info = _extract_info_box(card, listing_id)
        area = info.get("area")
        sub_area = info.get("sub area") or info.get("subarea")


        items.append({
            "source": "bali-home-immo",
            "source_key": "bali-home-immo",
            "source_listing_id": listing_id,
            "listing_key": f"bali-home-immo:{listing_id}",

            "url": href,
            "title": title,
            "thumb": thumb,

            "intent_preview": intent,
            "tenure_preview": tenure,
            "status_preview": status_preview,

            "price_preview": price,
            "price_category_preview": price_category,

            "bedrooms_preview": bedrooms,

            "location_preview": {
                "area": area,
                "sub_area": sub_area,
                "latitude": lat,
                "longitude": lon,
            },

            "raw_preview": {
                "info_box": info,
            }
        })

    return items