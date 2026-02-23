# from __future__ import annotations
# from typing import Dict, Any, Iterable

# from scraper.core.normalizer import merge_preview_into_detail, finalize_listing
# from scraper.core.reso_mapper import to_reso  
# from datetime import datetime, timezone
# from scraper.core.reso_mapper import to_reso
# from .crawl import iter_list_items
# from .detail_page import parse_detail_page


# class BaliHomeImmoAdapter:
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.scrape_run_id = datetime.now(timezone.utc).isoformat()

#     source_key = "bali-home-immo"

#     def iter_previews(self, start_url: str) -> Iterable[Dict[str, Any]]:
#         yield from iter_list_items(start_url, delay=0.8, max_pages=500)

#     def fetch_detail(self, preview: Dict[str, Any]) -> Dict[str, Any]:
#         listing = parse_detail_page(preview)
#         # parse_detail_page butuh item{"url","source_listing_id"} → preview sudah punya itu
#         listing["reso"] = to_reso(
#             listing,
#             scrape_run_id=self.scrape_run_id
#         )
#         # return parse_detail_page(preview)

#     def normalize(self, preview: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
#         merged = merge_preview_into_detail(preview, detail)
#         merged = finalize_listing(merged)

#         # RESO payload
#         merged["reso"] = to_reso(merged)
#         return merged




# # class BaliHomeImmoAdapter(BaseAdapter):

# #     source_key = "bali-home-immo"

# #     def __init__(self, *args, **kwargs):
# #         super().__init__(*args, **kwargs)
# #         self.scrape_run_id = datetime.now(timezone.utc).isoformat()

# #     def fetch_detail(self, preview):
# #         listing = parse_detail_page(preview)

# #         # attach RESO here

# #         return listing



from __future__ import annotations
from typing import Dict, Any, Iterable
from datetime import datetime, timezone

from scraper.core.normalizer import merge_preview_into_detail, finalize_listing
from scraper.core.reso_mapper import to_reso
from .crawl import iter_list_items
from .detail_page import parse_detail_page


class BaliHomeImmoAdapter:

    source_key = "bali-home-immo"

    def __init__(self):
        self.scrape_run_id = datetime.now(timezone.utc).isoformat()

    def iter_previews(self, start_url: str) -> Iterable[Dict[str, Any]]:
        yield from iter_list_items(start_url, delay=0.8, max_pages=500)

    def fetch_detail(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        # PURE parsing layer
        return parse_detail_page(preview)

    def normalize(
        self,
        preview: Dict[str, Any],
        detail: Dict[str, Any]
    ) -> Dict[str, Any]:

        # merge preview + detail
        merged = merge_preview_into_detail(preview, detail)

        # finalize listing (timestamps, hash, status)
        merged = finalize_listing(merged)

        # attach RESO payload AFTER finalization
        merged["reso"] = to_reso(
            merged,
            scrape_run_id=self.scrape_run_id
        )

        return merged