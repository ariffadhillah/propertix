from __future__ import annotations

from typing import Dict, Any, Iterable
from datetime import datetime, timezone

from scraper.core.normalizer import merge_preview_into_detail, finalize_record
from scraper.core.broker_schema import ensure_broker_block
from .crawl import iter_list_items
from .detail_page import parse_detail_page


class BaliHomeImmoAdapter:
    source_key = "propertia"

    def __init__(self):
        # run id untuk 1 kali run scraping
        self.scrape_run_id = datetime.now(timezone.utc).isoformat()

    def iter_previews(self, start_url: str) -> Iterable[Dict[str, Any]]:
        yield from iter_list_items(start_url, delay=0.8, max_pages=500)

    def fetch_detail(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        # PURE parsing layer
        return parse_detail_page(preview)

    def normalize(self, preview: Dict[str, Any], detail: Dict[str, Any]) -> Dict[str, Any]:
        """
        preview + detail -> merged flat -> finalize_record (nested schema client)
        Adapter TIDAK membangun RESO (dibangun di runner agar konsisten).
        """
        merged = merge_preview_into_detail(preview, detail)

        # nested record sesuai schema client
        record = finalize_record(merged, scrape_run_id=self.scrape_run_id)

        # attach raw preview/detail (berguna untuk audit / debug)
        record.setdefault("raw", {})
        record["raw"]["source_preview"] = preview
        record["raw"]["source_detail"] = detail

        # pastikan listing ada
        record.setdefault("listing", {})
        ensure_broker_block(record["listing"])

        # 1) pastikan "price" naik ke listing
        if not record["listing"].get("price"):
            if isinstance(detail, dict) and isinstance(detail.get("price"), dict):
                record["listing"]["price"] = detail["price"]
            elif isinstance(merged, dict) and isinstance(merged.get("price"), dict):
                record["listing"]["price"] = merged["price"]

        # 2) pastikan "prices" list naik ke listing
        if not record["listing"].get("prices"):
            if isinstance(detail, dict) and isinstance(detail.get("prices"), list):
                record["listing"]["prices"] = detail["prices"]
            elif isinstance(merged, dict) and isinstance(merged.get("prices"), list):
                record["listing"]["prices"] = merged["prices"]

        # NOTE:
        # - Jangan set record["reso"] di sini.
        # - Runner akan inject ingestion/status lalu build reso secara konsisten.

        return record