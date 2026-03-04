# # scraper/schema/v3_exporter.py
# from __future__ import annotations

# import json
# import re
# from typing import Any, Dict, List, Optional
# from urllib.parse import urlparse

# from scraper.core.hash_utils import (
#     compute_raw_payload_hash,
#     compute_canonical_content_hash,
#     compute_media_hash,
#     sha256_str,
# )

# SCHEMA_VERSION_V3 = "3.0.0"


# # ------------------------------------------------------------
# # small helpers
# # ------------------------------------------------------------

# def _stable_json_str(obj: Any) -> str:
#     return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# def _to_int(x: Any) -> Optional[int]:
#     if x is None:
#         return None
#     try:
#         return int(float(x))
#     except Exception:
#         return None


# def _to_float(x: Any) -> Optional[float]:
#     if x is None:
#         return None
#     try:
#         return float(x)
#     except Exception:
#         return None


# def _clean_str(x: Any) -> Optional[str]:
#     if not isinstance(x, str):
#         return None
#     s = x.strip()
#     return s or None


# def _norm_str(x: Any) -> Optional[str]:
#     s = _clean_str(x)
#     return s.lower() if s else None


# def _domain(url: Optional[str]) -> Optional[str]:
#     """
#     https://bali-home-immo.com/path?a=1 -> https://bali-home-immo.com
#     """
#     u = _clean_str(url)
#     if not u:
#         return None
#     try:
#         p = urlparse(u)
#         if p.scheme and p.netloc:
#             return f"{p.scheme}://{p.netloc}"
#     except Exception:
#         pass
#     return None


# def _listing_key_from_record(rec: Dict[str, Any]) -> Optional[str]:
#     listing = rec.get("listing") or {}
#     if not isinstance(listing, dict):
#         listing = {}

#     lk = _clean_str(listing.get("listing_key")) or _clean_str(listing.get("ListingKey"))
#     if lk:
#         return lk

#     source = _clean_str(listing.get("source"))
#     sid = _clean_str(listing.get("source_listing_id"))
#     if source and sid:
#         return f"{source}:{sid}"

#     url = (
#         _clean_str(listing.get("listing_url"))
#         or _clean_str(listing.get("source_url"))
#         or _clean_str(listing.get("url"))
#     )
#     if url:
#         return sha256_str(url)

#     return None


# def _listing_url_from_record(rec: Dict[str, Any]) -> Optional[str]:
#     listing = rec.get("listing") or {}
#     if not isinstance(listing, dict):
#         listing = {}
#     return (
#         _clean_str(listing.get("listing_url"))
#         or _clean_str(listing.get("source_url"))
#         or _clean_str(listing.get("url"))
#     )


# def _media_from_images(images: Any) -> List[Dict[str, Any]]:
#     out: List[Dict[str, Any]] = []
#     if not isinstance(images, list):
#         return out
#     order = 0
#     for u in images:
#         su = _clean_str(u)
#         if not su:
#             continue
#         out.append(
#             {
#                 "url": su,
#                 "order": order,
#                 "type": "image",
#                 "width": None,
#                 "height": None,
#                 "checksum": None,
#                 "phash": None,
#             }
#         )
#         order += 1
#     return out


# def _prices_to_variants(prices: Any, primary_price: Any) -> List[Dict[str, Any]]:
#     """
#     v3 listing.prices[]: price_variant
#       {type, money{amount,currency,raw_text}, period}
#     input internal: {currency, amount, period}
#     """
#     out: List[Dict[str, Any]] = []

#     def _variant_type(period: Optional[str]) -> str:
#         p = (period or "").lower().strip()
#         if p in ("one_time", "onetime", "one time"):
#             return "sale"
#         if p in ("month", "monthly"):
#             return "rent_long_month"
#         if p in ("year", "yearly", "annual"):
#             return "rent_long_year"
#         if p in ("night", "nightly", "day", "daily"):
#             return "rent_short_night"
#         return "unknown"

#     if isinstance(prices, list):
#         for p in prices:
#             if not isinstance(p, dict):
#                 continue
#             money = {
#                 "amount": p.get("amount"),
#                 "currency": p.get("currency"),
#                 "raw_text": None,
#             }
#             out.append(
#                 {
#                     "type": _variant_type(p.get("period")),
#                     "money": money,
#                     "period": p.get("period"),
#                 }
#             )

