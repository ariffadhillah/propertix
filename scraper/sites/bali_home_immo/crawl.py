# from typing import List, Dict, Any
# import time

# from .list_items import parse_list_page


# def crawl_all(base_url: str, delay: float = 1.0, max_pages: int = 200):

#     all_items: List[Dict[str, Any]] = []
#     seen_ids = set()

#     page = 1

#     while page <= max_pages:
#         url = f"{base_url}&page={page}"
#         print(f"[BHI] Crawling page {page}")

#         items = parse_list_page(url)

#         if not items:
#             print(f"[BHI] No items found on page {page}. Stop.")
#             break

#         new_count = 0

#         for item in items:
#             if item["source_listing_id"] in seen_ids:
#                 continue
#             seen_ids.add(item["source_listing_id"])
#             all_items.append(item)
#             new_count += 1

#         print(f"[BHI] Page {page}: {new_count} new items")

#         page += 1
#         time.sleep(delay)

#     print(f"[BHI] TOTAL COLLECTED: {len(all_items)}")
#     return all_items



from typing import Dict, Any, Generator
import time

from .list_items import parse_list_page


def iter_list_items(base_url: str, delay: float = 1.0, max_pages: int = 500) -> Generator[Dict[str, Any], None, None]:

    seen_ids = set()
    page = 1

    while page <= max_pages:
        url = f"{base_url}&page={page}"
        print(f"[BHI] Crawling page {page}")

        items = parse_list_page(url)

        if not items:
            print(f"[BHI] No items found on page {page}. Stop.")
            break

        for item in items:
            lid = item["source_listing_id"]
            if lid in seen_ids:
                continue
            seen_ids.add(lid)
            yield item

        page += 1
        time.sleep(delay)