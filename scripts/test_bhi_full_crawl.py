from scraper.sites.bali_home_immo.crawl import crawl_all

if __name__ == "__main__":
    base_url = "https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false"

    items = crawl_all(base_url)

    print("TOTAL:", len(items))