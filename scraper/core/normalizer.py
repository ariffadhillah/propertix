# # from __future__ import annotations

# # from datetime import datetime, timezone
# # import hashlib
# # import json
# # from typing import Any, Dict


# # def utc_now_iso() -> str:
# #     return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# # def compute_content_hash(listing: Dict[str, Any]) -> str:
# #     """
# #     Hash only stable business fields for change detection.
# #     (Don't include timestamps / debug / raw payload / transient fields)
# #     """
# #     stable = {
# #         "source": listing.get("source"),
# #         "source_listing_id": listing.get("source_listing_id"),
# #         "source_url": listing.get("source_url"),

# #         "title": listing.get("title"),
# #         "description": listing.get("description"),
# #         "intent": listing.get("intent"),
# #         "property_type": listing.get("property_type"),

# #         "price": listing.get("price"),
# #         "prices": listing.get("prices"),

# #         "bedrooms": listing.get("bedrooms"),
# #         "bathrooms": listing.get("bathrooms"),
# #         "land_size_sqm": listing.get("land_size_sqm"),
# #         "building_size_sqm": listing.get("building_size_sqm"),

# #         "location": listing.get("location"),
# #         "images": listing.get("images"),

# #         "broker_name": listing.get("broker_name"),
# #         "broker_phone": listing.get("broker_phone"),
# #         "broker_email": listing.get("broker_email"),
# #     }

# #     raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
# #     return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# # def finalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
# #     """
# #     Set timestamps, defaults, content_hash.
# #     """
# #     now = utc_now_iso()

# #     listing.setdefault("status", "active")

# #     if not listing.get("first_seen_at"):
# #         listing["first_seen_at"] = now
# #     listing["last_seen_at"] = now

# #     listing["content_hash"] = compute_content_hash(listing)
# #     return listing


# # def merge_preview_into_detail(preview: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
# #     """
# #     Merge list preview into detail result (lat/lon/area, price preview fallback, etc).
# #     Keep detail as source-of-truth where available.
# #     """
# #     out = dict(detail)

# #     # ensure source fields
# #     out.setdefault("source", preview.get("source") or preview.get("source_key") or "unknown")
# #     out.setdefault("source_listing_id", preview.get("source_listing_id"))
# #     out.setdefault("source_url", preview.get("url") or out.get("source_url"))

# #     # intent + property_type (preview can help)
# #     if out.get("intent") in (None, "", "unknown"):
# #         out["intent"] = preview.get("intent_preview") or out.get("intent") or "unknown"

# #     # location merge
# #     pv_loc = preview.get("location_preview") or {}
# #     if pv_loc:
# #         out_loc = out.get("location") or {}
# #         # only fill missing
# #         out_loc.setdefault("area", pv_loc.get("area"))
# #         out_loc.setdefault("latitude", pv_loc.get("latitude"))
# #         out_loc.setdefault("longitude", pv_loc.get("longitude"))
# #         out["location"] = out_loc

# #     # price fallback (kalau detail page kadang gak ada)
# #     if out.get("price") is None and preview.get("price_preview") is not None:
# #         out["price"] = {
# #             "currency": "IDR",
# #             "amount": float(preview["price_preview"]),
# #             "period": "one_time",  # default; detail page akan override kalau tahu
# #         }

# #     # thumb → images fallback kalau detail belum ambil images
# #     if (not out.get("images")) and preview.get("thumb"):
# #         out["images"] = [preview["thumb"]]

# #     # raw preview (optional)
# #     out_raw = out.get("raw") or {}
# #     out_raw.setdefault("preview", {})
# #     out_raw["preview"].update({
# #         "price_category_preview": preview.get("price_category_preview"),
# #         "status_preview": preview.get("status_preview"),
# #         "tenure_preview": preview.get("tenure_preview"),
# #     })
# #     out["raw"] = out_raw

# #     return out

# # 


# from __future__ import annotations

# from datetime import datetime, timezone
# import hashlib
# import json
# import re
# from typing import Any, Dict


