from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(obj: Any) -> str:
    s = _stable_json(obj)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _drop_nulls(obj: Any) -> Any:
    """
    Remove null/empty recursively, deterministic.
    Drop:
      - None
      - "" (after strip)
      - [] / {}
    Keep:
      - 0
      - False
    """
    if obj is None:
        return None

    if isinstance(obj, str):
        s = obj.strip()
        return s if s != "" else None

    if isinstance(obj, list):
        cleaned = []
        for x in obj:
            cx = _drop_nulls(x)
            if cx is None or cx == [] or cx == {}:
                continue
            cleaned.append(cx)
        return cleaned if cleaned else None

    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            cv = _drop_nulls(v)
            if cv is None or cv == [] or cv == {}:
                continue
            out[k] = cv
        return out if out else None

    return obj


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(float(x))
    except Exception:
        return None


def compute_media_hash(images: List[str]) -> str:
    """
    Internal: stable hash of image URLs only (sorted, de-duped).
    """
    clean: List[str] = []
    for u in images or []:
        if not u:
            continue
        u = str(u).strip()
        if u:
            clean.append(u)
    clean = sorted(set(clean))
    return stable_hash(clean)


def _get_listing_key(listing: Dict[str, Any]) -> Optional[str]:
    lk = listing.get("listing_key") or listing.get("ListingKey")
    if isinstance(lk, str) and lk.strip():
        return lk.strip()

    source = (listing.get("source") or "").strip()
    sid = (listing.get("source_listing_id") or listing.get("listing_id") or "").strip()
    if source and sid:
        return f"{source}:{sid}"

    url = (listing.get("source_url") or listing.get("url") or "").strip()
    if url:
        if source:
            return f"{source}:{sha256_str(url)}"
        return sha256_str(url)

    return None


def build_canonical_hash_input(listing: Dict[str, Any]) -> Dict[str, Any]:
    lk = _get_listing_key(listing)

    title = listing.get("title")
    description = listing.get("description")

    price_in = listing.get("price") or {}
    if not isinstance(price_in, dict):
        price_in = {}
    price_obj = {
        "amount": _to_float(price_in.get("amount")),
        "currency": price_in.get("currency"),
        "period": price_in.get("period"),
    }

    specs_in = listing.get("specs") or {}
    if not isinstance(specs_in, dict):
        specs_in = {}

    bedrooms = specs_in.get("bedrooms", listing.get("bedrooms"))
    bathrooms = specs_in.get("bathrooms", listing.get("bathrooms"))
    land_size_sqm = specs_in.get("land_size_sqm", listing.get("land_size_sqm"))
    building_size_sqm = specs_in.get("building_size_sqm", listing.get("building_size_sqm"))

    specs_obj = {
        "bedrooms": _to_int(bedrooms),
        "bathrooms": _to_int(bathrooms),
        "land_size_sqm": _to_float(land_size_sqm),
        "building_size_sqm": _to_float(building_size_sqm),
    }

    loc_in = listing.get("location") or {}
    if not isinstance(loc_in, dict):
        loc_in = {}

    lat = loc_in.get("lat")
    lng = loc_in.get("lng")
    if lat is None:
        lat = loc_in.get("latitude")
    if lng is None:
        lng = loc_in.get("longitude")

    area = loc_in.get("area")
    if area is None:
        area = listing.get("area") or listing.get("sub_area")

    location_obj = {
        "area": area,
        "lat": _to_float(lat),
        "lng": _to_float(lng),
    }

    images_in = listing.get("images") or []
    if not isinstance(images_in, list):
        images_in = []
    images: List[str] = []
    for u in images_in:
        if isinstance(u, str) and u.strip():
            images.append(u.strip())
    images = sorted(set(images))

    canonical_obj: Dict[str, Any] = {
        "ListingKey": lk,
        "title": title,
        "description": description,
        "price": price_obj,
        "specs": specs_obj,
        "location": location_obj,
        "images": images,
    }

    cleaned = _drop_nulls(canonical_obj) or {}
    return cleaned

def compute_canonical_content_hash(listing: Dict[str, Any]) -> str:
    cleaned = build_canonical_hash_input(listing)
    payload = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_str(payload)

def compute_content_hash(listing: Dict[str, Any]) -> str:
    """
    Backward-compatible alias:
    content_hash is aligned to client canonical spec for deterministic ingestion.
    """
    return compute_canonical_content_hash(listing)

def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def compute_raw_payload_hash(raw_payload: Any) -> str:
    """
    Hash untuk 'raw.payload' supaya bisa deteksi perubahan raw HTML/JSON juga.
    Harus deterministic: sort_keys + compact.
    """
    payload = _stable_json(raw_payload or {})
    return sha256_str(payload)