#     # ensure primary included (insert at 0 if not duplicate)
#     if isinstance(primary_price, dict) and primary_price:
#         money = {
#             "amount": primary_price.get("amount"),
#             "currency": primary_price.get("currency"),
#             "raw_text": None,
#         }
#         pv = {
#             "type": _variant_type(primary_price.get("period")),
#             "money": money,
#             "period": primary_price.get("period"),
#         }

#         key = (pv["type"], money.get("currency"), money.get("amount"), pv.get("period"))
#         seen = {
#             (
#                 x.get("type"),
#                 (x.get("money") or {}).get("currency"),
#                 (x.get("money") or {}).get("amount"),
#                 x.get("period"),
#             )
#             for x in out
#         }
#         if key not in seen:
#             out.insert(0, pv)

#     return out


# def _pick_whatsapp(broker: dict) -> str | None:
#     clr = broker.get("contact_links_raw")
#     if not isinstance(clr, dict):
#         return None
#     wa = clr.get("whatsapp")
#     if not isinstance(wa, list) or not wa:
#         return None
#     return _clean_str(wa[0])


# def _extract_lease_years_from_raw(raw_payload: Dict[str, Any], tenure_type: Optional[str]) -> Optional[int]:
#     """
#     BHI sometimes has: raw.payload.site_sections.general_information.<category>["leasehold period"] = "29 year(s)"
#     We parse it to int.
#     Only applies if tenure_type indicates leasehold.
#     """
#     t = (tenure_type or "").lower().strip()
#     if t != "leasehold":
#         return None

#     site_sections = raw_payload.get("site_sections")
#     if not isinstance(site_sections, dict):
#         return None

#     gi = site_sections.get("general_information")
#     if not isinstance(gi, dict):
#         return None

#     # pick "preferred" category if present
#     preferred = None
#     pcu = site_sections.get("primary_category_used")
#     if isinstance(pcu, dict):
#         preferred = _clean_str(pcu.get("general")) or _clean_str(pcu.get("preferred"))

#     candidates: List[str] = []
#     if preferred and isinstance(gi.get(preferred), dict):
#         v = gi[preferred].get("leasehold period")
#         if isinstance(v, str):
#             candidates.append(v)

#     # fallback: scan all categories
#     for _, block in gi.items():
#         if not isinstance(block, dict):
#             continue
#         v = block.get("leasehold period")
#         if isinstance(v, str):
#             candidates.append(v)

#     for txt in candidates:
#         m = re.search(r"(\d+)", txt)
#         if m:
#             try:
#                 return int(m.group(1))
#             except Exception:
#                 pass
#     return None


# def _extract_location(listing_in: Dict[str, Any], reso_in: Any) -> Dict[str, Any]:
#     """
#     Robust:
#     - prefer listing_in["location"] dict if present
#     - fallback to flat area/sub_area/latitude/longitude
#     - enrich region/country/city from RESO, BUT avoid duplicates (city==area/sub_area -> null)
#     """
#     loc_in = listing_in.get("location")
#     if not isinstance(loc_in, dict):
#         loc_in = {}

#     area = loc_in.get("area") or listing_in.get("area")
#     sub_area = loc_in.get("sub_area") or listing_in.get("sub_area")

#     lat = loc_in.get("latitude")
#     if lat is None:
#         lat = loc_in.get("lat")
#     if lat is None:
#         lat = listing_in.get("latitude")
#     lat = _to_float(lat)

#     lng = loc_in.get("longitude")
#     if lng is None:
#         lng = loc_in.get("lng")
#     if lng is None:
#         lng = listing_in.get("longitude")
#     lng = _to_float(lng)

#     city = loc_in.get("city")
#     region = loc_in.get("region")
#     country = loc_in.get("country")

#     # Enrich from RESO if missing
#     if isinstance(reso_in, dict):
#         if city is None:
#             city = reso_in.get("City")
#         if region is None:
#             region = reso_in.get("StateOrProvince")
#         if country is None:
#             country = reso_in.get("Country")

#     # Normalize duplicates: if city equals area/sub_area, drop it
#     city_n = _norm_str(city)
#     area_n = _norm_str(area)
#     sub_area_n = _norm_str(sub_area)
#     if city_n and (city_n == area_n or city_n == sub_area_n):
#         city = None

#     return {
#         "address_raw": loc_in.get("address_raw"),
#         "area": area,
#         "sub_area": sub_area,
#         "city": city,
#         "region": region,
#         "country": country,
#         "lat": lat,
#         "lng": lng,
#         "geo_source": loc_in.get("geo_source") or "unknown",
#         "geo_confidence": loc_in.get("geo_confidence") or "unknown",
#         "geo_precision_m": loc_in.get("geo_precision_m"),
#     }


