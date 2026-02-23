# # # from __future__ import annotations
# # # from pathlib import Path
# # # import json
# # # from typing import Dict, Any

# # # class StateStore:
# # #     def __init__(self, path: Path):
# # #         self.path = path
# # #         self.path.parent.mkdir(parents=True, exist_ok=True)
# # #         if not self.path.exists():
# # #             self.path.write_text(json.dumps({"listings": {}}, indent=2), encoding="utf-8")

# # #     def load(self) -> Dict[str, Any]:
# # #         return json.loads(self.path.read_text(encoding="utf-8"))

# # #     def save(self, data: Dict[str, Any]) -> None:
# # #         self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

# # #     def get_listing(self, key: str) -> Dict[str, Any] | None:
# # #         data = self.load()
# # #         return data["listings"].get(key)

# # #     def upsert_listing(self, key: str, record: Dict[str, Any]) -> None:
# # #         data = self.load()
# # #         data["listings"][key] = record
# # #         self.save(data)

# # #     def all_keys(self):
# # #         data = self.load()
# # #         return set(data["listings"].keys())



# # from __future__ import annotations
# # from dataclasses import dataclass
# # from pathlib import Path
# # from typing import Any, Dict, Optional
# # import json

# # @dataclass
# # class ListingState:
# #     content_hash: Optional[str]
# #     last_seen_at: Optional[str]
# #     status: str = "active"  # active/removed/unknown

# # class StateStore:
# #     def __init__(self, path: Path, source_key: str):
# #         self.path = path
# #         self.source_key = source_key
# #         self.data: Dict[str, Any] = {"source_key": source_key, "last_run_id": None, "listings": {}}

# #     def load(self) -> None:
# #         if self.path.exists():
# #             self.data = json.loads(self.path.read_text(encoding="utf-8"))

# #     def save(self) -> None:
# #         self.path.parent.mkdir(parents=True, exist_ok=True)
# #         self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

# #     def get(self, listing_id: str) -> Optional[ListingState]:
# #         row = (self.data.get("listings") or {}).get(listing_id)
# #         if not row:
# #             return None
# #         return ListingState(
# #             content_hash=row.get("content_hash"),
# #             last_seen_at=row.get("last_seen_at"),
# #             status=row.get("status", "active"),
# #         )

# #     def upsert(self, listing_id: str, content_hash: Optional[str], last_seen_at: Optional[str], status: str) -> None:
# #         self.data.setdefault("listings", {})
# #         self.data["listings"][listing_id] = {
# #             "content_hash": content_hash,
# #             "last_seen_at": last_seen_at,
# #             "status": status,
# #         }

# #     def all_active_ids(self) -> set[str]:
# #         out = set()
# #         for lid, row in (self.data.get("listings") or {}).items():
# #             if row.get("status") == "active":
# #                 out.add(lid)
# #         return out


# from __future__ import annotations
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Any, Dict, Tuple
# import json
# from datetime import datetime, timezone


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# @dataclass
# class IncrementalResult:
#     change_type: str  # new|updated|unchanged|removed
#     record: Dict[str, Any]


# class StateStore:
#     def __init__(self, path: str, source_key: str):
#         self.path = Path(path)
#         self.source_key = source_key
#         self.data: Dict[str, Any] = {"source_key": source_key, "updated_at": None, "listings": {}}
#         self.seen_this_run = set()

#     def load(self) -> None:
#         if self.path.exists():
#             self.data = json.loads(self.path.read_text(encoding="utf-8"))
#         self.data.setdefault("source_key", self.source_key)
#         self.data.setdefault("listings", {})

#     def save(self) -> None:
#         self.data["updated_at"] = utc_now_iso()
#         self.path.parent.mkdir(parents=True, exist_ok=True)
#         self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

#     def upsert_seen(self, listing_key: str, listing: Dict[str, Any]) -> IncrementalResult:
#         """
#         listing sudah harus punya:
#         - content_hash
#         - first_seen_at / last_seen_at
#         - status
#         """
#         listings = self.data["listings"]
#         prev = listings.get(listing_key)

