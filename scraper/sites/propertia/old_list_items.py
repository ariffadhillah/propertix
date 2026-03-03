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

    # 1️⃣ Target langsung ke hz-figure di h-beds
    bed_tag = card.select_one("li.h-beds span.hz-figure")
    if bed_tag:
        txt = bed_tag.get_text(strip=True)
        if txt.isdigit():
            return float(txt)

        # kalau misal ada format aneh
        m = re.search(r"(\d+)", txt)
        if m:
            return float(m.group(1))

    # 2️⃣ Fallback kalau class beda (future-proof)
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

    # card utama: div.item-listing-wrap[data-hz-id]
    for card in soup.select("div.item-listing-wrap[data-hz-id]"):
        # hz_id = (card.get("data-hz-id") or "").strip()
        # if not hz_id:
        #     continue

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
            # fallback: link di gambar
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

        # status label: "For sale land" dll
        status_label = card.select_one(".labels-wrap a.label-status")
        status_text = status_label.get_text(" ", strip=True) if status_label else ""
        intent = _infer_intent(status_text)

        # property type (Freehold Land / Leasehold Villa / etc)
        type_el = card.select_one("ul.item-amenities li.h-type span")
        property_type = type_el.get_text(" ", strip=True) if type_el else ""
        tenure, price_category = _infer_tenure_and_category(property_type)

        # price
        price_el = card.select_one("ul.item-amenities li.item-price span.price")
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        price = _clean_amount_idr(price_text)
        # print(price)
        

        # bedrooms
        bedrooms = _extract_bedrooms(card)

        # location from address tag
        addr_el = card.select_one("address.item-address span")
        addr_text = addr_el.get_text(" ", strip=True) if addr_el else ""
        area, sub_area = _extract_area_and_subarea(addr_text)

        # listing id alternatif yang kadang ada: "ID: PPL3095"
        # kita simpan di raw_preview saja, tapi source_listing_id tetap hz_id (post id) agar konsisten.
        pid_el = card.select_one("li.h-property-id span.hz-figure")
        human_listing_id = pid_el.get_text(" ", strip=True) if pid_el else None

        # Susun preview dict dengan struktur SAMA seperti BHI
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
                "status_preview": (status_text or None),
                "price_preview": price,
                "price_category_preview": price_category,
                "bedrooms_preview": bedrooms,
                "location_preview": {
                    "area": area,
                    "sub_area": sub_area,
                    "latitude": None,   # (list html biasanya tidak ada; bisa diisi nanti dari detail)
                    "longitude": None,
                },
                "raw_preview": {
                    "info_box": None,
                }
            }
        )

    return items


    #     items.append({
    #         "source": "bali-home-immo",
    #         "source_key": "bali-home-immo",
    #         "source_listing_id": listing_id,
    #         "listing_key": f"bali-home-immo:{listing_id}",

    #         "url": href,
    #         "title": title,
    #         "thumb": thumb,

    #         "intent_preview": intent,
    #         "tenure_preview": tenure,
    #         "status_preview": status_preview,

    #         "price_preview": price,
    #         "price_category_preview": price_category,

    #         "bedrooms_preview": bedrooms,

    #         "location_preview": {
    #             "area": area,
    #             "sub_area": sub_area,
    #             "latitude": lat,
    #             "longitude": lon,
    #         },

    #         "raw_preview": {
    #             "info_box": info,
    #         }
    #     })

    # return items