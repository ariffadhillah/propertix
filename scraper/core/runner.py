# # scraper/core/runner.py
# from __future__ import annotations

# from pathlib import Path
# from typing import Any, Dict, Optional, Sequence
# from datetime import datetime, timezone
# import traceback

# from scraper.core.state import StateStore
# from scraper.core.schema import empty_record
# from scraper.core.reso_mapper import to_reso

# from scraper.sinks.jsonl_sink import JsonlSink
# from scraper.sinks.base import Sink


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).isoformat()


# def _removed_record(source_key: str, lid: str, scraped_at: str, run_id: str) -> dict:
#     r = empty_record()

#     r["listing"]["source"] = source_key
#     r["listing"]["source_listing_id"] = lid
#     r["listing"]["source_url"] = None
#     r["listing"]["ListingKey"] = f"{source_key}:{lid}"

#     r["ingestion"]["scrape_run_id"] = run_id
#     r["ingestion"]["captured_at"] = scraped_at
#     r["ingestion"]["first_seen_at"] = None
#     r["ingestion"]["last_seen_at"] = scraped_at

#     r["status"]["current_status"] = "inactive"
#     r["status"]["last_change_type"] = "removed"

#     r.setdefault("raw", {})
#     r["raw"]["payload"] = {}

#     return r


# def _bridge_for_reso(record: Dict[str, Any]) -> Dict[str, Any]:
#     record.setdefault("listing", {})
#     record.setdefault("ingestion", {})
#     record.setdefault("status", {})

#     listing = dict(record["listing"])
#     ingestion = record["ingestion"]
#     status = record["status"]

#     listing["status"] = status.get("current_status") or listing.get("status")

#     if ingestion.get("first_seen_at") is not None:
#         listing["ingestion_first_seen_at"] = ingestion.get("first_seen_at")
#     if ingestion.get("last_seen_at") is not None:
#         listing["ingestion_last_seen_at"] = ingestion.get("last_seen_at")
#     if ingestion.get("scrape_run_id"):
#         listing["scrape_run_id"] = ingestion.get("scrape_run_id")
#     if ingestion.get("captured_at"):
#         listing["captured_at"] = ingestion.get("captured_at")

#     raw_payload = (record.get("raw") or {}).get("payload")
#     if raw_payload is not None:
#         listing["raw"] = {"payload": raw_payload}

#     return listing


# def _default_sink(out_path: str) -> Sink:
#     return JsonlSink(out_path)


# def run_site_stream(
#     adapter,
#     start_url: str,
#     out_path: str,
#     state_path: str,
#     limit: Optional[int] = None,
#     output_mode: str = "delta",   # "delta" | "snapshot"
#     sink: Optional[Sink] = None,
# ) -> Dict[str, Any]:
#     # --- (BIARKAN ISI KODE KAMU YANG ADA, TIDAK DIUBAH) ---
#     # (paste existing code)
#     ...


# def run_site_stream_multi(
#     adapter,
#     start_urls: Sequence[str],
#     out_path: str,
#     state_path: str,
#     limit: Optional[int] = None,
#     output_mode: str = "delta",   # "delta" | "snapshot"
#     sink: Optional[Sink] = None,
# ) -> Dict[str, Any]:
#     """
#     Multi start_url runner:
#     - limit bersifat GLOBAL (total previews across all URLs)
#     - seen_ids adalah UNION dari semua URLs
#     - removed detection dihitung SEKALI di akhir (bukan per URL)
#     """

#     run_id = getattr(adapter, "scrape_run_id", None) or utc_now_iso()

#     output_mode = (output_mode or "delta").lower().strip()
#     if output_mode not in ("delta", "snapshot"):
#         raise ValueError("output_mode must be 'delta' or 'snapshot'")

#     Path(out_path).parent.mkdir(parents=True, exist_ok=True)
#     Path(state_path).parent.mkdir(parents=True, exist_ok=True)

#     if sink is None:
#         sink = _default_sink(out_path)

#     state = StateStore(Path(state_path), adapter.source_key)
#     state.load()

#     seen_ids: set[str] = set()
#     written = 0
#     stats = {"new": 0, "updated": 0, "unchanged": 0, "removed": 0, "errors": 0}

