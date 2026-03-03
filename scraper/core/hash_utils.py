# scraper/core/hash_utils.py
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


# ============================================================
# BASIC HASH HELPERS
# ============================================================

def _stable_json(obj: Any) -> str:
    # Deterministic JSON serialization
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def stable_hash(obj: Any) -> str:
    return sha256_str(_stable_json(obj))


# ============================================================
# CLEANING / NORMALIZATION
# ============================================================

def _drop_nulls(obj: Any) -> Any:
    """
    Remove null/empty recursively.
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


# ============================================================
# LISTING KEY
# ============================================================

def _get_listing_key(listing: Dict[str, Any]) -> Optional[str]:
    lk = listing.get("ListingKey") or listing.get("listing_key")
    if isinstance(lk, str) and lk.strip():
        return lk.strip()

    source = (listing.get("source") or "").strip()
    sid = (listing.get("source_listing_id") or "").strip()

    if source and sid:
        return f"{source}:{sid}"

    url = (listing.get("source_url") or "").strip()
    if url:
        return sha256_str(url)

    return None


# ============================================================
# CANONICAL HASH INPUT
# ============================================================

def _normalize_images(images_in: Any) -> List[str]:
    if not isinstance(images_in, list):
        return []
    out: List[str] = []
    for u in images_in:
        if isinstance(u, str) and u.strip():
            out.append(u.strip())
    return sorted(set(out))


def _normalize_prices(prices_in: Any) -> List[Dict[str, Any]]:
    """
    Normalize multi-price list deterministically.
    Each item -> {"amount": float, "currency": str, "period": str}
    Sorted by (currency, period, amount) for stable ordering.
    """
    if not isinstance(prices_in, list):
        return []

    out: List[Dict[str, Any]] = []
    for p in prices_in:
        if not isinstance(p, dict):
            continue

        amount = _to_float(p.get("amount"))
        currency = p.get("currency")
        period = p.get("period")

        item = {
            "amount": amount,
            "currency": currency,
            "period": period,
        }
        item = _drop_nulls(item) or {}
        if not item:
            continue
        out.append(item)

    def _sort_key(x: Dict[str, Any]):
        return (
            str(x.get("currency") or ""),
            str(x.get("period") or ""),
            float(x.get("amount")) if x.get("amount") is not None else -1.0,
        )

    out = sorted(out, key=_sort_key)
    return out


def build_canonical_hash_input(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical object used for content hashing.

    Supports two shapes:
    1) Flat listing: bedrooms/latitude/longitude/etc at top level
    2) Nested: specs/location/price/prices already present

    Canonical fields (v1):
      ListingKey, title, description,
      price{amount,currency,period},
      prices[{amount,currency,period}],
      specs{bedrooms,bathrooms,land_size_sqm,building_size_sqm},
      location{area,sub_area,lat,lng},
      images[]
    """
    lk = _get_listing_key(listing) or listing.get("ListingKey")

    title = listing.get("title")
    description = listing.get("description")

    # ---------------- price (primary)
    price_in = listing.get("price") or {}
    if not isinstance(price_in, dict):
        price_in = {}
    price_obj = {
        "amount": _to_float(price_in.get("amount", listing.get("price_amount"))),
        "currency": price_in.get("currency", listing.get("price_currency")),
        "period": price_in.get("period", listing.get("price_period")),
    }

    # ---------------- prices (multi)
    prices_in = listing.get("prices")
    prices_obj = _normalize_prices(prices_in)

    # ---------------- specs
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

    # ---------------- location
    loc_in = listing.get("location") or {}
    if not isinstance(loc_in, dict):
        loc_in = {}

    area = loc_in.get("area", listing.get("area"))
    sub_area = loc_in.get("sub_area", listing.get("sub_area"))

    lat = loc_in.get("lat", loc_in.get("latitude", listing.get("latitude")))
    lng = loc_in.get("lng", loc_in.get("longitude", listing.get("longitude")))

    location_obj = {
        "area": area,
        "sub_area": sub_area,
        "lat": _to_float(lat),
        "lng": _to_float(lng),
    }

    # ---------------- images
    images = _normalize_images(listing.get("images"))

    canonical_obj: Dict[str, Any] = {
        "ListingKey": lk,
        "title": title,
        "description": description,
        "price": price_obj,
        "prices": prices_obj,
        "specs": specs_obj,
        "location": location_obj,
        "images": images,
    }

    cleaned = _drop_nulls(canonical_obj) or {}
    return cleaned


# ============================================================
# HASH COMPUTATION
# ============================================================

def compute_canonical_content_hash(listing_or_canonical: Dict[str, Any]) -> str:
    """
    Accepts either:
    - listing dict (flat/nested)
    - canonical hash input dict (already in canonical shape)
    We canonicalize again to be safe/deterministic.
    """
    cleaned = build_canonical_hash_input(listing_or_canonical)
    payload = _stable_json(cleaned)
    return sha256_str(payload)


def compute_content_hash(listing: Dict[str, Any]) -> str:
    # Backward-compatible alias
    return compute_canonical_content_hash(listing)


def compute_raw_payload_hash(raw_payload: Any) -> str:
    payload = _stable_json(raw_payload or {})
    return sha256_str(payload)


def compute_media_hash(images: List[str]) -> str:
    clean = _normalize_images(images)
    return stable_hash(clean)