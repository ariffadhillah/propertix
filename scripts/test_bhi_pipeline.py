from scraper.sites.bali_home_immo.crawl import iter_list_items
from scraper.sites.bali_home_immo.detail_page import parse_detail_page


BASE_URL = "https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false"


def merge_preview_into_detail(preview: dict, detail: dict) -> dict:
    """
    Merge list preview data into detail payload.
    """
    detail["intent"] = preview.get("intent_preview")
    detail["property_type"] = detail.get("property_type") or "villa"

    # merge lat/lon from list
    if preview.get("location_preview"):
        detail["location"] = detail.get("location") or {}
        detail["location"]["latitude"] = preview["location_preview"].get("latitude")
        detail["location"]["longitude"] = preview["location_preview"].get("longitude")
        detail["location"]["area"] = preview["location_preview"].get("area")

    return detail


if __name__ == "__main__":

    for preview in iter_list_items(BASE_URL):

        detail = parse_detail_page(preview)

        listing = merge_preview_into_detail(preview, detail)

        print("----")
        print(listing["source_listing_id"], listing["title"])
        print("Lat:", listing["location"])
        break