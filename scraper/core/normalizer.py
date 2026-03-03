# scraper/core/normalizer.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from scraper.core.schema import empty_record, ensure_taxonomy_fields
from scraper.core.hash_utils import (
    build_canonical_hash_input,
    compute_canonical_content_hash,
    compute_media_hash,
    compute_raw_payload_hash,
)

__all__ = [
    "ensure_stage2_placeholders",
    "iso_now",
    "utc_now_iso",
    "merge_preview_into_detail",
    "finalize_listing",
    "finalize_record",
]


# ============================================================
# PLACEHOLDERS (Stage 2)
# ============================================================

def ensure_stage2_placeholders(out: dict) -> dict:
    """
    Force-add field yang wajib ada di output (agent/office/openhouse + asset-level identity)
    tanpa merusak field existing.
    """
    # --- 1) RESO placeholders (force reso jadi dict) ---
    reso = out.get("reso")
    if not isinstance(reso, dict):
        reso = {}
        out["reso"] = reso

    reso.setdefault("ListAgentKey", None)
    reso.setdefault("ListOfficeKey", None)
    reso.setdefault("Member", None)
    reso.setdefault("Office", None)
    reso.setdefault("OpenHouses", [])

    # --- 2) Asset-level placeholders (root-level) ---
    if not isinstance(out.get("asset"), dict):
        out["asset"] = {
            "asset_id": None,
            "asset_key": None,
            "asset_class": None,
            "property_subtype": None,
            "geo": {"lat": None, "lng": None},
            "address": None,
            "created_at": None,
            "updated_at": None,
        }

    if not isinstance(out.get("asset_version"), dict):
        out["asset_version"] = {
            "asset_version_id": None,
            "asset_id": None,
            "valid_from": None,
            "valid_to": None,
            "snapshot": {},
        }

    if not isinstance(out.get("listing_asset_link"), dict):
        out["listing_asset_link"] = {
            "listing_key": (out.get("listing") or {}).get("ListingKey"),
            "asset_id": None,
            "confidence": None,
            "method": None,
            "reason": {},
            "created_at": None,
        }
    else:
        out["listing_asset_link"].setdefault(
            "listing_key", (out.get("listing") or {}).get("ListingKey")
        )

    return out


# ============================================================
# TIME HELPERS
# ============================================================

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# MERGE PREVIEW + DETAIL  ✅ (INI YANG HILANG)
# ============================================================

