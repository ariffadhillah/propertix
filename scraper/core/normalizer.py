from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict


def finalize_listing(listing: Dict[str, Any]) -> Dict[str, Any]:
    # ... rapikan field2 dulu ...

    # safety: images unique (opsional)
    if isinstance(listing.get("images"), list):
        listing["images"] = list(dict.fromkeys([x for x in listing["images"] if x]))

    listing["content_hash"] = compute_content_hash(listing)
    return listing


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_text(s: Any) -> Any:
    """Normalize whitespace for text fields."""
    if not isinstance(s, str):
        return s
    s = s.replace("\xa0", " ")
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _round_num(x: Any) -> Any:
    """Make numeric values stable (avoid 2 vs 2.0 issues)."""
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        # keep enough precision for prices/coords but avoid noise
        return round(x, 6)
    return x


def _canonical(obj: Any) -> Any:
    """
    Recursively canonicalize dict/list/scalars so hashing is deterministic.
    - dict keys sorted
    - lists sorted when possible (for prices/images)
    - text normalized
    - numbers rounded
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        # normalize keys + values
        items = {}
        for k, v in obj.items():
            # keep keys as-is but normalize string keys spacing
            kk = _norm_text(k) if isinstance(k, str) else k
            items[kk] = _canonical(v)
        # return as normal dict; json.dumps(sort_keys=True) will order keys
        return items

    if isinstance(obj, list):
        canon_list = [_canonical(x) for x in obj]

        # special: list of strings -> sort unique (images)
        if all(isinstance(x, str) for x in canon_list):
            uniq = list(dict.fromkeys([_norm_text(x) for x in canon_list if x]))
            return sorted(uniq)

        # special: list of dict prices -> sort by (period, currency, amount)
        if all(isinstance(x, dict) for x in canon_list):
            def _price_key(d: dict):
                return (
                    str(d.get("period") or ""),
                    str(d.get("currency") or ""),
                    float(d.get("amount") or 0.0),
                )
            # if looks like price dicts
            if any("amount" in d or "period" in d for d in canon_list):
                return sorted(canon_list, key=_price_key)

        return canon_list

    if isinstance(obj, str):
        return _norm_text(obj)

    # numbers / others
    return _round_num(obj)


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

    stable = _canonical(stable)

    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()