# # ------------------------------------------------------------
# # main exporter
# # ------------------------------------------------------------

# def to_v3_record(rec: Dict[str, Any]) -> Dict[str, Any]:
#     listing_in = rec.get("listing") or {}
#     ingestion_in = rec.get("ingestion") or {}
#     hashes_in = rec.get("hashes") or {}
#     status_in = rec.get("status") or {}
#     raw_in = rec.get("raw") or {}
#     reso_in = rec.get("reso")

#     if not isinstance(listing_in, dict):
#         listing_in = {}
#     if not isinstance(ingestion_in, dict):
#         ingestion_in = {}
#     if not isinstance(hashes_in, dict):
#         hashes_in = {}
#     if not isinstance(status_in, dict):
#         status_in = {}
#     if not isinstance(raw_in, dict):
#         raw_in = {}

#     listing_key = _listing_key_from_record(rec)
#     listing_url = _listing_url_from_record(rec)

#     # --- media
#     images = listing_in.get("images") or []
#     media = _media_from_images(images)

#     # --- broker/contacts
#     broker = listing_in.get("broker") or {}
#     if not isinstance(broker, dict):
#         broker = {}

#     contacts = {
#         "agent_name": broker.get("broker_name"),
#         "agent_phone": broker.get("broker_phone"),
#         "agent_whatsapp": _pick_whatsapp(broker),
#         "agent_email": broker.get("broker_email"),
#         "agency_name": broker.get("agency_name"),
#     }

#     # --- hashes
#     raw_payload = raw_in.get("payload") or {}
#     if not isinstance(raw_payload, dict):
#         raw_payload = {}

#     raw_payload_hash = hashes_in.get("raw_payload_hash") or compute_raw_payload_hash(raw_payload)

#     chi_obj = hashes_in.get("canonical_hash_input")
#     if not isinstance(chi_obj, dict) or not chi_obj:
#         from scraper.core.hash_utils import build_canonical_hash_input
#         chi_obj = build_canonical_hash_input(listing_in)

#     canonical_hash_input_str = _stable_json_str(chi_obj)

#     canonical_content_hash = hashes_in.get("canonical_content_hash")
#     if not canonical_content_hash:
#         canonical_content_hash = compute_canonical_content_hash(chi_obj)

#     media_hash = compute_media_hash([m["url"] for m in media]) if media else None

#     # --- source url base domain
#     source_site_url = _domain(listing_url) or _domain(listing_in.get("source_url")) or "unknown"

#     # --- location (robust + enrich)
#     location = _extract_location(listing_in, reso_in)

#     # --- sizes
#     land_size_sqm = listing_in.get("land_size_sqm")
#     if land_size_sqm is None and isinstance(listing_in.get("specs"), dict):
#         land_size_sqm = listing_in["specs"].get("land_size_sqm")
#     land_size_sqm = _to_float(land_size_sqm)

#     land_size = {
#         "sqm": _to_int(land_size_sqm) if land_size_sqm is not None else None,
#         "raw_value": _to_int(land_size_sqm) if land_size_sqm is not None else None,
#         "raw_unit": "sqm" if land_size_sqm is not None else None,
#         "conversion_note": None,
#     }

#     building_size_sqm = listing_in.get("building_size_sqm")
#     if building_size_sqm is None and isinstance(listing_in.get("specs"), dict):
#         building_size_sqm = listing_in["specs"].get("building_size_sqm")
#     building_size_sqm = _to_float(building_size_sqm)

#     # --- beds/baths (fallback to specs)
#     beds = listing_in.get("bedrooms")
#     baths = listing_in.get("bathrooms")
#     if isinstance(listing_in.get("specs"), dict):
#         beds = beds if beds is not None else listing_in["specs"].get("bedrooms")
#         baths = baths if baths is not None else listing_in["specs"].get("bathrooms")
#     beds = _to_int(beds)
#     baths = _to_int(baths)

#     # --- price
#     price_obj = listing_in.get("price") if isinstance(listing_in.get("price"), dict) else {}
#     money = {
#         "amount": _to_int((price_obj or {}).get("amount")),
#         "currency": (price_obj or {}).get("currency"),
#         "raw_text": None,
#     }

#     variants = _prices_to_variants(listing_in.get("prices"), price_obj)

#     # --- tenure
#     tenure_type = listing_in.get("tenure_type")
#     lease_years = _extract_lease_years_from_raw(raw_payload, tenure_type)

