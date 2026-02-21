# # import requests
# # import time
# # import json
# # from detail_page_scrape import scrape_property_detail
# # import os
# # from datetime import datetime, timezone
# # import hashlib

# # BASE = "https://propertia.com/wp-admin/admin-ajax.php"

# # HEADERS = {
# #     'User-Agent': 'Mozilla/5.0',
# #     'Accept': 'application/json, text/javascript, */*; q=0.01',
# #     'X-Requested-With': 'XMLHttpRequest',
# #     'Referer': 'https://propertia.com/search-results-3/?paged=1&listing_page_id=23498'
# # }

# # PARAMS_TEMPLATE = {
# #     "listing_page_id": "23498",
# #     "action": "houzez_half_map_listings",
# #     "sortby": "d_date",
# #     "item_layout": "v1",
# #     "layout_view": "grid",
# #     "is_pagination_request": "false"
# # }

# # def run():
# #     run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_propertia"

# #     out_dir = os.path.join("output", "propertia")
# #     os.makedirs(out_dir, exist_ok=True)

# #     jsonl_path = os.path.join(out_dir, f"run_{run_id}.jsonl")
# #     summary_path = os.path.join(out_dir, f"run_{run_id}_summary.json")

# #     summary = {
# #         "source_site": "propertia",
# #         "run_id": run_id,
# #         "started_at": datetime.now(timezone.utc).isoformat(),
# #         "pages_fetched": 0,
# #         "urls_collected": 0,
# #         "detail_success": 0,
# #         "detail_failed": 0,
# #         "errors": [],
# #     }

# #     def canonical_for_hash(rec: dict) -> dict:
# #         # field penting untuk change detection
# #         return {
# #             "title": rec.get("title"),
# #             "price": rec.get("price"),
# #             "years": rec.get("years"),
# #             "bedrooms": rec.get("bedrooms"),
# #             "bathrooms": rec.get("bathrooms"),
# #             "building_size_value": rec.get("building_size_value"),
# #             "building_size_unit": rec.get("building_size_unit"),
# #             "land_size_value": rec.get("land_size_value"),
# #             "land_size_unit": rec.get("land_size_unit"),
# #             "area": rec.get("area"),
# #             "address": rec.get("address"),
# #             "property_status": rec.get("property_status"),
# #             "property_type": rec.get("property_type"),
# #             "labels": rec.get("labels"),
# #             "features": rec.get("features"),
# #             # images & description biasanya besar; untuk MVP boleh tidak masuk hash
# #         }

# #     def content_hash(rec: dict) -> str:
# #         raw = json.dumps(canonical_for_hash(rec), sort_keys=True, ensure_ascii=False)
# #         return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# #     page = 1
# #     unique_urls = set()

# #     # =====================
# #     # STEP 1 — COLLECT URLS
# #     # =====================
# #     while True:
# #         print(f"\nCollecting page {page}")

# #         params = PARAMS_TEMPLATE.copy()
# #         params["paged"] = page

# #         try:
# #             response = requests.get(BASE, headers=HEADERS, params=params, timeout=30)
# #             response.raise_for_status()
# #             data = response.json()
# #             summary["pages_fetched"] += 1
# #         except Exception as e:
# #             summary["errors"].append({"stage": "collect", "page": page, "error": str(e)})
# #             print("Collect error:", e)
# #             break

# #         properties = data.get("properties", [])
# #         if not properties:
# #             print("No more properties.")
# #             break

# #         for prop in properties:
# #             url = prop.get("url")
# #             if url:
# #                 unique_urls.add(url)

# #         page += 1
# #         time.sleep(1)

# #     unique_urls = list(unique_urls)
# #     summary["urls_collected"] = len(unique_urls)
# #     print("\nTOTAL URLS:", len(unique_urls))

# #     # =====================
# #     # STEP 2 — SCRAPE DETAIL
# #     # =====================
# #     for i, url in enumerate(unique_urls, 1):
# #         print(f"\n[{i}/{len(unique_urls)}] Scraping detail")

# #         try:
# #             detail_data = scrape_property_detail(url)  # pakai nama detail_data biar jelas
# #             if not detail_data:
# #                 summary["detail_failed"] += 1
# #                 continue

# #             # dedupe_key
# #             pid = detail_data.get("property_id")
# #             listing_url = detail_data.get("url") or url

# #             detail_data["listing_url"] = listing_url
# #             detail_data["external_id"] = pid  # optional, lebih jelas utk Django

# #             if pid:
# #                 detail_data["dedupe_key"] = f"propertia:{pid}"
# #             else:
# #                 detail_data["dedupe_key"] = f"propertia:{listing_url}"

