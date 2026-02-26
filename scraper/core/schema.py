from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Literal

# --- Client enums (source of truth) ---
AssetClass = Literal["residential", "land", "hospitality", "commercial"]
PropertySubType = Literal[
    # Residential
    "villa", "apartment", "townhouse", "branded_residence",
    # Land
    "residential_land", "development_land", "agricultural_land",
    # Hospitality
    "hotel", "villa_complex", "resort",
    # Commercial
    "office", "retail",
]
OfferCategory = Literal["sale", "rent", "other"]
TenureType = Literal["freehold", "leasehold", "unknown"]
RentPeriod = Literal["night", "week", "month", "year", "unknown"]

# --- Helpers: coercion (normalize to enums) ---

def coerce_offer_category(v: Any) -> OfferCategory:
    s = (v or "").strip().lower()
    if s in ("sale", "for_sale", "sell"):
        return "sale"
    if s in ("rent", "for_rent", "rental", "lease"):
        return "rent"
    return "other"

def coerce_tenure_type(v: Any) -> TenureType:
    s = (v or "").strip().lower()
    if s in ("freehold",):
        return "freehold"
    if s in ("leasehold",):
        return "leasehold"
    return "unknown"

def coerce_rent_period(v: Any) -> RentPeriod:
    s = (v or "").strip().lower()
    if s in ("night", "nightly", "daily", "day"):
        return "night"
    if s in ("week", "weekly"):
        return "week"
    if s in ("month", "monthly"):
        return "month"
    if s in ("year", "yearly", "annual"):
        return "year"
    return "unknown"

def normalize_text_key(s: str) -> str:
    return (s or "").strip().lower().replace("-", "_").replace(" ", "_")

def map_subtype_and_asset_class(raw_type: Optional[str]) -> Tuple[AssetClass, PropertySubType]:
    """
    Map raw property type (from URL/selector) into client enums.

    IMPORTANT:
    - raw_type dari BHI biasanya: villa, apartment, land, hotel, resort, office, retail
    - kalau cuma 'land' (generic) => default ke development_land (MVP) supaya valid enum.
      (Nanti breadcrumb/label bisa refine jadi residential_land/agricultural_land)
    """
    t = normalize_text_key(raw_type or "")

    # Residential
    if t in ("villa",):
        return ("residential", "villa")
    if t in ("apartment", "apt"):
        return ("residential", "apartment")
    if t in ("townhouse", "town_house"):
        return ("residential", "townhouse")
    if t in ("branded_residence", "brandedresidence"):
        return ("residential", "branded_residence")

    # Hospitality
    if t in ("hotel",):
        return ("hospitality", "hotel")
    if t in ("villa_complex", "villa_complexes", "villa_complexe", "villa-complex"):
        return ("hospitality", "villa_complex")
    if t in ("resort",):
        return ("hospitality", "resort")

    # Commercial
    if t in ("office",):
        return ("commercial", "office")
    if t in ("retail", "retailil"):
        return ("commercial", "retail")

    # Land
    if t in ("residential_land",):
        return ("land", "residential_land")
    if t in ("development_land", "land"):
        return ("land", "development_land")
    if t in ("agricultural_land",):
        return ("land", "agricultural_land")

    # Safe fallback (MVP)
    return ("residential", "villa")

def ensure_taxonomy_fields(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure client fields exist & normalized:
    offer_category, tenure_type, rent_period, asset_class, property_subtype

    Legacy fields boleh ada, tapi client fields wajib diisi.
    """
    # 1) offer_category from legacy intent if missing
    if not listing.get("offer_category"):
        listing["offer_category"] = coerce_offer_category(listing.get("intent"))

    listing["offer_category"] = coerce_offer_category(listing.get("offer_category"))
    listing["tenure_type"] = coerce_tenure_type(listing.get("tenure_type") or listing.get("tenure"))
    listing["rent_period"] = coerce_rent_period(listing.get("rent_period"))

    # 2) subtype + asset_class from legacy property_type if missing
    if not listing.get("property_subtype") or not listing.get("asset_class"):
        asset_class, subtype = map_subtype_and_asset_class(listing.get("property_subtype") or listing.get("property_type"))
        listing.setdefault("asset_class", asset_class)
        listing.setdefault("property_subtype", subtype)

    return listing


SCHEMA_VERSION = "listings_master_v1"

def empty_record() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,

        "listing": {
            "source": None,
            "source_listing_id": None,
            "source_url": None,
            "ListingKey": None,

            "title": None,
            "description": None,

            "price_amount": None,
            "price_currency": None,
            "price_period": None,

            "bedrooms": None,
            "bathrooms": None,
            "land_size_sqm": None,
            "building_size_sqm": None,

            "area": None,
            "latitude": None,
            "longitude": None,

            "images": [],

            # ✅ taxonomy client (ini penting buat API-ready)
            "offer_category": None,
            "tenure_type": None,
            "rent_period": None,
            "asset_class": None,
            "property_subtype": None,

            "broker": {
                "broker_name": None,
                "broker_phone_raw": None,
                "broker_phone": None,
                "broker_email": None,
                "broker_profile_url": None,
                "agency_name": None,
                "contact_links_raw": {"mailto": [], "tel": [], "whatsapp": [], "other": []},
            },
        },

        "hashes": {
            "canonical_hash_input": {
                "ListingKey": None,
                "title": None,
                "description": None,
                "price": {"amount": None, "currency": None, "period": None},
                "specs": {"bedrooms": None, "bathrooms": None, "land_size_sqm": None, "building_size_sqm": None},
                "location": {"area": None, "lat": None, "lng": None},
                "images": [],
            },
            "canonical_content_hash": None,
            "raw_payload_hash": None,
        },

        "ingestion": {
            "scrape_run_id": None,
            "captured_at": None,
            "first_seen_at": None,
            "last_seen_at": None,
        },

        "status": {
            "current_status": "active",
            "last_change_type": None,
        },

        "reso": None,

        "raw": {
            "payload": {},
            "source_preview": None,
            "source_detail": None,
        },
    }