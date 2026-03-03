# # scripts/test_propertia_detail.py
# import json
# from scraper.sites.propertia.detail_page import parse_detail_page

# def main():

#     # minimal item object (sesuai kontrak parse_detail_page)


#     item = {
#         "source_listing_id": "test-1",
#         "source_url": url,
#     }

#     listing = parse_detail_page(item)

#     print("\n=== FULL JSON ===")
#     print(json.dumps(listing, ensure_ascii=False, indent=2))

# if __name__ == "__main__":
#     main()


import json
from scraper.sites.propertia.detail_page import parse_detail_page

def main():
    # url = "https://propertia.com/property/https-propertia-com-property-stylish-freehold-modern-villa-in-pecatu/"
    # url = "https://propertia.com/property/turn-key-contemporary-tropical-villa-in-ubud/"
    # url = "https://propertia.com/property/incredible-freehold-villa-in-the-heart-of-umalas/"
    # url = "https://propertia.com/property/balangan-land-offering-the-perfect-size-for-development/"
    # url = "https://propertia.com/property/stylish-tropical-2-bendroom-villa-in-suluban/"
    # url = "https://propertia.com/property/rare-freehold-land-in-bingin-offering-exceptional-location-and-strong-investment-potential/"
    url = "https://propertia.com/property/beautiful-3-bedroom-japanese-scandinavian-villa-in-umalas/"
    item = {
        "source_listing_id": "test-1",
        "source_url": url,
        "url": url,  # hapus ini kalau kamu sudah fix parser pakai source_url
    }

    listing = parse_detail_page(item)

    print("\n=== SUMMARY ===")
    keys = [
        "source_listing_id","source_url","title",
        "offer_category","tenure_type","rent_period",
        "asset_class","property_subtype",
        "price","bedrooms","bathrooms","land_size_sqm","building_size_sqm",
        "location",
        "broker_name","broker_phone","broker_email","agency_name",
    ]
    for k in keys:
        print(f"{k}: {listing.get(k)}")

    print("\n=== RAW BREADCRUMB ===")
    print(listing.get("raw", {}).get("breadcrumb", []))

    print("\n=== FULL JSON ===")
    print(json.dumps(listing, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()