# #             # content hash
# #             detail_data["content_hash"] = content_hash(detail_data)

# #             # (opsional tapi bagus) metadata minimal per record
# #             detail_data["source_site"] = "propertia"
# #             detail_data["run_id"] = run_id
# #             detail_data["scraped_at"] = datetime.now(timezone.utc).isoformat()

# #             with open(jsonl_path, "a", encoding="utf-8") as f:
# #                 f.write(json.dumps(detail_data, ensure_ascii=False, sort_keys=True) + "\n")

# #             summary["detail_success"] += 1

# #         except Exception as e:
# #             summary["detail_failed"] += 1
# #             summary["errors"].append({"stage": "detail", "url": url, "error": str(e)})
# #             print("Error scraping:", url, e)

# #         time.sleep(1)  # anti-ban

# #     summary["finished_at"] = datetime.now(timezone.utc).isoformat()

# #     with open(summary_path, "w", encoding="utf-8") as f:
# #         json.dump(summary, f, ensure_ascii=False, indent=2)

# #     print("\nDONE")
# #     print("JSONL   :", jsonl_path)
# #     print("SUMMARY :", summary_path)

# #     return summary


# # # if __name__ == "__main__":
# # #     results = run()
    

# # #     # preview sample
# # #     from pprint import pprint
# # #     pprint(results[:2])



# # if __name__ == "__main__":
# #     run()




# import os
# import time
# import json
# import hashlib
# from datetime import datetime, timezone
# from typing import Optional, Dict, Any, Tuple

# import requests

# from detail_page_scrape import scrape_property_detail

# BASE = "https://propertia.com/wp-admin/admin-ajax.php"

# HEADERS = {
#     "User-Agent": "Mozilla/5.0",
#     "Accept": "application/json, text/javascript, */*; q=0.01",
#     "X-Requested-With": "XMLHttpRequest",
#     "Referer": "https://propertia.com/search-results-3/?paged=1&listing_page_id=23498",
# }

# PARAMS_TEMPLATE = {
#     "listing_page_id": "23498",
#     "action": "houzez_half_map_listings",
#     "sortby": "d_date",
#     "item_layout": "v1",
#     "layout_view": "grid",
#     "is_pagination_request": "false",
# }


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).isoformat()


# def canonical_for_hash(rec: Dict[str, Any]) -> Dict[str, Any]:
#     """Field penting untuk change detection. Jangan masukkan run_id/scraped_at."""
#     return {
#         "title": rec.get("title"),
#         "price": rec.get("price"),
#         "years": rec.get("years"),
#         "bedrooms": rec.get("bedrooms"),
#         "bathrooms": rec.get("bathrooms"),
#         "building_size_value": rec.get("building_size_value"),
#         "building_size_unit": rec.get("building_size_unit"),
#         "land_size_value": rec.get("land_size_value"),
#         "land_size_unit": rec.get("land_size_unit"),
#         "area": rec.get("area"),
#         "address": rec.get("address"),
#         "property_status": rec.get("property_status"),
#         "property_type": rec.get("property_type"),
#         "labels": rec.get("labels"),
#         "features": rec.get("features"),
#         "neighborhood": rec.get("neighborhood"),
#         # images & description biasanya besar; untuk MVP boleh tidak masuk hash
#     }


# def compute_content_hash(rec: Dict[str, Any]) -> str:
#     raw = json.dumps(canonical_for_hash(rec), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
#     return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# def make_run_id(site: str) -> str:
#     return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_{site}"


# def ensure_dir(path: str) -> None:
#     os.makedirs(path, exist_ok=True)


# def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
#     with open(path, "a", encoding="utf-8") as f:
#         f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


# def fetch_listing_page(page: int, timeout: int = 30) -> Optional[Dict[str, Any]]:
#     """Fetch halaman listing dari Houzez AJAX. Return JSON dict atau None bila gagal/blocked."""
#     params = PARAMS_TEMPLATE.copy()
#     params["paged"] = page

#     try:
#         resp = requests.get(BASE, headers=HEADERS, params=params, timeout=timeout)
#         # blocked detection ringan
#         if resp.status_code in (403, 429):
#             return {"_blocked": True, "_status": resp.status_code, "_text": resp.text[:200]}

#         resp.raise_for_status()
#         return resp.json()
#     except Exception:
#         return None


# def run(
#     mode: str = "full",
#     max_pages: Optional[int] = None,
#     delay_seconds: float = 1.0,
# ) -> Dict[str, Any]:
#     site = "propertia"
#     run_id = make_run_id(site)

