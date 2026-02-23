from scraper.sites.bali_home_immo.detail_page import parse_detail_page

if __name__ == "__main__":
    item = {
        # "url": "https://bali-home-immo.com/realestate-property/for-sale/villa/leasehold/ungasan/charming-2-bedroom-modern-villa-for-sale-and-rent-in-ungasan-rf6236b",
        # "url": "https://bali-home-immo.com/realestate-property/for-sale/villa/freehold/ungasan/off-plan-3-units-of-1-bedroom-villa-for-sale-freehold-and-leasehold-in-bali-ungasan-rf7664",
        # "url": "https://bali-home-immo.com/realestate-property/for-sale/villa/freehold/nusa-dua/modern-tropical-2-bedroom-villa-with-private-pool-fully-furnished-ready-to-live-rf9597",
        "url": "https://bali-home-immo.com/realestate-property/for-sale/villa/leasehold/ungasan/charming-2-bedroom-modern-villa-for-sale-and-rent-in-ungasan-rf6236b",
        "source_listing_id": "test-id"
    }
    data = parse_detail_page(item)
    print("title:", data["title"])
    print("description preview:", (data["description"] or ""))
    print("description paragraphs:", (data["description"] or "").count("\n\n") + 1 if data["description"] else 0)
    # print("images:", data["images"])
    # print("images count:", len(data["images"]))
    # print("first image:", data["images"][0] if data["images"] else None)


# import json
# from pprint import pprint
# from scraper.sites.bali_home_immo.detail_page import parse_detail_page

# if __name__ == "__main__":
#     item = {
#         "url": "https://bali-home-immo.com/realestate-property/for-sale/villa/freehold/nusa-dua/modern-tropical-2-bedroom-villa-with-private-pool-fully-furnished-ready-to-live-rf9597",
#         "source_listing_id": "RF9597"
#     }

#     data = parse_detail_page(item)

#     print("\n================ INTERNAL STRUCTURE ================\n")
#     pprint(data)

#     print("\n================ RESO STRUCTURE ================\n")
#     pprint(data.get("reso"))

#     print("\n================ JSON (Pretty) ================\n")
    # print(json.dumps(data, indent=2, ensure_ascii=False))