from scraper.sites.bali_home_immo.list_items import parse_list_page

if __name__ == "__main__":
    url = "https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false&page=1"
    items = parse_list_page(url)

    print("count:", len(items))
    for it in items[:5]:
        print("-" * 60)
        print(it["source_listing_id"], it["title"])
        print("url:", it["url"])
        print("thumb:", it["thumb"])
        print("price_preview:", it["price_preview"], it["price_category_preview"])
        print("loc:", it["location_preview"])