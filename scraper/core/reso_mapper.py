# from __future__ import annotations

# from datetime import datetime
# from typing import Any, Dict, Optional, List
# run_id = datetime.utcnow().isoformat()

# PROPERTY_TYPE_MAP = {
#     "villa": "Villa",
#     "house": "House",
#     "apartment": "Apartment",
#     "land": "Land",
#     "commercial": "Commercial",
#     "other": "Other",
#     "unknown": "Unknown",
# }


# def _map_address(listing: Dict[str, Any]) -> Dict[str, Any]:
#     loc = listing.get("location") or {}

#     return {
#         "City": loc.get("area"),
#         "StateOrProvince": "Bali",
#         "Country": "Indonesia",
#     }

# def _period_to_price_unit(period: Optional[str]) -> Optional[str]:
#     """
#     internal periods: one_time / year / month / day
#     -> RESO-ish unit
#     """
#     if not period:
#         return None
#     p = period.lower().strip()
#     if p == "one_time":
#         return "OneTime"
#     if p == "year":
#         return "Year"
#     if p == "month":
#         return "Month"
#     if p == "day":
#         return "Day"
#     return None


# def _to_float(v: Any) -> Optional[float]:
#     if isinstance(v, (int, float)):
#         return float(v)
#     return None


# def _to_int(v: Any) -> Optional[int]:
#     if isinstance(v, bool):
#         return None
#     if isinstance(v, int):
#         return v
#     if isinstance(v, float):
#         return int(v)
#     return None


# # def _map_standard_status(status_internal: str) -> str:
# #     s = (status_internal or "unknown").lower()
# #     if s == "active":
# #         return "Active"
# #     if s == "removed":
# #         return "Closed"
# #     return "Unknown"

# def _map_standard_status(status: Optional[str]) -> str:
#     s = (status or "").lower()

#     if s in ("active", "off_plan"):
#         return "Active"
#     if s in ("sold", "removed"):
#         return "Closed"

#     return "Unknown"

# def _map_property_type(listing: Dict[str, Any]) -> Optional[str]:
#     url = (listing.get("source_url") or "").lower()

#     if "/villa/" in url:
#         return "Villa"
#     if "/apartment/" in url:
#         return "Apartment"
#     if "/land/" in url:
#         return "Land"

#     return None

# def to_reso_listing(listing: Dict[str, Any], source_key: str) -> Dict[str, Any]:
#     """
#     Convert internal scraper-normalized listing dict -> RESO-aligned-ish Listing payload.
#     This payload can be sent to GraphQL ingestListings(batch).
#     """

#     # ---- Identity
#     listing_id = listing.get("source_listing_id")  # source-specific
#     listing_key = f"{source_key}:{listing_id}" if listing_id else f"{source_key}:unknown"

#     # ---- Pricing
#     primary = listing.get("price") or {}
#     list_price = _to_float(primary.get("amount"))
#     currency = primary.get("currency") or "IDR"
#     price_unit = _period_to_price_unit(primary.get("period"))

#     prices_all: List[Dict[str, Any]] = []
#     for p in (listing.get("prices") or []):
#         prices_all.append({
#             "Price": _to_float(p.get("amount")),
#             "Currency": p.get("currency") or currency,
#             "PriceUnit": _period_to_price_unit(p.get("period")),
#         })

#     # ---- Core attributes
#     beds = _to_float(listing.get("bedrooms"))  # keep float for safety
#     # baths = _to_int(listing.get("bathrooms"))  # RESO asks Integer
#     baths = int(baths) if baths is not None else None

#     living_area = _to_float(listing.get("building_size_sqm"))      # LivingArea (sqm)
#     lot_size_sqm = _to_float(listing.get("land_size_sqm"))         # LotSizeSquareMeters

#     # ---- Status
#     status_internal = (listing.get("status") or "unknown").lower()
#     standard_status = _map_standard_status(status_internal)

#     # ListingStatus: keep closer to internal (still string)
#     listing_status = status_internal.capitalize() if status_internal else "Unknown"

#     # ---- PropertyType
#     # prop_type = (listing.get("property_type") or "unknown").lower().strip()
#     # prop_type_out = PROPERTY_TYPE_MAP.get(prop_type, "Unknown")
#     prop_type_out = prop_type_out = _map_property_type(listing)

#     # ---- Geo
#     loc = listing.get("location") or {}
#     lat = _to_float(loc.get("latitude"))
#     lng = _to_float(loc.get("longitude"))

#     address = _map_address(listing)

#     # ---- Media
#     media = listing.get("images") or []
#     if not isinstance(media, list):
#         media = []

#     media = list(dict.fromkeys(listing.get("images") or []))

#     # ---- Raw payload
#     raw_payload = listing.get("raw") or {}
#     if not isinstance(raw_payload, dict):
#         raw_payload = {"_raw": raw_payload}

#     return {
#         "ScrapeRunId": run_id,
#         "ScrapedAt": now_iso,
#         "SourceKey": "bali-home-immo"

#         # Source + identity
#         "SourceKey": source_key,
#         "ListingKey": listing_key,
#         "ListingId": listing_id,
#         "ListingURL": listing.get("source_url"),

#         # Status
#         "StandardStatus": standard_status,
#         "ListingStatus": listing_status,

#         # Pricing
#         "ListPrice": list_price,
#         "Currency": currency,
#         "PriceUnit": price_unit,

