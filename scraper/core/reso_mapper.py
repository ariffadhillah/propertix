from __future__ import annotations

from typing import Any, Dict, List, Optional


def _period_to_price_unit(period: Optional[str]) -> Optional[str]:
    if not period:
        return None
    p = str(period).lower().strip()
    if p in ("one_time", "onetime", "one time"):
        return "OneTime"
    if p in ("year", "yearly", "annual"):
        return "Year"
    if p in ("month", "monthly"):
        return "Month"
    if p in ("night", "nightly", "day", "daily"):
        return "Day"
    if p in ("week", "weekly"):
        return "Week"
    return None


def _to_float(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
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


def _map_standard_status(internal_status: Optional[str]) -> str:
    s = (internal_status or "").lower().strip()
    if s in ("active", "off_plan", "off-plan"):
        return "Active"
    if s in ("removed", "sold", "closed", "inactive"):
        return "Closed"
    return "Unknown"


def _title_case_safe(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = str(s).replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _get_listing_key(listing: Dict[str, Any], source_key: str, listing_id: Optional[str]) -> str:
    lk = listing.get("ListingKey") or listing.get("listing_key")
    if isinstance(lk, str) and lk.strip():
        return lk.strip()
    if listing_id:
        return f"{source_key}:{listing_id}"
    return f"{source_key}:unknown"


def _extract_primary_price(listing: Dict[str, Any]) -> Dict[str, Any]:
    price = listing.get("price")
    if isinstance(price, dict) and price:
        return price
    return {
        "amount": listing.get("price_amount"),
        "currency": listing.get("price_currency"),
        "period": listing.get("price_period"),
    }


def _extract_prices_list(listing: Dict[str, Any]) -> List[Dict[str, Any]]:
    prices = listing.get("prices")
    if isinstance(prices, list) and prices:
        return [p for p in prices if isinstance(p, dict)]
    raw = _safe_dict(listing.get("raw"))
    payload = _safe_dict(raw.get("payload"))
    prices2 = payload.get("prices")
    if isinstance(prices2, list) and prices2:
        return [p for p in prices2 if isinstance(p, dict)]
    return []


def _extract_location(listing: Dict[str, Any]) -> Dict[str, Any]:
    loc = listing.get("location")
    if not isinstance(loc, dict):
        loc = {}

    if not loc.get("area") and listing.get("area"):
        loc["area"] = listing.get("area")
    if not loc.get("sub_area") and listing.get("sub_area"):
        loc["sub_area"] = listing.get("sub_area")

    if loc.get("latitude") is None and listing.get("latitude") is not None:
        loc["latitude"] = listing.get("latitude")
    if loc.get("longitude") is None and listing.get("longitude") is not None:
        loc["longitude"] = listing.get("longitude")

    return loc


def to_reso_listing(listing: Dict[str, Any], source_key: str) -> Dict[str, Any]:
    listing_id = listing.get("source_listing_id")
    listing_key = _get_listing_key(listing, source_key, listing_id)

    primary = _safe_dict(_extract_primary_price(listing))

    # IMPORTANT: treat 0 as missing (avoid analytics/comps pollution)
    amount = _to_float(primary.get("amount")) or _to_float(listing.get("price_amount"))
    if amount is not None and amount <= 0:
        amount = None

    currency = (primary.get("currency") if primary.get("currency") else None) or listing.get("price_currency") or "IDR"
    price_unit = _period_to_price_unit(primary.get("period") or listing.get("price_period"))

    prices_all: List[Dict[str, Any]] = []
    for p in _extract_prices_list(listing):
        a = _to_float(p.get("amount"))
        if a is None or a <= 0:
            continue
        prices_all.append(
            {
                "Price": a,
                "Currency": p.get("currency") or currency,
                "PriceUnit": _period_to_price_unit(p.get("period")),
            }
        )

    loc = _extract_location(listing)
    lat = _to_float(loc.get("latitude")) or _to_float(listing.get("latitude"))
    lng = _to_float(loc.get("longitude")) or _to_float(listing.get("longitude"))

    city = (loc.get("area") or listing.get("area") or loc.get("sub_area") or listing.get("sub_area"))
    prop_type = listing.get("property_subtype") or listing.get("property_type")
    prop_type_reso = _title_case_safe(prop_type)

    # timestamps (bridge from runner may inject these)
    first_seen = listing.get("first_seen_at") or listing.get("ingestion_first_seen_at")
    last_seen = listing.get("last_seen_at") or listing.get("ingestion_last_seen_at")

    scraped_at = (last_seen or "").replace("+00:00", "")

    out: Dict[str, Any] = {
        "ScrapeRunId": listing.get("scrape_run_id"),
        "ScrapedAt": scraped_at,
        "SourceKey": source_key,
        "ListingKey": listing_key,
        "ListingId": listing_id,
        "ListingURL": listing.get("source_url"),
        "StandardStatus": _map_standard_status(listing.get("status")),
        "ListingStatus": _title_case_safe(listing.get("status")) or "Unknown",
        "ListPrice": amount,
        "Currency": currency,
        "PriceUnit": price_unit,
        "PropertyType": prop_type_reso,
        "BedroomsTotal": _to_int(listing.get("bedrooms")),
        "BathroomsTotalInteger": _to_int(listing.get("bathrooms")),
        "LivingArea": _to_float(listing.get("building_size_sqm")),
        "LotSizeSquareMeters": _to_float(listing.get("land_size_sqm")),
        "Latitude": lat,
        "Longitude": lng,
        "City": city,
        "StateOrProvince": "Bali",
        "Country": "Indonesia",
        "FirstSeenAt": first_seen,
        "LastSeenAt": last_seen,
        "Prices": prices_all,
        "Media": listing.get("images") or [],
        "RawPayload": listing.get("raw") or {},
        "AssetClass": listing.get("asset_class"),
        "PropertySubType": listing.get("property_subtype"),
        "OfferCategory": listing.get("offer_category"),
        "TenureType": listing.get("tenure_type"),
        "RentPeriod": listing.get("rent_period"),
    }

    if listing.get("title"):
        out["Title"] = listing["title"]
    if listing.get("description"):
        out["Description"] = listing["description"]

    # --- Stage 2 placeholders (wajib ada walau null/kosong) ---
    out.setdefault("ListAgentKey", None)
    out.setdefault("ListOfficeKey", None)
    out.setdefault("Member", None)     # atau {} kalau kamu mau object kosong
    out.setdefault("Office", None)     # atau {} kalau kamu mau object kosong
    out.setdefault("OpenHouses", [])   # open house tidak relevan untuk BHI

    return out


def to_reso(listing: Dict[str, Any], scrape_run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Backward-compatible wrapper:
      - adapter lama bisa panggil to_reso(listing, scrape_run_id="...")
      - kalau scrape_run_id diberikan, inject ke listing sebelum mapping
    """
    if scrape_run_id:
        listing = dict(listing)
        listing["scrape_run_id"] = scrape_run_id

    source_key = listing.get("source") or listing.get("source_key") or "unknown"
    return to_reso_listing(listing, source_key)