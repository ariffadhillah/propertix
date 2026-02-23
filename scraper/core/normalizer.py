from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compute_content_hash(listing: Dict[str, Any]) -> str:
    """
    Hash only stable business fields for change detection.
    (Don't include timestamps / debug / raw payload / transient fields)
    """
    stable = {
        "source": listing.get("source"),
        "source_listing_id": listing.get("source_listing_id"),
        "source_url": listing.get("source_url"),

        "title": listing.get("title"),
        "description": listing.get("description"),
        "intent": listing.get("intent"),
        "property_type": listing.get("property_type"),

        "price": listing.get("price"),
        "prices": listing.get("prices"),

        "bedrooms": listing.get("bedrooms"),
        "bathrooms": listing.get("bathrooms"),
        "land_size_sqm": listing.get("land_size_sqm"),
        "building_size_sqm": listing.get("building_size_sqm"),

        "location": listing.get("location"),
        "images": listing.get("images"),

        "broker_name": listing.get("broker_name"),
        "broker_phone": listing.get("broker_phone"),
        "broker_email": listing.get("broker_email"),
    }

    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def finalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set timestamps, defaults, content_hash.
    """
    now = utc_now_iso()

    listing.setdefault("status", "active")

    if not listing.get("first_seen_at"):
        listing["first_seen_at"] = now
    listing["last_seen_at"] = now

    listing["content_hash"] = compute_content_hash(listing)
    return listing


def merge_preview_into_detail(preview: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge list preview into detail result (lat/lon/area, price preview fallback, etc).
    Keep detail as source-of-truth where available.
    """
    out = dict(detail)

    # ensure source fields
    out.setdefault("source", preview.get("source") or preview.get("source_key") or "unknown")
    out.setdefault("source_listing_id", preview.get("source_listing_id"))
    out.setdefault("source_url", preview.get("url") or out.get("source_url"))

    # intent + property_type (preview can help)
    if out.get("intent") in (None, "", "unknown"):
        out["intent"] = preview.get("intent_preview") or out.get("intent") or "unknown"

    # location merge
    pv_loc = preview.get("location_preview") or {}
    if pv_loc:
        out_loc = out.get("location") or {}
        # only fill missing
        out_loc.setdefault("area", pv_loc.get("area"))
        out_loc.setdefault("latitude", pv_loc.get("latitude"))
        out_loc.setdefault("longitude", pv_loc.get("longitude"))
        out["location"] = out_loc

    # price fallback (kalau detail page kadang gak ada)
    if out.get("price") is None and preview.get("price_preview") is not None:
        out["price"] = {
            "currency": "IDR",
            "amount": float(preview["price_preview"]),
            "period": "one_time",  # default; detail page akan override kalau tahu
        }

    # thumb → images fallback kalau detail belum ambil images
    if (not out.get("images")) and preview.get("thumb"):
        out["images"] = [preview["thumb"]]

    # raw preview (optional)
    out_raw = out.get("raw") or {}
    out_raw.setdefault("preview", {})
    out_raw["preview"].update({
        "price_category_preview": preview.get("price_category_preview"),
        "status_preview": preview.get("status_preview"),
        "tenure_preview": preview.get("tenure_preview"),
    })
    out["raw"] = out_raw

    return out