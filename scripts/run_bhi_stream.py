# from __future__ import annotations
# import os

# from scraper.sites.bali_home_immo.adapter import BaliHomeImmoAdapter
# from scraper.core.jsonl import append_jsonl  # sesuaikan nama function di jsonl.py


# BASE_URL = "https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false"


# os.makedirs("out", exist_ok=True)
# def main(out_path: str = "out/bhi.jsonl", limit: int | None = None):
#     adapter = BaliHomeImmoAdapter()
#     n = 0

#     for preview in adapter.iter_previews(BASE_URL):
#         detail = adapter.fetch_detail(preview)
#         listing = adapter.normalize(preview, detail)

#         append_jsonl(out_path, listing)

#         n += 1
#         if n % 20 == 0:
#             print(f"[BHI] written: {n}")
#         if limit and n >= limit:
#             break

#     print(f"[BHI] DONE written: {n} -> {out_path}")


# if __name__ == "__main__":
#     main(limit=30)  # test dulu 30


from scraper.sites.bali_home_immo.adapter import BaliHomeImmoAdapter
from scraper.core.runner import run_site_stream

def main(limit=None):
    adapter = BaliHomeImmoAdapter()
    start_url = "https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false"
    stats = run_site_stream(
        adapter=adapter,
        start_url=start_url,
        out_path="out/bhi.jsonl",
        state_path="state/bhi.json",
        limit=limit
    )
    print(stats)

if __name__ == "__main__":
    main(limit=30)