#         # Property core
#         "PropertyType": prop_type_out,
#         "BedroomsTotal": beds,
#         "BathroomsTotalInteger": baths,

#         # Areas
#         "LivingArea": living_area,
#         "LotSizeSquareMeters": lot_size_sqm,

#         # Geo
#         "Latitude": lat,
#         "Longitude": lng,

#         "City": address.get("City"),
#         "StateOrProvince": address.get("StateOrProvince"),
#         "Country": address.get("Country"),

#         # Timestamps
#         "FirstSeenAt": listing.get("first_seen_at"),
#         "LastSeenAt": listing.get("last_seen_at"),

#         # Observations / extras (backend will split)
#         "Prices": prices_all,
#         "Media": media,
#         "RawPayload": raw_payload,

#         # Helpful content fields
#         "Title": listing.get("title"),
#         "Description": listing.get("description"),
#     }


# def to_reso(listing: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Standard wrapper for adapters.
#     Uses the existing to_reso_listing(listing, source_key).
#     """
#     source_key = listing.get("source") or listing.get("source_key") or "unknown"
#     return to_reso_listing(listing, source_key)




from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, List


def _map_address(listing: Dict[str, Any]) -> Dict[str, Any]:
    loc = listing.get("location") or {}
    return {
        "City": loc.get("area"),
        "StateOrProvince": "Bali",
        "Country": "Indonesia",
    }


def _period_to_price_unit(period: Optional[str]) -> Optional[str]:
    if not period:
        return None
    p = period.lower().strip()
    if p == "one_time":
        return "OneTime"
    if p == "year":
        return "Year"
    if p == "month":
        return "Month"
    if p == "day":
        return "Day"
    return None


def _to_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _to_int(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return None


def _map_standard_status(status: Optional[str]) -> str:
    s = (status or "").lower()

    if s in ("active", "off_plan"):
        return "Active"
    if s in ("sold", "removed"):
        return "Closed"

    return "Unknown"


def _map_property_type(listing: Dict[str, Any]) -> Optional[str]:
    url = (listing.get("source_url") or "").lower()

    if "/villa/" in url:
        return "Villa"
    if "/apartment/" in url:
        return "Apartment"
    if "/land/" in url:
        return "Land"

    return None


def to_reso_listing(
    listing: Dict[str, Any],
    source_key: str,
    scrape_run_id: str,
) -> Dict[str, Any]:

    now_iso = datetime.utcnow().isoformat()

    listing_id = listing.get("source_listing_id")
    listing_key = f"{source_key}:{listing_id}" if listing_id else f"{source_key}:unknown"

    primary = listing.get("price") or {}
    list_price = _to_float(primary.get("amount"))
    currency = primary.get("currency") or "IDR"
    price_unit = _period_to_price_unit(primary.get("period"))

    prices_all: List[Dict[str, Any]] = []
    for p in (listing.get("prices") or []):
        prices_all.append({
            "Price": _to_float(p.get("amount")),
            "Currency": p.get("currency") or currency,
            "PriceUnit": _period_to_price_unit(p.get("period")),
        })

    beds = _to_float(listing.get("bedrooms"))
    baths = _to_int(listing.get("bathrooms"))

    living_area = _to_float(listing.get("building_size_sqm"))
    lot_size_sqm = _to_float(listing.get("land_size_sqm"))

    status_internal = (listing.get("status") or "unknown").lower()
    standard_status = _map_standard_status(status_internal)
    listing_status = status_internal.capitalize()

    prop_type_out = _map_property_type(listing)

    loc = listing.get("location") or {}
    lat = _to_float(loc.get("latitude"))
    lng = _to_float(loc.get("longitude"))

    address = _map_address(listing)

    media = listing.get("images") or []
    if not isinstance(media, list):
        media = []
    media = list(dict.fromkeys(media))

    raw_payload = listing.get("raw") or {}
    if not isinstance(raw_payload, dict):
        raw_payload = {"_raw": raw_payload}

    return {
        "ScrapeRunId": scrape_run_id,
        "ScrapedAt": now_iso,
        "SourceKey": source_key,

        "ListingKey": listing_key,
        "ListingId": listing_id,
        "ListingURL": listing.get("source_url"),

        "StandardStatus": standard_status,
        "ListingStatus": listing_status,

        "ListPrice": list_price,
        "Currency": currency,
        "PriceUnit": price_unit,

        "PropertyType": prop_type_out,
        "BedroomsTotal": beds,
        "BathroomsTotalInteger": baths,

        "LivingArea": living_area,
        "LotSizeSquareMeters": lot_size_sqm,

        "Latitude": lat,
        "Longitude": lng,

        "City": address.get("City"),
        "StateOrProvince": address.get("StateOrProvince"),
        "Country": address.get("Country"),

        "FirstSeenAt": listing.get("first_seen_at"),
        "LastSeenAt": listing.get("last_seen_at"),

        "Prices": prices_all,
        "Media": media,
        "RawPayload": raw_payload,

        "Title": listing.get("title"),
        "Description": listing.get("description"),
    }


def to_reso(
    listing: Dict[str, Any],
    scrape_run_id: str,
) -> Dict[str, Any]:

    source_key = listing.get("source") or "unknown"
    return to_reso_listing(listing, source_key, scrape_run_id)