#         self.seen_this_run.add(listing_key)

#         if not prev:
#             listings[listing_key] = {
#                 "content_hash": listing["content_hash"],
#                 "first_seen_at": listing["first_seen_at"],
#                 "last_seen_at": listing["last_seen_at"],
#                 "status": listing.get("status", "active"),
#                 "missing_runs": 0,
#             }
#             return IncrementalResult("new", listing)

#         # existing
#         prev_hash = prev.get("content_hash")
#         new_hash = listing["content_hash"]

#         prev["last_seen_at"] = listing["last_seen_at"]
#         prev["missing_runs"] = 0
#         prev["status"] = listing.get("status", prev.get("status", "active"))

#         if new_hash != prev_hash:
#             prev["content_hash"] = new_hash
#             return IncrementalResult("updated", listing)

#         return IncrementalResult("unchanged", listing)

#     def mark_removed(self, missing_runs_threshold: int = 2) -> list[Dict[str, Any]]:
#         """
#         Setelah run selesai: listing yang tidak terlihat → missing_runs++
#         Jika >= threshold → status removed
#         """
#         removed_records = []
#         for listing_key, meta in self.data["listings"].items():
#             if listing_key in self.seen_this_run:
#                 continue

#             meta["missing_runs"] = int(meta.get("missing_runs", 0)) + 1

#             if meta["missing_runs"] >= missing_runs_threshold and meta.get("status") != "removed":
#                 meta["status"] = "removed"
#                 removed_records.append({
#                     "listing_key": listing_key,
#                     "status": "removed",
#                     "last_seen_at": meta.get("last_seen_at"),
#                     "content_hash": meta.get("content_hash"),
#                 })

#         return removed_records



from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set


@dataclass
class StateRecord:
    content_hash: Optional[str] = None
    last_seen_at: Optional[str] = None
    status: str = "active"  # "active" | "removed"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StateRecord":
        return cls(
            content_hash=d.get("content_hash"),
            last_seen_at=d.get("last_seen_at"),
            status=d.get("status") or "active",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_hash": self.content_hash,
            "last_seen_at": self.last_seen_at,
            "status": self.status,
        }


class StateStore:
    """
    Persist state per source in JSON:
    {
      "source": "bali-home-immo",
      "last_run_id": "...",
      "listings": {
         "RF123": {"content_hash":"..","last_seen_at":"..","status":"active"},
         ...
      }
    }
    """

    def __init__(self, path: str | Path, source_key: str):
        self.path = Path(path)
        self.source_key = source_key
        self.data: Dict[str, Any] = {
            "source": source_key,
            "last_run_id": None,
            "listings": {},
        }

    def load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                # kalau corrupt, jangan crash total; start fresh
                self.data = {"source": self.source_key, "last_run_id": None, "listings": {}}

        # normalisasi struktur minimal
        if "listings" not in self.data or not isinstance(self.data["listings"], dict):
            self.data["listings"] = {}
        if "source" not in self.data:
            self.data["source"] = self.source_key

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, listing_id: str) -> Optional[StateRecord]:
        d = self.data.get("listings", {}).get(listing_id)
        if not isinstance(d, dict):
            return None
        return StateRecord.from_dict(d)

    def upsert(self, listing_id: str, content_hash: Optional[str], last_seen_at: str, status: str = "active") -> None:
        self.data.setdefault("listings", {})
        self.data["listings"][listing_id] = StateRecord(
            content_hash=content_hash,
            last_seen_at=last_seen_at,
            status=status or "active",
        ).to_dict()

    def all_ids(self) -> Set[str]:
        return set(self.data.get("listings", {}).keys())

    def all_active_ids(self) -> Set[str]:
        """
        Runner butuh ini untuk removed detection:
        prev_active - seen_ids => removed_ids
        """
        out: Set[str] = set()
        for lid, rec in (self.data.get("listings") or {}).items():
            if not isinstance(rec, dict):
                continue
            st = (rec.get("status") or "active").lower()
            if st == "active":
                out.add(lid)
        return out