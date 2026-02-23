from __future__ import annotations
import hashlib
import orjson
from typing import Any, Dict

def stable_hash(obj: Dict[str, Any]) -> str:
    # Sort keys to ensure stability
    b = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(b).hexdigest()

def hash_for_listing_change(payload: Dict[str, Any]) -> str:
    # Remove volatile fields before hashing
    volatile = {"first_seen_at", "last_seen_at", "content_hash"}
    filtered = {k: v for k, v in payload.items() if k not in volatile}
    return stable_hash(filtered)