#     out_dir = os.path.join("output", site)
#     ensure_dir(out_dir)

#     jsonl_path = os.path.join(out_dir, f"run_{run_id}.jsonl")
#     summary_path = os.path.join(out_dir, f"run_{run_id}_summary.json")

#     summary: Dict[str, Any] = {
#         "source_site": site,
#         "run_id": run_id,
#         "mode": mode,
#         "started_at": utc_now_iso(),
#         "pages_fetched": 0,
#         "urls_collected": 0,
#         "detail_success": 0,
#         "detail_failed": 0,
#         "blocked": False,
#         "errors": [],  # list of dicts
#     }

#     # =====================
#     # STEP 1 — COLLECT URLS
#     # =====================
#     page = 1
#     unique_urls = set()

#     while True:
#         if max_pages is not None and page > max_pages:
#             break

#         print(f"\nCollecting page {page}")
#         data = fetch_listing_page(page)

#         if data is None:
#             summary["errors"].append({"stage": "collect", "page": page, "error": "fetch_failed_or_invalid_json"})
#             break

#         if data.get("_blocked"):
#             summary["blocked"] = True
#             summary["errors"].append(
#                 {"stage": "collect", "page": page, "error": f"blocked_status_{data.get('_status')}"}
#             )
#             break

#         summary["pages_fetched"] += 1

#         properties = data.get("properties", [])
#         if not properties:
#             print("No more properties.")
#             break

#         for prop in properties:
#             url = prop.get("url")
#             if url:
#                 unique_urls.add(url)

#         page += 1
#         time.sleep(delay_seconds)

#     urls = list(unique_urls)
#     summary["urls_collected"] = len(urls)
#     print("\nTOTAL URLS:", len(urls))

#     # =====================
#     # STEP 2 — SCRAPE DETAIL
#     # =====================
#     for i, url in enumerate(urls, 1):
#         print(f"\n[{i}/{len(urls)}] Scraping detail: {url}")

#         try:
#             detail = scrape_property_detail(url)
#             if not detail:
#                 summary["detail_failed"] += 1
#                 continue

#             # metadata untuk ingestion Django
#             pid = detail.get("property_id")
#             listing_url = detail.get("url") or url

#             detail["source_site"] = site
#             detail["run_id"] = run_id
#             detail["scraped_at"] = utc_now_iso()

#             detail["listing_url"] = listing_url
#             detail["external_id"] = pid

#             # dedupe_key
#             if pid:
#                 detail["dedupe_key"] = f"{site}:{pid}"
#             else:
#                 detail["dedupe_key"] = f"{site}:{listing_url}"

#             # content_hash
#             detail["content_hash"] = compute_content_hash(detail)

#             append_jsonl(jsonl_path, detail)
#             summary["detail_success"] += 1

#         except Exception as e:
#             summary["detail_failed"] += 1
#             summary["errors"].append({"stage": "detail", "url": url, "error": str(e)})

#         time.sleep(delay_seconds)

#     summary["finished_at"] = utc_now_iso()

#     with open(summary_path, "w", encoding="utf-8") as f:
#         json.dump(summary, f, ensure_ascii=False, indent=2)

#     print("\nDONE")
#     print("JSONL   :", jsonl_path)
#     print("SUMMARY :", summary_path)

#     return summary


# if __name__ == "__main__":
#     run()



import os
import time
import json
import hashlib
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests

from detail_page_scrape import scrape_property_detail

BASE = "https://propertia.com/wp-admin/admin-ajax.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://propertia.com/search-results-3/?paged=1&listing_page_id=23498",
}

PARAMS_TEMPLATE = {
    "listing_page_id": "23498",
    "action": "houzez_half_map_listings",
    "sortby": "d_date",
    "item_layout": "v1",
    "layout_view": "grid",
    "is_pagination_request": "false",
}