# def finalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
#     # ... rapikan field2 dulu ...

#     # safety: images unique (opsional)
#     if isinstance(listing.get("images"), list):
#         listing["images"] = list(dict.fromkeys([x for x in listing["images"] if x]))

#     listing["content_hash"] = compute_content_hash(listing)
#     return listing


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# def _norm_text(s: Any) -> Any:
#     """Normalize whitespace for text fields."""
#     if not isinstance(s, str):
#         return s
#     s = s.replace("\xa0", " ")
#     s = s.strip()
#     s = re.sub(r"\s+", " ", s)
#     return s


# def _round_num(x: Any) -> Any:
#     """Make numeric values stable (avoid 2 vs 2.0 issues)."""
#     if isinstance(x, bool):
#         return x
#     if isinstance(x, int):
#         return x
#     if isinstance(x, float):
#         # keep enough precision for prices/coords but avoid noise
#         return round(x, 6)
#     return x


# def _canonical(obj: Any) -> Any:
#     """
#     Recursively canonicalize dict/list/scalars so hashing is deterministic.
#     - dict keys sorted
#     - lists sorted when possible (for prices/images)
#     - text normalized
#     - numbers rounded
#     """
#     if obj is None:
#         return None

#     if isinstance(obj, dict):
#         # normalize keys + values
#         items = {}
#         for k, v in obj.items():
#             # keep keys as-is but normalize string keys spacing
#             kk = _norm_text(k) if isinstance(k, str) else k
#             items[kk] = _canonical(v)
#         # return as normal dict; json.dumps(sort_keys=True) will order keys
#         return items

#     if isinstance(obj, list):
#         canon_list = [_canonical(x) for x in obj]

#         # special: list of strings -> sort unique (images)
#         if all(isinstance(x, str) for x in canon_list):
#             uniq = list(dict.fromkeys([_norm_text(x) for x in canon_list if x]))
#             return sorted(uniq)

#         # special: list of dict prices -> sort by (period, currency, amount)
#         if all(isinstance(x, dict) for x in canon_list):
#             def _price_key(d: dict):
#                 return (
#                     str(d.get("period") or ""),
#                     str(d.get("currency") or ""),
#                     float(d.get("amount") or 0.0),
#                 )
#             # if looks like price dicts
#             if any("amount" in d or "period" in d for d in canon_list):
#                 return sorted(canon_list, key=_price_key)

#         return canon_list

#     if isinstance(obj, str):
#         return _norm_text(obj)

#     # numbers / others
#     return _round_num(obj)


# def compute_content_hash(listing: Dict[str, Any]) -> str:
#     """
#     Hash only stable business fields for change detection.
#     (Don't include timestamps / debug / raw payload / transient fields)
#     """
#     stable = {
#         "source": listing.get("source"),
#         "source_listing_id": listing.get("source_listing_id"),
#         "source_url": listing.get("source_url"),

#         "title": listing.get("title"),
#         "description": listing.get("description"),
#         "intent": listing.get("intent"),
#         "property_type": listing.get("property_type"),

#         "price": listing.get("price"),
#         "prices": listing.get("prices"),

#         "bedrooms": listing.get("bedrooms"),
#         "bathrooms": listing.get("bathrooms"),
#         "land_size_sqm": listing.get("land_size_sqm"),
#         "building_size_sqm": listing.get("building_size_sqm"),

#         "location": listing.get("location"),
#         "images": listing.get("images"),

#         "broker_name": listing.get("broker_name"),
#         "broker_phone": listing.get("broker_phone"),
#         "broker_email": listing.get("broker_email"),
#     }

#     stable = _canonical(stable)

#     raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
#     return hashlib.sha256(raw.encode("utf-8")).hexdigest()

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from scraper.core.hash_utils import compute_all_hashes


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def map_asset_class(property_type: str) -> str:
    if property_type in ("villa", "apartment", "townhouse"):
        return "residential"
    if property_type == "land":
        return "land"
    if property_type in ("hotel", "resort"):
        return "hospitality"
    if property_type in ("office", "retail"):
        return "commercial"
    return "residential"

