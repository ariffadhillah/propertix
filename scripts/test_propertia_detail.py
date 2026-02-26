# scripts/test_propertia_detail.py
import json
from scraper.sites.propertia.detail_page import parse_detail_page

def main():
    url = "https://propertia.com/property/charming-4-bedroom-ready-to-move-in-family-villa-in-prime-canggu/"

    # minimal item object (sesuai kontrak parse_detail_page)
    item = {
        "source_listing_id": "test-1",
        "url": url,
    }

    listing = parse_detail_page(item)

    # Print ringkasan dulu biar gampang cek
    keys = [
        "source_listing_id", "source_url", "title",
        "offer_category", "tenure_type", "rent_period",
        "asset_class", "property_subtype",
        "price", "prices",
        "bedrooms", "bathrooms", "land_size_sqm", "building_size_sqm",
        "location", "images",
        "broker_name", "broker_phone", "broker_email", "agency_name",
    ]

    print("\n=== SUMMARY ===")
    for k in keys:
        print(f"{k}: {listing.get(k)}")

    print("\n=== RAW BREADCRUMB ===")
    raw = listing.get("raw") or {}
    print(raw.get("breadcrumb"))

    # Dump full JSON biar bisa inspeksi lengkap
    print("\n=== FULL JSON ===")
    print(json.dumps(listing, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()