#     # global preview counter (mirrors enumerate behavior)
#     preview_idx = 0

#     try:
#         # ---------------------------
#         # Main crawl over ALL start_urls
#         # ---------------------------
#         for u_i, start_url in enumerate(start_urls, start=1):
#             # Optional: logging here is OK, CLI already prints
#             for preview in adapter.iter_previews(start_url):
#                 if limit is not None and preview_idx >= limit:
#                     break
#                 preview_idx += 1

#                 lid = preview.get("source_listing_id")
#                 if not lid:
#                     continue

#                 seen_ids.add(lid)

#                 try:
#                     detail = adapter.fetch_detail(preview)
#                     record = adapter.normalize(preview, detail)

#                     record.setdefault("listing", {})
#                     record.setdefault("hashes", {})
#                     record.setdefault("ingestion", {})
#                     record.setdefault("status", {})
#                     record.setdefault("raw", {})

#                     record["listing"]["source"] = record["listing"].get("source") or adapter.source_key
#                     record["ingestion"]["scrape_run_id"] = record["ingestion"].get("scrape_run_id") or run_id

#                     prev = state.get(lid)
#                     now_iso = utc_now_iso()

#                     captured_at = record["ingestion"].get("captured_at") or now_iso
#                     first_seen = prev.first_seen_at if (prev and getattr(prev, "first_seen_at", None)) else captured_at

#                     record["ingestion"]["captured_at"] = captured_at
#                     record["ingestion"]["first_seen_at"] = record["ingestion"].get("first_seen_at") or first_seen
#                     record["ingestion"]["last_seen_at"] = captured_at

#                     record["status"]["current_status"] = record["status"].get("current_status") or "active"

#                     current_hash = (record.get("hashes") or {}).get("canonical_content_hash")
#                     if not current_hash:
#                         raise ValueError("Missing hashes.canonical_content_hash in record")

#                     record["reso"] = to_reso(_bridge_for_reso(record))

#                     if prev is None:
#                         change = "new"
#                         stats["new"] += 1
#                     else:
#                         if (prev.content_hash or "") != (current_hash or ""):
#                             change = "updated"
#                             stats["updated"] += 1
#                         else:
#                             change = "unchanged"
#                             stats["unchanged"] += 1

#                     record["status"]["last_change_type"] = change

#                     if output_mode == "snapshot":
#                         sink.write(record, change)
#                         written += 1
#                     else:
#                         if change in ("new", "updated"):
#                             sink.write(record, change)
#                             written += 1

#                     state.upsert(
#                         listing_id=lid,
#                         content_hash=current_hash,
#                         first_seen_at=first_seen,
#                         last_seen_at=captured_at,
#                         status="active",
#                     )

#                 except Exception as e:
#                     stats["errors"] += 1
#                     print(f"[ERROR] lid={lid} url={preview.get('source_url') or preview.get('url')}")
#                     print(f"[ERROR] {type(e).__name__}: {e}")
#                     traceback.print_exc()
#                     continue

#             if limit is not None and preview_idx >= limit:
#                 break

#         # ---------------------------
#         # Removed detection (ONCE)
#         # ---------------------------
#         prev_active = state.all_active_ids()
#         removed_ids = prev_active - seen_ids
#         removed_now = utc_now_iso()

#         for lid in removed_ids:
#             stats["removed"] += 1

#             prev_row = state.get(lid)
#             first_seen_removed = getattr(prev_row, "first_seen_at", None) if prev_row else None

#             removed = _removed_record(adapter.source_key, lid, removed_now, run_id)
#             removed["ingestion"]["first_seen_at"] = first_seen_removed
#             removed["ingestion"]["last_seen_at"] = removed_now
#             removed["reso"] = to_reso(_bridge_for_reso(removed))

#             sink.write(removed, "removed")
#             written += 1

#             state.upsert(
#                 listing_id=lid,
#                 content_hash=prev_row.content_hash if prev_row else None,
#                 first_seen_at=first_seen_removed,
#                 last_seen_at=removed_now,
#                 status="removed",
#             )

#         state.data["last_run_id"] = run_id
#         state.save()

#         stats["written"] = written
#         return stats

#     finally:
#         try:
#             sink.close()
#         except Exception:
#             pass