#     tenure = {
#         "tenure_type": tenure_type,
#         "lease_years": lease_years,
#         "lease_expiry_year": None,
#         "extension_option": None,
#         "extension_terms_raw": None,
#     }

#     # --- listing_type inference
#     offer = (listing_in.get("offer_category") or "").lower().strip()
#     rentp = (listing_in.get("rent_period") or "").lower().strip()
#     if offer == "sale":
#         listing_type = "sale"
#     elif offer == "rent":
#         listing_type = "rent_long" if rentp in ("month", "year", "unknown", "") else "rent_short"
#     else:
#         listing_type = None

#     # --- status mapping (IMPORTANT: use preview.status_preview)
#     preview = raw_payload.get("preview") if isinstance(raw_payload.get("preview"), dict) else {}
#     status_preview = (preview.get("status_preview") or "").lower().strip()

#     current_status = (status_in.get("current_status") or "active").lower().strip()
#     last_change = (status_in.get("last_change_type") or "unknown").lower().strip()

#     if status_preview == "off_plan":
#         listing_status = "off_plan"
#     elif current_status in ("active",):
#         listing_status = "active"
#     elif current_status in ("inactive", "removed", "sold", "closed"):
#         listing_status = "inactive"
#     else:
#         listing_status = "unknown"

#     if last_change in ("new", "updated", "seen", "relisted"):
#         lifecycle = last_change
#     elif last_change == "removed":
#         lifecycle = "unknown"
#         listing_status = "removed"
#     else:
#         lifecycle = "unknown"

#     out: Dict[str, Any] = {
#         "schema_version": SCHEMA_VERSION_V3,

#         "ingestion": {
#             "scrape_run_id": ingestion_in.get("scrape_run_id"),
#             "captured_at": ingestion_in.get("captured_at"),
#             "first_seen_at": ingestion_in.get("first_seen_at"),
#             "last_seen_at": ingestion_in.get("last_seen_at"),
#             "source_timezone": None,
#             "http_status": None,
#             "content_type": None,
#             "parser_version": None,
#         },

#         "source": {
#             "source_name": listing_in.get("source") or rec.get("source_name") or "unknown",
#             "source_type": "broker_site",
#             "source_url": source_site_url,
#             "source_listing_id": _clean_str(listing_in.get("source_listing_id")) or listing_in.get("source_listing_id"),
#             "source_agent_name": contacts.get("agent_name"),
#             "source_agency_name": contacts.get("agency_name"),
#         },

#         "hashes": {
#             "raw_payload_hash": raw_payload_hash,
#             "canonical_hash_input": canonical_hash_input_str,  # string
#             "canonical_content_hash": canonical_content_hash,
#             "media_hash": media_hash,
#         },

#         "status": {
#             "listing_status": listing_status,
#             "lifecycle": lifecycle,
#         },

#         "listing": {
#             "listing_key": listing_key,
#             "listing_url": listing_url,

#             "title": listing_in.get("title"),
#             "description": listing_in.get("description"),
#             "language": None,

#             "listing_type": listing_type,

#             "price": money,
#             "prices": variants,

#             "property_type": listing_in.get("asset_class"),
#             "property_subtype": listing_in.get("property_subtype"),

#             "beds": beds,
#             "baths": baths,

#             "building_size_sqm": _to_int(building_size_sqm) if building_size_sqm is not None else None,
#             "land_size": land_size,

#             "tenure": tenure,
#             "location": location,

#             "media": media,

#             "contacts": contacts,
#         },

#         "identity": {
#             "normalized_property_id": None,
#             "candidate_property_ids": [],
#             "match_confidence": None,
#             "match_features_used": [],
#         },

#         "reso": reso_in if isinstance(reso_in, dict) else (reso_in or {}),

#         "raw": {
#             "payload": raw_payload,
#             "html_snippet": None,
#             "extraction_notes": None,
#         },
#     }

#     return out



# scraper/schema/v3_exporter.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from scraper.core.hash_utils import (
    compute_raw_payload_hash,
    compute_canonical_content_hash,
    compute_media_hash,
    sha256_str,
)

SCHEMA_VERSION_V3 = "3.0.0"


# ------------------------------------------------------------
# small helpers
# ------------------------------------------------------------