BLOCKED_STATUS = {403, 429}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id(site: str) -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_{site}"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def canonical_for_hash(rec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical untuk change detection.
    Pakai price.amount/currency/period agar stabil lintas format raw string.
    """
    price = rec.get("price") or {}
    if isinstance(price, dict):
        price_canon = {
            "currency": price.get("currency"),
            "amount": price.get("amount"),
            "period": price.get("period"),
        }
    else:
        price_canon = {"currency": None, "amount": None, "period": None}

    return {
        "title": rec.get("title"),
        "price": price_canon,
        "years": rec.get("years"),
        "bedrooms": rec.get("bedrooms"),
        "bathrooms": rec.get("bathrooms"),
        "building_size_value": rec.get("building_size_value"),
        "building_size_unit": rec.get("building_size_unit"),
        "land_size_value": rec.get("land_size_value"),
        "land_size_unit": rec.get("land_size_unit"),
        "area": rec.get("area"),
        "address": rec.get("address"),
        "property_status": rec.get("property_status"),
        "property_type": rec.get("property_type"),
        "labels": rec.get("labels"),
        "features": rec.get("features"),
        "neighborhood": rec.get("neighborhood"),
        "price_per_are_per_year": rec.get("price_per_are_per_year"),
        # images & description besar → skip pada MVP hash
    }


def compute_content_hash(rec: Dict[str, Any]) -> str:
    raw = json.dumps(canonical_for_hash(rec), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_listing_page(session: requests.Session, page: int, timeout: int = 30) -> Optional[Dict[str, Any]]:
    params = PARAMS_TEMPLATE.copy()
    params["paged"] = page

    try:
        resp = session.get(BASE, headers=HEADERS, params=params, timeout=timeout)

        if resp.status_code in BLOCKED_STATUS:
            return {"_blocked": True, "_status": resp.status_code, "_text": (resp.text or "")[:200]}

        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def run(
    mode: str = "full",
    max_pages: Optional[int] = None,
    max_listings: Optional[int] = None,
    delay_seconds: float = 2.0,
    delay_jitter: float = 1.5,
) -> Dict[str, Any]:
    """
    delay_seconds: base delay
    delay_jitter: random tambahan 0..delay_jitter
    """
    site = "propertia"
    run_id = make_run_id(site)

    out_dir = os.path.join("output", site)
    ensure_dir(out_dir)

    jsonl_path = os.path.join(out_dir, f"run_{run_id}.jsonl")
    summary_path = os.path.join(out_dir, f"run_{run_id}_summary.json")

    summary: Dict[str, Any] = {
        "source_site": site,
        "run_id": run_id,
        "mode": mode,
        "started_at": utc_now_iso(),
        "pages_fetched": 0,
        "urls_collected": 0,
        "detail_success": 0,
        "detail_failed": 0,
        "blocked": False,
        "errors": [],
    }

    session = requests.Session()

    try:
        # =====================
        # STEP 1 — COLLECT URLS
        # =====================
        page = 1
        unique_urls = set()

        while True:
            if max_pages is not None and page > max_pages:
                break

            print(f"\nCollecting page {page}")
            data = fetch_listing_page(session, page)

            if data is None:
                summary["errors"].append({"stage": "collect", "page": page, "error": "fetch_failed_or_invalid_json"})
                break

            if data.get("_blocked"):
                summary["blocked"] = True
                summary["errors"].append(
                    {"stage": "collect", "page": page, "error": f"blocked_status_{data.get('_status')}"}
                )
                break

            summary["pages_fetched"] += 1

            properties = data.get("properties", [])
            if not properties:
                print("No more properties.")
                break

            for prop in properties:
                url = prop.get("url")
                if url:
                    unique_urls.add(url)

            page += 1
            time.sleep(delay_seconds + random.uniform(0, delay_jitter))

        urls = list(unique_urls)
        if max_listings is not None:
            urls = urls[:max_listings]

        summary["urls_collected"] = len(urls)
        print("\nTOTAL URLS:", len(urls))

        # =====================
        # STEP 2 — SCRAPE DETAIL
        # =====================
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Scraping detail: {url}")

            try:
                detail = scrape_property_detail(
                    url,
                    session=session,
                    delay_range=(0.0, delay_jitter),
                )
                if not detail:
                    summary["detail_failed"] += 1
                    continue

                pid = detail.get("property_id")
                listing_url = detail.get("url") or url

                detail["source_site"] = site
                detail["run_id"] = run_id
                detail["scraped_at"] = utc_now_iso()

                detail["listing_url"] = listing_url
                detail["external_id"] = pid

                detail["dedupe_key"] = f"{site}:{pid}" if pid else f"{site}:{listing_url}"

                detail["content_hash"] = compute_content_hash(detail)

                append_jsonl(jsonl_path, detail)
                summary["detail_success"] += 1

            except Exception as e:
                summary["detail_failed"] += 1
                summary["errors"].append({"stage": "detail", "url": url, "error": str(e)})

            time.sleep(delay_seconds + random.uniform(0, delay_jitter))

        summary["finished_at"] = utc_now_iso()

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print("\nDONE")
        print("JSONL   :", jsonl_path)
        print("SUMMARY :", summary_path)

        return summary

    finally:
        session.close()


if __name__ == "__main__":
    # test cepat (biar tidak keblok pas development)
    run(max_pages=2, max_listings=20)