def map_property_subtype(property_type: str) -> str:
    mapping = {
        "villa": "villa",
        "apartment": "apartment",
        "townhouse": "townhouse",
        "land": "residential_land",
        "hotel": "hotel",
        "resort": "resort",
        "office": "office",
        "retail": "retail",
    }
    return mapping.get(property_type, "villa")

def merge_preview_into_detail(preview: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge preview fields into detail.
    Rule:
      - detail menang (lebih lengkap)
      - preview mengisi yang kosong di detail
      - preview metadata disimpan di raw.preview agar bisa debug
    """
    merged = dict(detail or {})

    # identity defaults
    if not merged.get("source"):
        merged["source"] = preview.get("source")
    if not merged.get("source_listing_id"):
        merged["source_listing_id"] = preview.get("source_listing_id")
    if not merged.get("source_url"):
        merged["source_url"] = preview.get("url") or preview.get("source_url")

    # title fallback
    if not merged.get("title"):
        merged["title"] = preview.get("title")

    # location: merge existing + preview
    loc = merged.get("location") or {}
    if not isinstance(loc, dict):
        loc = {}

    loc_prev = preview.get("location_preview") or preview.get("location") or {}
    if isinstance(loc_prev, dict):
        # only fill missing
        for k in ("area", "sub_area", "latitude", "longitude"):
            if loc.get(k) is None and loc_prev.get(k) is not None:
                loc[k] = loc_prev.get(k)

    merged["location"] = loc if loc else None

    # preview price hints
    if merged.get("price") is None and preview.get("price_preview") is not None:
        # NOTE: price_preview biasanya amount + category; gunakan sebagai fallback kasar
        merged["price"] = {
            "currency": "IDR",
            "amount": float(preview["price_preview"]),
            "period": "one_time",
        }

    # status hint dari preview
    if merged.get("status") is None:
        sp = preview.get("status_preview")
        if sp:
            merged["status"] = sp

    # store preview raw for debugging
    raw = merged.get("raw") or {}
    if not isinstance(raw, dict):
        raw = {"_raw": raw}

    raw_preview = {
        k: preview.get(k)
        for k in (
            "price_category_preview",
            "status_preview",
            "tenure_preview",
            "location_preview",
            "raw_preview",
        )
        if preview.get(k) is not None
    }
    if raw_preview:
        raw.setdefault("preview", raw_preview)

    merged["raw"] = raw

    return merged


def finalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final pass before writing JSONL / sending to ingestion:
      - set defaults
      - normalize some shapes
      - compute hashes (content_hash + media_hash) from hash_utils
      - ensure first_seen_at / last_seen_at exist (if pipeline belum set)
    """
    out = dict(listing or {})

    # defaults
    out.setdefault("intent", "unknown")
    out.setdefault("property_type", "unknown")
    out.setdefault("images", [])
    out.setdefault("prices", [])

    # ensure location dict or None
    loc = out.get("location")
    if loc is not None and not isinstance(loc, dict):
        out["location"] = None

    # timestamps (kalau pipeline state belum inject)
    now = _now_iso()
    if not out.get("first_seen_at"):
        out["first_seen_at"] = now
    out["last_seen_at"] = now

    # status default: kalau belum ada, anggap active (karena muncul di crawl)
    out.setdefault("status", "active")

    # normalize images list (unique keep order)
    imgs = out.get("images") or []
    if isinstance(imgs, list):
        seen = set()
        cleaned = []
        for u in imgs:
            if not u:
                continue
            if u in seen:
                continue
            seen.add(u)
            cleaned.append(u)
        out["images"] = cleaned
    else:
        out["images"] = []

    # compute hashes (ONLY HERE)
    content_hash, media_hash = compute_all_hashes(out)
    out["content_hash"] = content_hash
    out["media_hash"] = media_hash
    listing["asset_class"] = map_asset_class(listing["property_type"])
    listing["property_subtype"] = map_property_subtype(listing["property_type"])

    return out