def _stable_json_str(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _to_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(float(x))
    except Exception:
        return None


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _clean_str(x: Any) -> Optional[str]:
    if not isinstance(x, str):
        return None
    s = x.strip()
    return s or None


def _domain(url: Optional[str]) -> Optional[str]:
    """
    https://bali-home-immo.com/path?a=1 -> https://bali-home-immo.com
    """
    u = _clean_str(url)
    if not u:
        return None
    try:
        p = urlparse(u)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    except Exception:
        pass
    return None


def _get_spec(listing_in: Dict[str, Any], key: str) -> Any:
    """
    Prefer top-level; fallback to listing_in["specs"].
    """
    if key in listing_in and listing_in.get(key) is not None:
        return listing_in.get(key)
    specs = listing_in.get("specs")
    if isinstance(specs, dict):
        return specs.get(key)
    return None


def _listing_key_from_record(rec: Dict[str, Any]) -> Optional[str]:
    listing = rec.get("listing") or {}
    if not isinstance(listing, dict):
        listing = {}

    lk = _clean_str(listing.get("listing_key")) or _clean_str(listing.get("ListingKey"))
    if lk:
        return lk

    source = _clean_str(listing.get("source"))
    sid = _clean_str(listing.get("source_listing_id"))
    if source and sid:
        return f"{source}:{sid}"

    url = (
        _clean_str(listing.get("listing_url"))
        or _clean_str(listing.get("source_url"))
        or _clean_str(listing.get("url"))
    )
    if url:
        return sha256_str(url)

    return None


def _listing_url_from_record(rec: Dict[str, Any]) -> Optional[str]:
    listing = rec.get("listing") or {}
    if not isinstance(listing, dict):
        listing = {}
    return (
        _clean_str(listing.get("listing_url"))
        or _clean_str(listing.get("source_url"))
        or _clean_str(listing.get("url"))
    )


def _media_from_images(images: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(images, list):
        return out
    order = 0
    for u in images:
        su = _clean_str(u)
        if not su:
            continue
        out.append(
            {
                "url": su,
                "order": order,
                "type": "image",
                "width": None,
                "height": None,
                "checksum": None,
                "phash": None,
            }
        )
        order += 1
    return out


def _prices_to_variants(prices: Any, primary_price: Any) -> List[Dict[str, Any]]:
    """
    v3 listing.prices[]: {type, money{amount,currency,raw_text}, period}
    """
    out: List[Dict[str, Any]] = []

    def _variant_type(period: Optional[str]) -> str:
        p = (period or "").lower().strip()
        if p in ("one_time", "onetime", "one time"):
            return "sale"
        if p in ("year", "yearly", "annual"):
            return "rent_long_year"
        if p in ("month", "monthly"):
            return "rent_long_month"
        if p in ("night", "nightly", "day", "daily"):
            return "rent_short_night"
        return "unknown"

    def _to_money_obj(p: dict) -> dict:
        return {
            "amount": _to_int(p.get("amount")),
            "currency": p.get("currency"),
            "raw_text": None,
        }

    if isinstance(prices, list):
        for p in prices:
            if not isinstance(p, dict):
                continue
            out.append(
                {
                    "type": _variant_type(p.get("period")),
                    "money": _to_money_obj(p),
                    "period": p.get("period"),
                }
            )

    # always ensure primary included AND placed at top (then we sort)
    if isinstance(primary_price, dict) and primary_price:
        pv = {
            "type": _variant_type(primary_price.get("period")),
            "money": _to_money_obj(primary_price),
            "period": primary_price.get("period"),
        }

        def _key(x: dict):
            m = x.get("money") or {}
            return (x.get("type"), m.get("currency"), m.get("amount"), x.get("period"))

        pk = _key(pv)
        out = [x for x in out if _key(x) != pk]
        out.insert(0, pv)

    # final sort: sale first, then yearly, then monthly, then short, then unknown
    priority = {
        "sale": 0,
        "rent_long_year": 1,
        "rent_long_month": 2,
        "rent_short_night": 3,
        "unknown": 9,
    }
    out.sort(key=lambda x: (priority.get(x.get("type"), 99), x.get("period") or ""))

    return out


def _pick_whatsapp(broker: dict) -> Optional[str]:
    clr = broker.get("contact_links_raw")
    if not isinstance(clr, dict):
        return None
    wa = clr.get("whatsapp")
    if not isinstance(wa, list) or not wa:
        return None
    return _clean_str(wa[0])


def _extract_location(listing_in: Dict[str, Any]) -> Dict[str, Any]:
    loc_in = listing_in.get("location")
    if not isinstance(loc_in, dict):
        loc_in = {}

    area = loc_in.get("area") or listing_in.get("area")
    sub_area = loc_in.get("sub_area") or listing_in.get("sub_area")

    lat = loc_in.get("latitude")
    if lat is None:
        lat = loc_in.get("lat")
    if lat is None:
        lat = listing_in.get("latitude")
    lat = _to_float(lat)

    lng = loc_in.get("longitude")
    if lng is None:
        lng = loc_in.get("lng")
    if lng is None:
        lng = listing_in.get("longitude")
    lng = _to_float(lng)

    return {
        "address_raw": loc_in.get("address_raw"),
        "area": area,
        "sub_area": sub_area,
        "city": loc_in.get("city"),
        "region": loc_in.get("region"),
        "country": loc_in.get("country"),
        "lat": lat,
        "lng": lng,
        "geo_source": loc_in.get("geo_source") or "unknown",
        "geo_confidence": loc_in.get("geo_confidence") or "unknown",
        "geo_precision_m": loc_in.get("geo_precision_m"),
    }


def _parse_lease_years_from_raw(raw_payload: Dict[str, Any]) -> Optional[int]:
    """
    BHI example:
      raw.payload.site_sections.general_information.leasehold["leasehold period"] == "22 year(s)"
    We parse first integer.
    """
    try:
        ss = raw_payload.get("site_sections")
        if not isinstance(ss, dict):
            return None

        gi = ss.get("general_information")
        if not isinstance(gi, dict):
            return None

        # prefer leasehold branch
        leasehold = gi.get("leasehold")
        if not isinstance(leasehold, dict):
            return None

        txt = leasehold.get("leasehold period")
        if not isinstance(txt, str):
            return None

        m = re.search(r"(\d+)", txt)
        if not m:
            return None

        return int(m.group(1))
    except Exception:
        return None


def _parse_year_from_text(x: Any) -> Optional[int]:
    if not isinstance(x, str):
        return None
    m = re.search(r"\b(19|20)\d{2}\b", x)
    if not m:
        return None
    try:
        return int(m.group(0))
    except Exception:
        return None


def _parse_bool_from_extension_text(x: Any) -> Optional[bool]:
    """
    Map extension text -> bool:
      'Available', 'Yes', 'Possible' -> True
      'No', 'Not available', 'None' -> False
      else -> None
    """
    if not isinstance(x, str):
        return None
    s = x.strip().lower()
    if not s:
        return None

    true_markers = ("available", "yes", "possible", "option", "extendable")
    false_markers = ("no", "not available", "unavailable", "none", "n/a")

    if any(t in s for t in true_markers):
        return True
    if any(t in s for t in false_markers):
        return False
    return None


def _extract_tenure_details_from_raw(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unify tenure enrichment for BHI + Propertia:
    - Propertia keys (from your sample):
        general_information.leasehold["lease years"] = "17"
        general_information.leasehold["end of lease"] = "October 2043"
        general_information.leasehold["extension"] = "Available"
    - BHI keys:
        general_information.<cat>["leasehold period"] = "22 year(s)"
    Returns dict with possibly:
      lease_years, lease_expiry_year, extension_option, extension_terms_raw
    """
    out: Dict[str, Any] = {
        "lease_years": None,
        "lease_expiry_year": None,
        "extension_option": None,
        "extension_terms_raw": None,
    }

    ss = raw_payload.get("site_sections")
    if not isinstance(ss, dict):
        return out

    gi = ss.get("general_information")
    if not isinstance(gi, dict):
        return out

    leasehold = gi.get("leasehold")
    if not isinstance(leasehold, dict):
        leasehold = {}

    # --- Propertia style
    # lease years
    ly = leasehold.get("lease years")
    out["lease_years"] = _to_int(ly) if ly is not None else None

    # end of lease -> year
    eol = leasehold.get("end of lease")
    out["lease_expiry_year"] = _parse_year_from_text(eol)

    # extension
    ext = leasehold.get("extension")
    ext_txt = _clean_str(ext) if isinstance(ext, str) else None
    out["extension_terms_raw"] = ext_txt
    out["extension_option"] = _parse_bool_from_extension_text(ext_txt)

    # --- BHI fallback (only if lease_years still empty)
    if out["lease_years"] is None:
        out["lease_years"] = _parse_lease_years_from_raw(raw_payload)

    return out


def _auto_fill_geo_signals(location: Dict[str, Any]) -> None:
    """
    If lat/lng exist but geo_source/confidence unknown -> assume it came from page map.
    (Better than unknown for client usage.)
    """
    if location.get("lat") is None or location.get("lng") is None:
        return

    gs = (location.get("geo_source") or "").strip().lower()
    gc = (location.get("geo_confidence") or "").strip().lower()

    if not gs or gs == "unknown":
        location["geo_source"] = "page_map"
    if not gc or gc == "unknown":
        location["geo_confidence"] = "high"


# ------------------------------------------------------------
# main exporter
# ------------------------------------------------------------

def to_v3_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    listing_in = rec.get("listing") or {}
    ingestion_in = rec.get("ingestion") or {}
    hashes_in = rec.get("hashes") or {}
    status_in = rec.get("status") or {}
    raw_in = rec.get("raw") or {}
    reso_in = rec.get("reso")

    if not isinstance(listing_in, dict):
        listing_in = {}
    if not isinstance(ingestion_in, dict):
        ingestion_in = {}
    if not isinstance(hashes_in, dict):
        hashes_in = {}
    if not isinstance(status_in, dict):
        status_in = {}
    if not isinstance(raw_in, dict):
        raw_in = {}
    if not isinstance(reso_in, dict):
        reso_in = {}

    listing_key = _listing_key_from_record(rec)
    listing_url = _listing_url_from_record(rec)

    # --- media
    images = listing_in.get("images") or []
    media = _media_from_images(images)

    # --- contacts from broker
    broker = listing_in.get("broker") or {}
    if not isinstance(broker, dict):
        broker = {}

    contacts = {
        "agent_name": broker.get("broker_name"),
        "agent_phone": broker.get("broker_phone"),
        "agent_whatsapp": _pick_whatsapp(broker),
        "agent_email": broker.get("broker_email"),
        "agency_name": broker.get("agency_name"),
    }

    # --- raw payload
    raw_payload = raw_in.get("payload") or {}
    if not isinstance(raw_payload, dict):
        raw_payload = {}

    # --- location
    location = _extract_location(listing_in)

    # enrich location from RESO if missing
    if location.get("city") is None:
        location["city"] = reso_in.get("City")
    if location.get("region") is None:
        location["region"] = reso_in.get("StateOrProvince")
    if location.get("country") is None:
        location["country"] = reso_in.get("Country")

    # auto-geo signals
    _auto_fill_geo_signals(location)

    # --- primary price (money)
    price_obj = listing_in.get("price") if isinstance(listing_in.get("price"), dict) else {}
    money = {
        "amount": _to_int((price_obj or {}).get("amount")),
        "currency": (price_obj or {}).get("currency"),
        "raw_text": None,
    }

    # --- variants
    variants = _prices_to_variants(listing_in.get("prices"), price_obj)

    # --- listing_type inference (based on actual variants)
    has_sale = any((v.get("type") == "sale") for v in variants)
    has_rent = any((v.get("type") or "").startswith("rent_") for v in variants)

    if has_sale and has_rent:
        listing_type = "sale_and_rent"
    elif has_sale:
        listing_type = "sale"
    elif has_rent:
        has_short = any(v.get("type") == "rent_short_night" for v in variants)
        listing_type = "rent_short" if has_short else "rent_long"
    else:
        listing_type = None

    # --- sizes
    land_size_sqm = _to_int(_get_spec(listing_in, "land_size_sqm"))
    land_size = {
        "sqm": land_size_sqm,
        "raw_value": land_size_sqm,
        "raw_unit": "sqm" if land_size_sqm is not None else None,
        "conversion_note": None,
    }

    building_size_sqm = _to_int(_get_spec(listing_in, "building_size_sqm"))

    # --- tenure
    # tenure_type = listing_in.get("tenure_type")
    # lease_years = _to_int(listing_in.get("lease_years"))
    # if (lease_years is None) and (str(tenure_type or "").lower().strip() == "leasehold"):
    #     lease_years = _parse_lease_years_from_raw(raw_payload)

    # tenure = {
    #     "tenure_type": tenure_type,
    #     "lease_years": lease_years,
    #     "lease_expiry_year": _to_int(listing_in.get("lease_expiry_year")),
    #     "extension_option": listing_in.get("extension_option"),
    #     "extension_terms_raw": listing_in.get("extension_terms_raw"),
    # }

    # --- tenure
    tenure_type = listing_in.get("tenure_type")

    # keep explicit listing fields if already present
    lease_years = _to_int(listing_in.get("lease_years"))
    lease_expiry_year = _to_int(listing_in.get("lease_expiry_year"))
    extension_option = listing_in.get("extension_option")
    extension_terms_raw = listing_in.get("extension_terms_raw")

    # ONLY enrich from raw when tenure_type == leasehold and fields still empty
    if str(tenure_type or "").lower().strip() == "leasehold":
        raw_tenure = _extract_tenure_details_from_raw(raw_payload)

        if lease_years is None:
            lease_years = raw_tenure.get("lease_years")
        if lease_expiry_year is None:
            lease_expiry_year = raw_tenure.get("lease_expiry_year")
        if extension_option is None:
            extension_option = raw_tenure.get("extension_option")
        if extension_terms_raw is None:
            extension_terms_raw = raw_tenure.get("extension_terms_raw")

    tenure = {
        "tenure_type": tenure_type,
        "lease_years": lease_years,
        "lease_expiry_year": lease_expiry_year,
        "extension_option": extension_option,
        "extension_terms_raw": extension_terms_raw,
    }

    # --- status mapping
    current_status = (status_in.get("current_status") or "active").lower().strip()
    last_change = (status_in.get("last_change_type") or "unknown").lower().strip()

    if current_status in ("active", "off_plan", "off-plan"):
        listing_status = "active"
    elif current_status in ("inactive", "removed", "sold", "closed"):
        listing_status = "inactive"
    else:
        listing_status = "unknown"

    if last_change in ("new", "updated", "seen", "relisted"):
        lifecycle = last_change
    elif last_change == "removed":
        lifecycle = "unknown"
        listing_status = "removed"
    else:
        lifecycle = "unknown"

    # --- hashes
    raw_payload_hash = hashes_in.get("raw_payload_hash") or compute_raw_payload_hash(raw_payload)

    chi_obj = hashes_in.get("canonical_hash_input")
    if not isinstance(chi_obj, dict) or not chi_obj:
        from scraper.core.hash_utils import build_canonical_hash_input
        chi_obj = build_canonical_hash_input(listing_in)

    canonical_hash_input_str = _stable_json_str(chi_obj)

    canonical_content_hash = hashes_in.get("canonical_content_hash")
    if not canonical_content_hash:
        canonical_content_hash = compute_canonical_content_hash(chi_obj)

    media_hash = compute_media_hash([m["url"] for m in media]) if media else None

    # --- source block (base domain)
    source_site_url = _domain(listing_url) or _domain(listing_in.get("source_url")) or "unknown"

    beds = _to_int(_get_spec(listing_in, "bedrooms"))
    baths = _to_int(_get_spec(listing_in, "bathrooms"))

    out: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_V3,

        "ingestion": {
            "scrape_run_id": ingestion_in.get("scrape_run_id"),
            "captured_at": ingestion_in.get("captured_at"),
            "first_seen_at": ingestion_in.get("first_seen_at"),
            "last_seen_at": ingestion_in.get("last_seen_at"),
            "source_timezone": None,
            "http_status": None,
            "content_type": None,
            "parser_version": None,
        },

        "source": {
            "source_name": listing_in.get("source") or rec.get("source_name") or "unknown",
            "source_type": "broker_site",
            "source_url": source_site_url,
            "source_listing_id": _clean_str(listing_in.get("source_listing_id")) or listing_in.get("source_listing_id"),
            "source_agent_name": contacts.get("agent_name"),
            "source_agency_name": contacts.get("agency_name"),
        },

        "hashes": {
            "raw_payload_hash": raw_payload_hash,
            "canonical_hash_input": canonical_hash_input_str,
            "canonical_content_hash": canonical_content_hash,
            "media_hash": media_hash,
        },

        "status": {
            "listing_status": listing_status,
            "lifecycle": lifecycle,
        },

        "listing": {
            "listing_key": listing_key,
            "listing_url": listing_url,

            "title": listing_in.get("title"),
            "description": listing_in.get("description"),
            "language": None,

            "listing_type": listing_type,

            "price": money,
            "prices": variants,

            "property_type": listing_in.get("asset_class"),
            "property_subtype": listing_in.get("property_subtype"),

            "beds": beds,
            "baths": baths,

            "building_size_sqm": building_size_sqm,
            "land_size": land_size,

            "tenure": tenure,
            "location": location,

            "media": media,

            "contacts": contacts,
        },

        "identity": {
            "normalized_property_id": None,
            "candidate_property_ids": [],
            "match_confidence": None,
            "match_features_used": [],
        },

        "reso": reso_in,

        "raw": {
            "payload": raw_payload,
            "html_snippet": None,
            "extraction_notes": None,
        },
    }

    return out