from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
import re
import requests
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup


AJAX_ENDPOINT = "https://propertia.com/wp-admin/admin-ajax.php"


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Connection": "keep-alive",
        "Referer": "https://propertia.com/",
    })
    return s


def _update_query(url: str, updates: Dict[str, str]) -> str:
    u = urlsplit(url)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    q.update({k: str(v) for k, v in updates.items()})
    new_q = urlencode(q, doseq=True)
    return urlunsplit((u.scheme, u.netloc, u.path, new_q, ""))


def _parse_price_idr(raw: str) -> Optional[float]:
    if not raw:
        return None
    s = raw.strip()
    # contoh " IDR4.850.000.000"
    s = s.replace("IDR", "").strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _extract_area_from_address_html(address_html: str) -> Optional[str]:
    if not address_html:
        return None
    # address field berisi HTML kecil
    soup = BeautifulSoup(address_html, "lxml")
    txt = soup.get_text(" ", strip=True)
    # contoh: "Canggu"
    return txt or None


def _detect_intent_and_tenure(property_type: str) -> Tuple[str, str]:
    """
    property_type contoh: "Leasehold Villa", "Freehold Villa"
    """
    pt = (property_type or "").lower()

    # propertia list ini umumnya sale; kalau nanti ada rent, bisa kamu extend
    intent = "sale"

    tenure = "unknown"
    if "leasehold" in pt:
        tenure = "leasehold"
    elif "freehold" in pt:
        tenure = "freehold"

    return intent, tenure


def _extract_bedrooms_from_meta_html(meta_html: str) -> Optional[float]:
    """
    meta berisi HTML, contoh ada icon bed + angka.
    """
    if not meta_html:
        return None
    soup = BeautifulSoup(meta_html, "lxml")
    txt = soup.get_text(" ", strip=True)
    # ambil angka pertama sebagai bedrooms (heuristic)
    m = re.search(r"\b(\d+)\b", txt)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def parse_list_page(
    url: str,
    timeout: int = 30,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    """
    url: endpoint admin-ajax.php?... (seperti yang kamu paste)
    return list preview items, mengikuti struktur BHI list_items.py
    """
    sess = session or _make_session()

    r = sess.get(url, timeout=timeout)
    r.raise_for_status()

    # kadang response bisa string JSON, kadang sudah JSON
    try:
        data = r.json()
    except Exception:
        data = json.loads(r.text)

    props = data.get("properties") or []
    items: List[Dict[str, Any]] = []

    for p in props:
        href = (p.get("url") or "").strip()
        if not href:
            continue

        listing_id = p.get("property_id")
        if listing_id is None:
            continue
        listing_id = str(listing_id).strip()

        title = (p.get("title") or "").strip() or None
        thumb = (p.get("thumbnail") or "").strip() or None

        intent, tenure = _detect_intent_and_tenure(p.get("property_type") or "")

        price = _parse_price_idr(p.get("price") or "")
        price_category = tenure if tenure != "unknown" else None

        lat = None
        lon = None
        try:
            lat = float(p.get("latitude")) if p.get("latitude") not in (None, "") else None
        except Exception:
            pass
        try:
            lon = float(p.get("longitude")) if p.get("longitude") not in (None, "") else None
        except Exception:
            pass

        area = _extract_area_from_address_html(p.get("address") or "")
        bedrooms = _extract_bedrooms_from_meta_html(p.get("meta") or "")

        items.append({
            "source": "propertia",
            "source_key": "propertia",
            "source_listing_id": listing_id,
            "listing_key": f"propertia:{listing_id}",

            "url": href,
            "title": title,
            "thumb": thumb,

            "intent_preview": intent,
            "tenure_preview": tenure,
            "status_preview": "",

            "price_preview": price,
            "price_category_preview": price_category,

            "bedrooms_preview": bedrooms,

            "location_preview": {
                "area": area,
                "sub_area": "",
                "latitude": lat,
                "longitude": lon,
            },

            "raw_preview": {
                "info_box": "",
            }
        })

    return items