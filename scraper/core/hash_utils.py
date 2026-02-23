# from __future__ import annotations

# import hashlib
# import json
# import re
# from typing import Any, Dict, List, Optional, Tuple

# # Field-field yang JANGAN ikut hashing (karena berubah tiap run / noisy)
# NON_HASH_KEYS = {
#     "raw",
#     "reso",
#     "content_hash",
#     "first_seen_at",
#     "last_seen_at",
#     "scrape_run_id",
#     "scraped_at",
# }

# _WS_RE = re.compile(r"\s+")


# def _norm_str(s: Any) -> Optional[str]:
#     if s is None:
#         return None
#     if not isinstance(s, str):
#         s = str(s)
#     s = s.strip()
#     if not s:
#         return None
#     # rapikan whitespace biar stabil
#     s = _WS_RE.sub(" ", s)
#     return s


# def _round_float(x: Any, ndigits: int = 6) -> Optional[float]:
#     try:
#         if x is None:
#             return None
#         return round(float(x), ndigits)
#     except Exception:
#         return None


# def _uniq_sorted_str_list(xs: Any) -> List[str]:
#     if not xs or not isinstance(xs, list):
#         return []
#     out = []
#     seen = set()
#     for v in xs:
#         s = _norm_str(v)
#         if not s:
#             continue
#         if s in seen:
#             continue
#         seen.add(s)
#         out.append(s)
#     out.sort()
#     return out


# def _normalize_prices(prices: Any) -> List[Dict[str, Any]]:
#     """
#     prices internal: [{currency, amount, period}, ...]
#     buat stabil: normalisasi + sort
#     """
#     if not prices or not isinstance(prices, list):
#         return []

#     out: List[Dict[str, Any]] = []
#     for p in prices:
#         if not isinstance(p, dict):
#             continue
#         currency = _norm_str(p.get("currency")) or None
#         period = _norm_str(p.get("period")) or None
#         amount = _round_float(p.get("amount"), 2)
#         if amount is None:
#             continue
#         out.append({"currency": currency, "amount": amount, "period": period})

#     out.sort(key=lambda d: (d.get("period") or "", d.get("currency") or "", d.get("amount") or 0))
#     return out


# def canonical_for_hash(listing: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Ambil subset field yang dianggap 'meaningful change' untuk incremental.
#     Ini yang dipakai buat compute_content_hash.
#     """

#     loc = listing.get("location") or {}
#     if not isinstance(loc, dict):
#         loc = {}

#     primary_price = listing.get("price") or {}
#     if not isinstance(primary_price, dict):
#         primary_price = {}

#     canonical = {
#         # identity-ish
#         "source": _norm_str(listing.get("source")),
#         "source_listing_id": _norm_str(listing.get("source_listing_id")),
#         "source_url": _norm_str(listing.get("source_url")),

#         # classification
#         "intent": _norm_str(listing.get("intent")),
#         "property_type": _norm_str(listing.get("property_type")),
#         "tenure": _norm_str(listing.get("tenure")),
#         "rent_period": _norm_str(listing.get("rent_period")),

#         # text
#         "title": _norm_str(listing.get("title")),
#         "description": _norm_str(listing.get("description")),

#         # sizes
#         "land_size_sqm": _round_float(listing.get("land_size_sqm"), 3),
#         "building_size_sqm": _round_float(listing.get("building_size_sqm"), 3),

#         # rooms
#         "bedrooms": _round_float(listing.get("bedrooms"), 1),
#         "bathrooms": _round_float(listing.get("bathrooms"), 1),

#         # geo
#         "location": {
#             "area": _norm_str(loc.get("area")),
#             "sub_area": _norm_str(loc.get("sub_area")),
#             "latitude": _round_float(loc.get("latitude"), 7),
#             "longitude": _round_float(loc.get("longitude"), 7),
#         },

#         # pricing
#         "price": {
#             "currency": _norm_str(primary_price.get("currency")),
#             "amount": _round_float(primary_price.get("amount"), 2),
#             "period": _norm_str(primary_price.get("period")),
#         },
#         "prices": _normalize_prices(listing.get("prices")),

#         # media
#         "images": _uniq_sorted_str_list(listing.get("images")),
#     }

#     # drop None recursively biar payload ringkas dan stabil
#     return _drop_nones(canonical)


# def _drop_nones(obj: Any) -> Any:
#     if isinstance(obj, dict):
#         out = {}
#         for k, v in obj.items():
#             v2 = _drop_nones(v)
#             if v2 is None:
#                 continue
#             # skip dict kosong
#             if isinstance(v2, dict) and not v2:
#                 continue
#             # skip list kosong
#             if isinstance(v2, list) and not v2:
#                 continue
#             out[k] = v2
#         return out
#     if isinstance(obj, list):
#         out = []
#         for v in obj:
#             v2 = _drop_nones(v)
#             if v2 is None:
#                 continue
#             out.append(v2)
#         return out
#     return obj


# def compute_content_hash(listing: Dict[str, Any]) -> str:
#     payload = canonical_for_hash(listing)
#     blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
#     return hashlib.sha256(blob.encode("utf-8")).hexdigest()


from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple


# =========================
# Normalization helpers
# =========================

_WS_RE = re.compile(r"\s+")


