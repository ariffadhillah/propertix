from typing import Dict, Any


def ensure_broker_block(listing: Dict[str, Any]) -> None:
    """
    Ensure listing["broker"] exists with required schema.
    This is schema enforcement only — no scraping logic.
    """

    broker = listing.get("broker")
    if not isinstance(broker, dict):
        broker = {}
        listing["broker"] = broker

    # Required identity fields
    broker.setdefault("broker_name", None)
    broker.setdefault("broker_phone_raw", None)
    broker.setdefault("broker_phone", None)
    broker.setdefault("broker_email", None)
    broker.setdefault("broker_profile_url", None)
    broker.setdefault("agency_name", None)

    # Raw contact links structure
    clr = broker.get("contact_links_raw")
    if not isinstance(clr, dict):
        clr = {}
        broker["contact_links_raw"] = clr

    clr.setdefault("mailto", [])
    clr.setdefault("tel", [])
    clr.setdefault("whatsapp", [])
    clr.setdefault("messenger", [])
    clr.setdefault("form", [])
    clr.setdefault("other", [])