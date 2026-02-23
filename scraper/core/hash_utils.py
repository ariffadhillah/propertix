from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

# Field-field yang JANGAN ikut hashing (karena berubah tiap run / noisy)
NON_HASH_KEYS = {
    "raw",
    "reso",
    "content_hash",
    "first_seen_at",
    "last_seen_at",
    "scrape_run_id",
    "scraped_at",
}

_WS_RE = re.compile(r"\s+")


def _norm_str(s: Any) -> Optional[str]:
    if s is None:
        return None
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    if not s:
        return None
    # rapikan whitespace biar stabil
    s = _WS_RE.sub(" ", s)
    return s


def _round_float(x: Any, ndigits: int = 6) -> Optional[float]:
    try:
        if x is None:
            return None
        return round(float(x), ndigits)
    except Exception:
        return None


def _uniq_sorted_str_list(xs: Any) -> List[str]:
    if not xs or not isinstance(xs, list):
        return []
    out = []
    seen = set()
    for v in xs:
        s = _norm_str(v)
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    out.sort()
    return out


def _normalize_prices(prices: Any) -> List[Dict[str, Any]]:
    """
    prices internal: [{currency, amount, period}, ...]
    buat stabil: normalisasi + sort
    """
    if not prices or not isinstance(prices, list):
        return []

    out: List[Dict[str, Any]] = []
    for p in prices:
        if not isinstance(p, dict):
            continue
        currency = _norm_str(p.get("currency")) or None
        period = _norm_str(p.get("period")) or None
        amount = _round_float(p.get("amount"), 2)
        if amount is None:
            continue
        out.append({"currency": currency, "amount": amount, "period": period})

    out.sort(key=lambda d: (d.get("period") or "", d.get("currency") or "", d.get("amount") or 0))
    return out


def canonical_for_hash(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ambil subset field yang dianggap 'meaningful change' untuk incremental.
    Ini yang dipakai buat compute_content_hash.
    """

    loc = listing.get("location") or {}
    if not isinstance(loc, dict):
        loc = {}

    primary_price = listing.get("price") or {}
    if not isinstance(primary_price, dict):
        primary_price = {}

    canonical = {
        # identity-ish
        "source": _norm_str(listing.get("source")),
        "source_listing_id": _norm_str(listing.get("source_listing_id")),
        "source_url": _norm_str(listing.get("source_url")),

        # classification
        "intent": _norm_str(listing.get("intent")),
        "property_type": _norm_str(listing.get("property_type")),
        "tenure": _norm_str(listing.get("tenure")),
        "rent_period": _norm_str(listing.get("rent_period")),

        # text
        "title": _norm_str(listing.get("title")),
        "description": _norm_str(listing.get("description")),

        # sizes
        "land_size_sqm": _round_float(listing.get("land_size_sqm"), 3),
        "building_size_sqm": _round_float(listing.get("building_size_sqm"), 3),

        # rooms
        "bedrooms": _round_float(listing.get("bedrooms"), 1),
        "bathrooms": _round_float(listing.get("bathrooms"), 1),

        # geo
        "location": {
            "area": _norm_str(loc.get("area")),
            "sub_area": _norm_str(loc.get("sub_area")),
            "latitude": _round_float(loc.get("latitude"), 7),
            "longitude": _round_float(loc.get("longitude"), 7),
        },

        # pricing
        "price": {
            "currency": _norm_str(primary_price.get("currency")),
            "amount": _round_float(primary_price.get("amount"), 2),
            "period": _norm_str(primary_price.get("period")),
        },
        "prices": _normalize_prices(listing.get("prices")),

        # media
        "images": _uniq_sorted_str_list(listing.get("images")),
    }

    # drop None recursively biar payload ringkas dan stabil
    return _drop_nones(canonical)


def _drop_nones(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            v2 = _drop_nones(v)
            if v2 is None:
                continue
            # skip dict kosong
            if isinstance(v2, dict) and not v2:
                continue
            # skip list kosong
            if isinstance(v2, list) and not v2:
                continue
            out[k] = v2
        return out
    if isinstance(obj, list):
        out = []
        for v in obj:
            v2 = _drop_nones(v)
            if v2 is None:
                continue
            out.append(v2)
        return out
    return obj


def compute_content_hash(listing: Dict[str, Any]) -> str:
    payload = canonical_for_hash(listing)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()