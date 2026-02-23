from __future__ import annotations

from typing import Dict, Any, Iterable, Set, Tuple
import time

from .list_items import parse_list_page


def iter_list_items(
    start_url: str,
    delay: float = 0.8,
    max_pages: int = 500,
    stop_after_no_new_pages: int = 2,
) -> Iterable[Dict[str, Any]]:
    """
    Yield preview items across pages, deduped by source_listing_id.
    Production guards:
      - stop when page has no items
      - stop when page repeats (same ids as previous)
      - stop when we see 0 new items for N pages (pagination loop / cache)
    """
    seen_ids: Set[str] = set()
    prev_page_sig: Tuple[str, ...] | None = None
    no_new_streak = 0

    page = 1
    while page <= max_pages:
        url = f"{start_url}&page={page}"
        print(f"[BHI] Crawling page {page}")

        items = parse_list_page(url)
        if not items:
            print(f"[BHI] No items on page {page}. Stop.")
            break

        # signature halaman: urutan ids yang muncul
        page_ids = [it.get("source_listing_id", "") for it in items if it.get("source_listing_id")]
        page_sig = tuple(page_ids)

        if prev_page_sig is not None and page_sig == prev_page_sig:
            print(f"[BHI] Page {page} repeats previous page. Stop.")
            break
        prev_page_sig = page_sig

        new_in_page = 0
        for it in items:
            sid = it.get("source_listing_id")
            if not sid:
                continue
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            new_in_page += 1
            yield it

        if new_in_page == 0:
            no_new_streak += 1
            print(f"[BHI] Page {page}: 0 new items (streak={no_new_streak})")
            if no_new_streak >= stop_after_no_new_pages:
                print("[BHI] Pagination loop suspected. Stop.")
                break
        else:
            no_new_streak = 0
            print(f"[BHI] Page {page}: {new_in_page} new items")

        page += 1
        time.sleep(delay)