# from __future__ import annotations
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Dict, Any, List, Tuple

# from scraper.core.hash_utils import hash_for_listing_change
# from scraper.core.jsonl import write_jsonl
# from scraper.core.state import StateStore

# def iso_now():
#     return datetime.now(timezone.utc).isoformat()

# def run_adapter(adapter, out_dir: Path, state_path: Path, max_pages: int | None = None):
#     state = StateStore(state_path)

#     run_ts = iso_now()
#     seen_keys = set()

#     new_rows = []
#     updated_rows = []
#     unchanged = 0

#     pages = list(adapter.iter_list_pages())
#     if max_pages is not None:
#         pages = pages[:max_pages]

#     for page_url in pages:
#         items = adapter.parse_list_page(page_url)

#         for item in items:
#             listing = adapter.parse_detail_page(item)

#             # enforce required identity fields
#             listing["source"] = adapter.source_name
#             listing["first_seen_at"] = listing.get("first_seen_at") or run_ts
#             listing["last_seen_at"] = run_ts
#             listing["status"] = listing.get("status") or "active"

#             key = f'{listing["source"]}:{listing["source_listing_id"]}'
#             seen_keys.add(key)

#             listing["content_hash"] = hash_for_listing_change(listing)

#             prev = state.get_listing(key)
#             if prev is None:
#                 new_rows.append(listing)
#                 state.upsert_listing(key, {"content_hash": listing["content_hash"], "last_seen_at": run_ts})
#             else:
#                 if prev.get("content_hash") != listing["content_hash"]:
#                     updated_rows.append(listing)
#                     state.upsert_listing(key, {"content_hash": listing["content_hash"], "last_seen_at": run_ts})
#                 else:
#                     unchanged += 1
#                     # update last_seen only
#                     state.upsert_listing(key, {"content_hash": prev.get("content_hash"), "last_seen_at": run_ts})

#     # mark removed listings (present in state but not seen this run)
#     removed_rows = []
#     for key in (state.all_keys() - seen_keys):
#         prev = state.get_listing(key)
#         if not prev:
#             continue
#         # emit a removal event row
#         source, source_listing_id = key.split(":", 1)
#         removed_rows.append({
#             "source": source,
#             "source_listing_id": source_listing_id,
#             "source_url": None,
#             "first_seen_at": None,
#             "last_seen_at": run_ts,
#             "status": "removed",
#             "content_hash": None,
#             "raw": {"reason": "not_seen_in_run"}
#         })

#     # output JSONL
#     out_dir.mkdir(parents=True, exist_ok=True)
#     write_jsonl(out_dir / f"{adapter.source_name}_new.jsonl", new_rows)
#     write_jsonl(out_dir / f"{adapter.source_name}_updated.jsonl", updated_rows)
#     write_jsonl(out_dir / f"{adapter.source_name}_removed.jsonl", removed_rows)

#     return {
#         "source": adapter.source_name,
#         "new": len(new_rows),
#         "updated": len(updated_rows),
#         "removed": len(removed_rows),
#         "unchanged": unchanged,
#     }


from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from datetime import datetime, timezone

from scraper.core.state import StateStore
from scraper.core.jsonl import append_jsonl

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def run_site_stream(
    adapter,
    start_url: str,
    out_path: str,
    state_path: str,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    run_id = getattr(adapter, "scrape_run_id", None) or utc_now_iso()
    scraped_at = utc_now_iso()

    state = StateStore(Path(state_path), adapter.source_key)
    state.load()

    seen_ids: set[str] = set()
    written = 0
    stats = {"new": 0, "updated": 0, "unchanged": 0, "removed": 0, "errors": 0}

    for i, preview in enumerate(adapter.iter_previews(start_url)):
        if limit and i >= limit:
            break

        lid = preview.get("source_listing_id")
        if not lid:
            continue
        seen_ids.add(lid)

        try:
            detail = adapter.fetch_detail(preview)
            merged = adapter.normalize(preview, detail)  # should compute content_hash + set first/last seen etc

            merged.setdefault("source", adapter.source_key)
            merged.setdefault("first_seen_at", scraped_at)
            merged["last_seen_at"] = scraped_at
            merged["status"] = merged.get("status") or "active"

            prev = state.get(lid)
            if prev is None:
                change_type = "new"
                stats["new"] += 1
                append_jsonl(out_path, {**merged, "change_type": change_type, "scrape_run_id": run_id})
                written += 1
            else:
                if (prev.content_hash or "") != (merged.get("content_hash") or ""):
                    change_type = "updated"
                    stats["updated"] += 1
                    append_jsonl(out_path, {**merged, "change_type": change_type, "scrape_run_id": run_id})
                    written += 1
                else:
                    change_type = "unchanged"
                    stats["unchanged"] += 1

            # update state row
            state.upsert(
                listing_id=lid,
                content_hash=merged.get("content_hash"),
                last_seen_at=scraped_at,
                status="active",
            )

        except Exception:
            stats["errors"] += 1
            # log detail error (di sini minimal skip)
            continue

    # removed detection
    prev_active = state.all_active_ids()
    removed_ids = prev_active - seen_ids
    for lid in removed_ids:
        stats["removed"] += 1
        # emit minimal removed record
        append_jsonl(out_path, {
            "source": adapter.source_key,
            "source_listing_id": lid,
            "status": "removed",
            "last_seen_at": scraped_at,
            "change_type": "removed",
            "scrape_run_id": run_id,
        })
        state.upsert(lid, content_hash=state.get(lid).content_hash if state.get(lid) else None, last_seen_at=scraped_at, status="removed")

    state.data["last_run_id"] = run_id
    state.save()

    stats["written"] = written
    return stats