# from typing import Iterable
# import requests


# def iter_pages(start_url: str) -> Iterable[str]:
#     """
#     Loop page=1,2,3 sampai tidak ada listing lagi.
#     """
#     page = 1

#     while True:
#         url = start_url.replace("page=1", f"page={page}")
#         print("[bali-home-immo] checking page:", page)

#         r = requests.get(url, timeout=30)
#         if r.status_code != 200:
#             break

#         # stop kalau tidak ada listing card lagi
#         if "realestate-property" not in r.text:
#             break

#         yield url
#         page += 1