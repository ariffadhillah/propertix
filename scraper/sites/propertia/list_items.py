from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlsplit, urlunsplit


def _strip_query(url: str) -> str:
    if not url:
        return url
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc, u.path, "", ""))


def _clean_amount_idr(raw: str) -> Optional[float]:
    """
    Convert strings like:
      "IDR14.300.000.000" -> 14300000000.0
      " IDR5.380.000.000" -> 5380000000.0
    """
    if not raw:
        return None
    s = raw.strip()
    s = s.replace("IDR", "").replace("Rp", "").strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _infer_intent(status_text: str) -> str:
    t = (status_text or "").lower()
    # Propertia label contoh: "For sale land"
    if "for sale" in t or "sale" in t:
        return "sale"
    if "rent" in t or "for rent" in t:
        return "rent"
    return "other"


def _infer_tenure_and_category(property_type: str) -> Tuple[str, str]:
    """
    From text like:
      "Freehold Land" -> tenure=freehold, price_category=freehold
      "Leasehold Villa" -> tenure=leasehold, price_category=leasehold
    """
    t = (property_type or "").lower()
    if "freehold" in t:
        return "freehold", "freehold"
    if "leasehold" in t:
        return "leasehold", "leasehold"
    return "unknown", "unknown"


def _get_first_img(card: BeautifulSoup) -> Optional[str]:
    img = card.select_one(".listing-image-wrap img")
    if not img:
        return None
    src = (img.get("src") or img.get("data-src") or "").strip()
    if not src:
        return None
    if src.startswith("data:image"):
        src = (img.get("data-src") or "").strip()
    return src or None


def _extract_bedrooms(card: BeautifulSoup) -> Optional[float]:
    """
    Extract bedrooms from Houzez Propertia card.
    Target:
        <li class="h-beds"> ... <span class="hz-figure">1</span>
    """
    bed_tag = card.select_one("li.h-beds span.hz-figure")
    if bed_tag:
        txt = bed_tag.get_text(strip=True)
        if txt.isdigit():
            return float(txt)
        m = re.search(r"(\d+)", txt)
        if m:
            return float(m.group(1))

    bed_tag = card.select_one("li.h-bedrooms span.hz-figure")
    if bed_tag:
        txt = bed_tag.get_text(strip=True)
        m = re.search(r"(\d+)", txt)
        if m:
            return float(m.group(1))

    return None


def _extract_area_and_subarea(addr_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    address contoh: "Umalas - Bumbak"
    area=Umalas, sub_area=Bumbak
    """
    if not addr_text:
        return None, None
    parts = [p.strip() for p in addr_text.split("-") if p.strip()]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " - ".join(parts[1:])


def _infer_status_preview(card: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (status_preview, status_text_raw)

    status_preview (BHI-like enum):
      - "off_plan" jika ada label OFF PLAN
      - "sold" jika ada label SOLD
      - None untuk listing aktif normal / NEW LISTING / dll

    status_text_raw:
      - teks mentah dari label-status (mis "For sale villa")
    """
    status_label = card.select_one(".labels-wrap a.label-status")
    status_text = status_label.get_text(" ", strip=True) if status_label else ""
    status_text = status_text.strip() or None

    # badge tambahan: NEW LISTING, OFF PLAN, SOLD, dll
    badges = [
        (a.get_text(" ", strip=True) or "").strip().lower()
        for a in card.select(".labels-wrap a.hz-label, .labels-wrap a.label")
    ]

    status_preview = None
    if any("off plan" in b for b in badges):
        status_preview = "off_plan"
    elif any(b == "sold" or "sold" in b for b in badges):
        status_preview = "sold"

    return status_preview, status_text


def parse_list_page(url: str, timeout: int = 30) -> List[Dict[str, Any]]:
    r = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        },
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items: List[Dict[str, Any]] = []

    for card in soup.select("div.item-listing-wrap[data-hz-id]"):
        # ambil ID properti asli dari <span class="hz-figure">
        id_tag = card.select_one("li.h-property-id span.hz-figure")
        if not id_tag:
            continue

        listing_id = id_tag.get_text(strip=True)
        if not listing_id:
            continue

        # detail url + title
        a = card.select_one("h2.item-title a")
        if not a:
            a = card.select_one(".listing-image-wrap a.hover-effect")

        href = (a.get("href") if a else "") or ""
        href = href.strip()
        if not href:
            continue
        href = _strip_query(href)

        title = (a.get_text(" ", strip=True) if a else "") or ""
        title = title.strip() or None

        # thumbnail
        thumb = _get_first_img(card)

        # ✅ status enum + raw status text
        status_preview, status_text = _infer_status_preview(card)

        # intent dari status_text ("For sale villa", dll)
        intent = _infer_intent(status_text or "")

        # property type (Freehold Land / Leasehold Villa / etc)
        type_el = card.select_one("ul.item-amenities li.h-type span")
        property_type = type_el.get_text(" ", strip=True) if type_el else ""
        tenure, price_category = _infer_tenure_and_category(property_type)

        # price
        price_el = card.select_one("ul.item-amenities li.item-price span.price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        price = _clean_amount_idr(price_text)

        # bedrooms
        bedrooms = _extract_bedrooms(card)

        # location from address tag
        addr_el = card.select_one("address.item-address span")
        addr_text = addr_el.get_text(" ", strip=True) if addr_el else ""
        area, sub_area = _extract_area_and_subarea(addr_text)

        items.append(
            {
                "source": "propertia",
                "source_key": "propertia",
                "source_listing_id": str(listing_id),
                "listing_key": f"propertia:{listing_id}",
                "url": href,
                "title": title,
                "thumb": thumb,
                "intent_preview": intent,
                "tenure_preview": tenure,

                # ✅ BHI-like: status enum kecil
                "status_preview": status_preview,

                "price_preview": price,
                "price_category_preview": price_category,
                "bedrooms_preview": bedrooms,
                "location_preview": {
                    "area": area,
                    "sub_area": sub_area,
                    "latitude": None,
                    "longitude": None,
                },
                "raw_preview": {
                    "info_box": None,
                    # ✅ simpan mentahnya di raw (biar bisa debug)
                    "status_text": status_text,
                },
            }
        )

    return items