# v3
# scraper/core/runner.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from datetime import datetime, timezone
import traceback

from scraper.core.state import StateStore
from scraper.core.schema import empty_record
from scraper.core.reso_mapper import to_reso

from scraper.sinks.jsonl_sink import JsonlSink
from scraper.sinks.base import Sink


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_sink(out_path: str) -> Sink:
    return JsonlSink(out_path)


def _export_record(record: Dict[str, Any], schema_version: str) -> Dict[str, Any]:
    """
    Export record ke format target tanpa mengubah record internal.
    schema_version:
      - "legacy" (default) -> return record apa adanya
      - "v3" -> convert ke client v3 schema via scraper/schema/v3_exporter.py
    """
    sv = (schema_version or "legacy").strip().lower()
    if sv == "v3":
        from scraper.schema.v3_exporter import to_v3_record
        return to_v3_record(record)
    return record


def _removed_record(source_key: str, lid: str, scraped_at: str, run_id: str) -> dict:
    """
    Build minimal removed record in internal schema (legacy template),
    later can be exported to v3 via _export_record().
    """
    r = empty_record()

    r["listing"]["source"] = source_key
    r["listing"]["source_listing_id"] = lid
    r["listing"]["source_url"] = None
    r["listing"]["ListingKey"] = f"{source_key}:{lid}"

    r["ingestion"]["scrape_run_id"] = run_id
    r["ingestion"]["captured_at"] = scraped_at
    r["ingestion"]["first_seen_at"] = None
    r["ingestion"]["last_seen_at"] = scraped_at

    r["status"]["current_status"] = "inactive"
    r["status"]["last_change_type"] = "removed"

    r.setdefault("raw", {})
    r["raw"]["payload"] = {}

    return r


