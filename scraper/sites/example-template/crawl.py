from __future__ import annotations

from typing import Any, Dict, Iterable, Set, Tuple
import time

from .list_items import parse_list_page


def iter_list_items(
    start_url: str,
    delay: float = 0.8,
    max_pages: int = 500,
    stop_after_no_new_pages: int = 2,
) -> Iterable[Dict[str, Any]]:
    """
    start_url: admin-ajax.php?...paged=1...
    Kita akan override paged=page setiap loop.
    """
    seen_ids: Set[str] = set()
    prev_page_sig: Tuple[str, ...] | None = None
    no_new_streak = 0

    page = 1
    while page <= max_pages:
        # penting: endpoint kamu punya parameter paged= (kadang dobel), tapi kita cukup replace key 'paged'
        # kalau ternyata di query ada dua 'paged', parse_list_page akan terima hasil server sesuai terakhir / behavior WP.
        url = start_url

        # brute-force replace "&paged=1" jadi "&paged={page}" kalau ada
        # ini cara paling aman tanpa “ngatur ulang query dict” (karena URL kamu panjang)
        url = _replace_paged(url, page)

        print(f"[PROPERTIA] Crawling page {page}")

        items = parse_list_page(url)
        if not items:
            print(f"[PROPERTIA] No items on page {page}. Stop.")
            break

        page_ids = [it.get("source_listing_id", "") for it in items if it.get("source_listing_id")]
        page_sig = tuple(page_ids)

        if prev_page_sig is not None and page_sig == prev_page_sig:
            print(f"[PROPERTIA] Page {page} repeats previous page. Stop.")
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
            print(f"[PROPERTIA] Page {page}: 0 new items (streak={no_new_streak})")
            if no_new_streak >= stop_after_no_new_pages:
                print("[PROPERTIA] Pagination loop suspected. Stop.")
                break
        else:
            no_new_streak = 0
            print(f"[PROPERTIA] Page {page}: {new_in_page} new items")

        page += 1
        time.sleep(delay)


def _replace_paged(url: str, page: int) -> str:
    """
    URL kamu kadang punya 'paged=1&paged=2' (duplikat).
    Cara paling aman: replace semua 'paged=<angka>' jadi paged=<page>.
    """
    import re
    return re.sub(r"(\bpaged=)\d+", rf"\g<1>{page}", url)