def merge_preview_into_detail(preview: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge strategy:
    - detail wins for content fields
    - preview supplies missing fields (location_preview, thumb, etc)
    - normalize URL to only source_url (avoid url vs source_url duplicates)
    """
    out: Dict[str, Any] = dict(preview or {})

    for k, v in (detail or {}).items():
        if v is None:
            continue
        out[k] = v

    # Merge location dicts carefully
    loc_p = (preview or {}).get("location") or (preview or {}).get("location_preview")
    loc_d = (detail or {}).get("location")
    if isinstance(loc_p, dict) or isinstance(loc_d, dict):
        merged: Dict[str, Any] = {}
        if isinstance(loc_p, dict):
            merged.update(loc_p)
        if isinstance(loc_d, dict):
            merged.update(loc_d)
        out["location"] = merged or None

    # URL canonicalization (top-level only source_url)
    if not out.get("source_url"):
        u = (preview or {}).get("url") or (detail or {}).get("url")
        if isinstance(u, str) and u.strip():
            out["source_url"] = u.strip()

    # remove legacy url to prevent duplicates downstream
    out.pop("url", None)

    # keep preview debug
    raw = out.get("raw") or {}
    if "preview" not in raw and preview:
        raw["preview"] = {
            "location_preview": (preview or {}).get("location") or (preview or {}).get("location_preview"),
            "status_preview": (preview or {}).get("status") or (preview or {}).get("status_preview"),
            "price_category_preview": (preview or {}).get("price_category_preview"),
            "tenure_preview": (preview or {}).get("tenure_preview"),
            "raw_preview": (preview or {}).get("raw_preview"),
        }
    out["raw"] = raw

    return out


# ============================================================
# FINALIZE LISTING (internal pipeline)
# ============================================================

def finalize_listing(listing: Dict[str, Any], scrape_run_id: str, seen_at: Optional[str] = None) -> Dict[str, Any]:
    """
    Fill required metadata + taxonomy + hashes.
    (Ini buat pipeline internal listing, bukan record final output)
    """
    now = seen_at or iso_now()

    listing.setdefault("source", "unknown")
    listing.setdefault("status", "active")

    # timestamps
    listing.setdefault("first_seen_at", now)
    listing["last_seen_at"] = now
    listing["scrape_run_id"] = scrape_run_id

    # Ensure client taxonomy fields are present & normalized
    ensure_taxonomy_fields(listing)

    # Client-required canonical hash
    listing["canonical_content_hash"] = compute_canonical_content_hash(listing)

    # Backward compatible: runner/state currently uses content_hash
    listing["content_hash"] = listing["canonical_content_hash"]

    # media hash still useful for image-only diffs
    listing["media_hash"] = compute_media_hash(listing.get("images") or [])

    # store canonical hash input for debugging
    canon_obj = build_canonical_hash_input(listing)
    listing.setdefault("raw", {})
    listing["raw"].setdefault("debug", {})
    listing["raw"]["debug"]["canonical_hash_input"] = canon_obj

    return listing


# ============================================================
# FINAL OUTPUT RECORD
# ============================================================

def finalize_record(merged_flat: dict, *, scrape_run_id: str, captured_at: str | None = None) -> dict:
    """
    Build final output record:
      {schema_version, listing, hashes, ingestion, status, reso, raw, asset placeholders}
    """
    rec = empty_record()
    now = captured_at or utc_now_iso()

    # ---------------- ingestion
    rec["ingestion"]["scrape_run_id"] = scrape_run_id
    rec["ingestion"]["captured_at"] = now
    rec["ingestion"]["first_seen_at"] = merged_flat.get("first_seen_at")
    rec["ingestion"]["last_seen_at"] = merged_flat.get("last_seen_at") or now

    # ---------------- status
    rec["status"]["current_status"] = merged_flat.get("current_status") or merged_flat.get("status") or "active"
    rec["status"]["last_change_type"] = merged_flat.get("last_change_type")

    # ---------------- listing
    L = rec["listing"]

    L["source"] = merged_flat.get("source") or merged_flat.get("source_key")
    L["source_listing_id"] = merged_flat.get("source_listing_id")
    L["source_url"] = merged_flat.get("source_url")

    # ListingKey fallback wajib
    lk = merged_flat.get("ListingKey") or merged_flat.get("listing_key")
    if not lk and L["source"] and L["source_listing_id"]:
        lk = f"{L['source']}:{L['source_listing_id']}"
    L["ListingKey"] = lk

    L["title"] = merged_flat.get("title")
    L["description"] = merged_flat.get("description")

    # ---------------- price (primary) + nested price object
    price = merged_flat.get("price") or {}
    if isinstance(price, dict):
        L["price_amount"] = price.get("amount")
        L["price_currency"] = price.get("currency")
        L["price_period"] = price.get("period")
    else:
        L["price_amount"] = merged_flat.get("price_amount")
        L["price_currency"] = merged_flat.get("price_currency")
        L["price_period"] = merged_flat.get("price_period")

    L["price"] = {
        "currency": L.get("price_currency"),
        "amount": L.get("price_amount"),
        "period": L.get("price_period"),
    }

    # ---------------- specs
    L["bedrooms"] = merged_flat.get("bedrooms")
    L["bathrooms"] = merged_flat.get("bathrooms")
    L["land_size_sqm"] = merged_flat.get("land_size_sqm")
    L["building_size_sqm"] = merged_flat.get("building_size_sqm")

    # ---------------- location
    loc = merged_flat.get("location") or {}
    if isinstance(loc, dict):
        L["area"] = loc.get("area") or merged_flat.get("area")
        L["sub_area"] = loc.get("sub_area") or merged_flat.get("sub_area")
        L["latitude"] = loc.get("latitude") or loc.get("lat") or merged_flat.get("latitude")
        L["longitude"] = loc.get("longitude") or loc.get("lng") or merged_flat.get("longitude")
    else:
        L["area"] = merged_flat.get("area")
        L["sub_area"] = merged_flat.get("sub_area")
        L["latitude"] = merged_flat.get("latitude")
        L["longitude"] = merged_flat.get("longitude")

    # images + prices
    L["images"] = merged_flat.get("images") or []
    L["prices"] = merged_flat.get("prices") or []

    # ---------------- taxonomy
    L["offer_category"] = merged_flat.get("offer_category")
    L["tenure_type"] = merged_flat.get("tenure_type")
    L["rent_period"] = merged_flat.get("rent_period")
    L["asset_class"] = merged_flat.get("asset_class")
    L["property_subtype"] = merged_flat.get("property_subtype")

    # ---------------- broker
    B = L["broker"]
    broker_obj = merged_flat.get("broker")
    if isinstance(broker_obj, dict):
        B["broker_name"] = broker_obj.get("broker_name")
        B["broker_phone_raw"] = broker_obj.get("broker_phone_raw")
        B["broker_phone"] = broker_obj.get("broker_phone")
        B["broker_email"] = broker_obj.get("broker_email")
        B["broker_profile_url"] = broker_obj.get("broker_profile_url")
        B["agency_name"] = broker_obj.get("agency_name")

        clr = broker_obj.get("contact_links_raw")
        if isinstance(clr, dict):
            B["contact_links_raw"] = clr
    else:
        B["broker_name"] = merged_flat.get("broker_name")
        B["broker_phone_raw"] = merged_flat.get("broker_phone_raw")
        B["broker_phone"] = merged_flat.get("broker_phone")
        B["broker_email"] = merged_flat.get("broker_email")
        B["broker_profile_url"] = merged_flat.get("broker_profile_url")
        B["agency_name"] = merged_flat.get("agency_name")

        clr = merged_flat.get("contact_links_raw")
        if isinstance(clr, dict):
            B["contact_links_raw"] = clr

    # ---------------- raw payload
    rec["raw"]["payload"] = merged_flat.get("raw") or {}

    # ---------------- hashes (canonical + deterministic)
    chi = build_canonical_hash_input({
        "ListingKey": L["ListingKey"],
        "title": L.get("title"),
        "description": L.get("description"),
        "price": {
            "amount": L.get("price_amount"),
            "currency": L.get("price_currency"),
            "period": L.get("price_period"),
        },
        "prices": L.get("prices") or [],
        "specs": {
            "bedrooms": L.get("bedrooms"),
            "bathrooms": L.get("bathrooms"),
            "land_size_sqm": L.get("land_size_sqm"),
            "building_size_sqm": L.get("building_size_sqm"),
        },
        "location": {
            "area": L.get("area"),
            "sub_area": L.get("sub_area"),
            "lat": L.get("latitude"),
            "lng": L.get("longitude"),
        },
        "images": L.get("images") or [],
    })

    rec["hashes"]["canonical_hash_input"] = chi
    rec["hashes"]["canonical_content_hash"] = compute_canonical_content_hash(chi)
    rec["hashes"]["raw_payload_hash"] = compute_raw_payload_hash(rec["raw"]["payload"])

    # ✅ enforce canonical order
    if isinstance(chi.get("images"), list):
        L["images"] = chi["images"]
    if isinstance(chi.get("prices"), list):
        L["prices"] = chi["prices"]

    ensure_stage2_placeholders(rec)
    return rec