def _norm_str(s: Any) -> Optional[str]:
    """Normalize strings for hashing: strip, collapse whitespace."""
    if s is None:
        return None
    if not isinstance(s, str):
        s = str(s)
    s = s.strip()
    if not s:
        return None
    s = _WS_RE.sub(" ", s)
    return s


def _norm_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("true", "yes", "y", "1"):
            return True
        if t in ("false", "no", "n", "0"):
            return False
    return None


def _norm_float(v: Any, *, ndigits: int = 6) -> Optional[float]:
    """Normalize float-ish values to stable float with rounding."""
    if v is None:
        return None
    try:
        f = float(v)
    except Exception:
        return None
    # Handle NaN/inf
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return round(f, ndigits)


def _norm_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        t = v.strip()
        if not t:
            return None
        try:
            return int(float(t))
        except Exception:
            return None
    return None


def _drop_nones(obj: Any) -> Any:
    """
    Recursively remove None, empty dict, empty list, and empty strings.
    Ensures canonical JSON for stable hashing.
    """
    if obj is None:
        return None

    if isinstance(obj, str):
        s = _norm_str(obj)
        return s

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if v is None:
                continue
            vv = _drop_nones(v)
            if vv is None:
                continue
            # drop empty containers
            if vv == {} or vv == []:
                continue
            out[str(k)] = vv
        return out if out else None

    if isinstance(obj, list):
        out_list = []
        for v in obj:
            vv = _drop_nones(v)
            if vv is None or vv == {} or vv == []:
                continue
            out_list.append(vv)
        return out_list if out_list else None

    return obj


def _stable_json_dumps(obj: Any) -> str:
    """
    Stable JSON dump: sort_keys + compact separators.
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# =========================
# Hash input builders
# =========================

def build_content_fingerprint(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a stable 'content fingerprint' dict used for content_hash.
    IMPORTANT: exclude volatile fields:
      - raw / reso
      - timestamps (first_seen_at, last_seen_at)
      - scrape_run_id, scraped_at
      - content_hash itself
      - images (we hash separately in media_hash)
    """
    price = listing.get("price") or {}
    prices = listing.get("prices") or []

    loc = listing.get("location") or {}
    # location boleh, tapi distabilkan
    loc_fp = {
        "area": _norm_str(loc.get("area")),
        "sub_area": _norm_str(loc.get("sub_area") or loc.get("subArea")),
        "latitude": _norm_float(loc.get("latitude")),
        "longitude": _norm_float(loc.get("longitude")),
    }

    # Normalize prices list → stable sort
    prices_fp: List[Dict[str, Any]] = []
    for p in prices if isinstance(prices, list) else []:
        if not isinstance(p, dict):
            continue
        prices_fp.append({
            "currency": _norm_str(p.get("currency")),
            "amount": _norm_float(p.get("amount")),
            "period": _norm_str(p.get("period")),
        })

    prices_fp.sort(key=lambda x: (x.get("period") or "", x.get("currency") or "", x.get("amount") or 0.0))

    fp = {
        # identity-ish (source_listing_id + source_url tidak masuk content_hash agar pindah URL/query tidak bikin updated)
        "title": _norm_str(listing.get("title")),
        "description": _norm_str(listing.get("description")),
        "intent": _norm_str(listing.get("intent")),
        "property_type": _norm_str(listing.get("property_type")),

        "bedrooms": _norm_float(listing.get("bedrooms")),
        "bathrooms": _norm_float(listing.get("bathrooms")),  # kamu pakai float di internal
        "land_size_sqm": _norm_float(listing.get("land_size_sqm")),
        "building_size_sqm": _norm_float(listing.get("building_size_sqm")),

        "location": loc_fp,

        "price": {
            "currency": _norm_str(price.get("currency")),
            "amount": _norm_float(price.get("amount")),
            "period": _norm_str(price.get("period")),
        },

        "prices": prices_fp,

        # broker fields (optional; tetap distabilkan)
        "broker_name": _norm_str(listing.get("broker_name")),
        "broker_phone": _norm_str(listing.get("broker_phone")),
        "broker_email": _norm_str(listing.get("broker_email")),
    }

    # remove None / empties
    fp = _drop_nones(fp) or {}
    return fp


def build_media_fingerprint(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Separate fingerprint for media (images). This allows you to track media changes
    without marking listing 'updated' by content_hash.
    """
    imgs = listing.get("images") or []
    urls: List[str] = []
    if isinstance(imgs, list):
        for u in imgs:
            su = _norm_str(u)
            if su:
                urls.append(su)

    # stable unique + sorted
    urls = sorted(set(urls))

    fp = {"images": urls}
    fp = _drop_nones(fp) or {}
    return fp


# =========================
# Public API
# =========================

def compute_content_hash(listing: Dict[str, Any]) -> str:
    fp = build_content_fingerprint(listing)
    return _sha256_hex(_stable_json_dumps(fp))


def compute_media_hash(listing: Dict[str, Any]) -> str:
    fp = build_media_fingerprint(listing)
    return _sha256_hex(_stable_json_dumps(fp))


def compute_all_hashes(listing: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (content_hash, media_hash)
    """
    return compute_content_hash(listing), compute_media_hash(listing)
