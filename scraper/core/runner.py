# scraper/core/runner.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import traceback

from scraper.core.state import StateStore
from scraper.core.schema import empty_record
from scraper.core.reso_mapper import to_reso

from scraper.sinks.jsonl_sink import JsonlSink
from scraper.sinks.base import Sink


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _removed_record(source_key: str, lid: str, scraped_at: str, run_id: str) -> dict:
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

    return listing


def _default_sink(out_path: str) -> Sink:
    """
    Default behavior:
    - If no sink is provided, we write JSONL to out_path.
    """
    return JsonlSink(out_path)


def run_site_stream(
    adapter,
    start_url: str,
    out_path: str,
    state_path: str,
    limit: Optional[int] = None,
    output_mode: str = "delta",   # "delta" | "snapshot"
    sink: Optional[Sink] = None,
) -> Dict[str, Any]:
    """
    output_mode:
      - "delta": only write new/updated/removed (unchanged counted but not written)
      - "snapshot": write ALL items each run (new/updated/unchanged/removed)

    sink:
      - If provided, runner will write to that sink (JsonlSink/SQLiteSink/MultiSink/etc).
      - If None, defaults to JsonlSink(out_path).
    """
    run_id = getattr(adapter, "scrape_run_id", None) or utc_now_iso()

    output_mode = (output_mode or "delta").lower().strip()
    if output_mode not in ("delta", "snapshot"):
        raise ValueError("output_mode must be 'delta' or 'snapshot'")

    # Create folders (even if sink isn't JSONL, out_path is still used by default sink)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)

    # Default sink if none
    if sink is None:
        sink = _default_sink(out_path)

    state = StateStore(Path(state_path), adapter.source_key)
    state.load()

    seen_ids: set[str] = set()
    written = 0
    stats = {"new": 0, "updated": 0, "unchanged": 0, "removed": 0, "errors": 0}

    try:
        # ---------------------------
        # Main crawl: list -> detail -> normalize -> classify -> write
        # ---------------------------
        for i, preview in enumerate(adapter.iter_previews(start_url)):
            if limit and i >= limit:
                break

            lid = preview.get("source_listing_id")
            if not lid:
                continue

            seen_ids.add(lid)

            try:
                detail = adapter.fetch_detail(preview)
                record = adapter.normalize(preview, detail)  # MUST return nested record

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

                # current_hash = (record.get("hashes") or {}).get("canonical_content_hash")
                current_hash = (record.get("hashes") or {}).get("canonical_content_hash")
                if not current_hash:
                    # fallback: jangan biarkan None masuk ke state
                    # (pilih salah satu) -> error keras atau compute ulang jika tersedia
                    raise ValueError("Missing hashes.canonical_content_hash in record")

                # RESO mapping (always computed)
                record["reso"] = to_reso(_bridge_for_reso(record))

                # classify change
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

                # write policy
                if output_mode == "snapshot":
                    sink.write(record, change)
                    written += 1
                else:
                    # delta: only new/updated
                    if change in ("new", "updated"):
                        sink.write(record, change)
                        written += 1

                # update state
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

        # ---------------------------
        # Removed detection
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

            # removed is always written (both delta & snapshot)
            sink.write(removed, "removed")
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