def _bridge_for_reso(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    RESO mapper expects "listing-like" dict. Bridge record schema -> listing dict
    and keep minimal raw payload.
    """
    record.setdefault("listing", {})
    record.setdefault("ingestion", {})
    record.setdefault("status", {})

    listing = dict(record["listing"])
    ingestion = record["ingestion"]
    status = record["status"]

    listing["status"] = status.get("current_status") or listing.get("status")

    if ingestion.get("first_seen_at") is not None:
        listing["ingestion_first_seen_at"] = ingestion.get("first_seen_at")
    if ingestion.get("last_seen_at") is not None:
        listing["ingestion_last_seen_at"] = ingestion.get("last_seen_at")
    if ingestion.get("scrape_run_id"):
        listing["scrape_run_id"] = ingestion.get("scrape_run_id")
    if ingestion.get("captured_at"):
        listing["captured_at"] = ingestion.get("captured_at")

    raw_payload = (record.get("raw") or {}).get("payload")
    if raw_payload is not None:
        listing["raw"] = {"payload": raw_payload}

    return listing


def run_site_stream(
    adapter,
    start_url: str,
    out_path: str,
    state_path: str,
    limit: Optional[int] = None,
    output_mode: str = "delta",
    sink: Optional[Sink] = None,
) -> Dict[str, Any]:
    # Prevent accidental usage.
    raise NotImplementedError("run_site_stream is deprecated; use run_site_stream_multi instead.")


def run_site_stream_multi(
    adapter,
    start_urls: Sequence[str],
    out_path: str,
    state_path: str,
    limit: Optional[int] = None,
    output_mode: str = "delta",   # "delta" | "snapshot"
    sink: Optional[Sink] = None,
    schema_version: str = "legacy",
) -> Dict[str, Any]:
    """
    Multi start_url runner:
    - limit bersifat GLOBAL (total previews across all URLs)
    - seen_ids adalah UNION dari semua URLs
    - removed detection dihitung SEKALI di akhir
    """
    run_id = getattr(adapter, "scrape_run_id", None) or utc_now_iso()

    output_mode = (output_mode or "delta").lower().strip()
    if output_mode not in ("delta", "snapshot"):
        raise ValueError("output_mode must be 'delta' or 'snapshot'")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)

    if sink is None:
        sink = _default_sink(out_path)

    # NOTE: adapter must expose source_key (you already do)
    state = StateStore(Path(state_path), adapter.source_key)
    state.load()

    seen_ids: set[str] = set()
    written = 0
    stats = {"new": 0, "updated": 0, "unchanged": 0, "removed": 0, "errors": 0}

    preview_idx = 0

    try:
        # ---------------------------
        # Main crawl over ALL start_urls
        # ---------------------------
        for start_url in start_urls:
            for preview in adapter.iter_previews(start_url):
                if limit is not None and preview_idx >= limit:
                    break
                preview_idx += 1

                lid = preview.get("source_listing_id")
                if not lid:
                    continue

                seen_ids.add(lid)

                try:
                    detail = adapter.fetch_detail(preview)
                    record = adapter.normalize(preview, detail)

                    # ensure minimal shape
                    record.setdefault("listing", {})
                    record.setdefault("hashes", {})
                    record.setdefault("ingestion", {})
                    record.setdefault("status", {})
                    record.setdefault("raw", {})

                    record["listing"]["source"] = record["listing"].get("source") or adapter.source_key
                    record["ingestion"]["scrape_run_id"] = record["ingestion"].get("scrape_run_id") or run_id

                    prev = state.get(lid)
                    now_iso = utc_now_iso()

                    captured_at = record["ingestion"].get("captured_at") or now_iso
                    first_seen = prev.first_seen_at if (prev and getattr(prev, "first_seen_at", None)) else captured_at

                    record["ingestion"]["captured_at"] = captured_at
                    record["ingestion"]["first_seen_at"] = record["ingestion"].get("first_seen_at") or first_seen
                    record["ingestion"]["last_seen_at"] = captured_at

                    record["status"]["current_status"] = record["status"].get("current_status") or "active"

                    current_hash = (record.get("hashes") or {}).get("canonical_content_hash")
                    if not current_hash:
                        raise ValueError("Missing hashes.canonical_content_hash in record")

                    # build RESO from internal record (not exported)
                    record["reso"] = to_reso(_bridge_for_reso(record))

                    # change detection
                    if prev is None:
                        change = "new"
                        stats["new"] += 1
                    else:
                        if (prev.content_hash or "") != (current_hash or ""):
                            change = "updated"
                            stats["updated"] += 1
                        else:
                            change = "unchanged"
                            stats["unchanged"] += 1

                    record["status"]["last_change_type"] = change

                    # export
                    out_rec = _export_record(record, schema_version)

                    if output_mode == "snapshot":
                        sink.write(out_rec, change)
                        written += 1
                    else:
                        if change in ("new", "updated"):
                            sink.write(out_rec, change)
                            written += 1

                    # persist state (always)
                    state.upsert(
                        listing_id=lid,
                        content_hash=current_hash,
                        first_seen_at=first_seen,
                        last_seen_at=captured_at,
                        status="active",
                    )

                except Exception as e:
                    stats["errors"] += 1
                    print(f"[ERROR] lid={lid} url={preview.get('source_url') or preview.get('url')}")
                    print(f"[ERROR] {type(e).__name__}: {e}")
                    traceback.print_exc()
                    continue

            if limit is not None and preview_idx >= limit:
                break

        # ---------------------------
        # Removed detection (ONCE)
        # ---------------------------
        prev_active = state.all_active_ids()
        removed_ids = prev_active - seen_ids
        removed_now = utc_now_iso()

        for lid in removed_ids:
            stats["removed"] += 1

            prev_row = state.get(lid)
            first_seen_removed = getattr(prev_row, "first_seen_at", None) if prev_row else None

            removed = _removed_record(adapter.source_key, lid, removed_now, run_id)
            removed["ingestion"]["first_seen_at"] = first_seen_removed
            removed["ingestion"]["last_seen_at"] = removed_now
            removed["reso"] = to_reso(_bridge_for_reso(removed))

            out_removed = _export_record(removed, schema_version)
            sink.write(out_removed, "removed")
            written += 1

            state.upsert(
                listing_id=lid,
                content_hash=prev_row.content_hash if prev_row else None,
                first_seen_at=first_seen_removed,
                last_seen_at=removed_now,
                status="removed",
            )

        state.data["last_run_id"] = run_id
        state.save()

        stats["written"] = written
        return stats

    finally:
        try:
            sink.close()
        except Exception:
            pass