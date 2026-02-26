from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set


@dataclass
class StateRow:
    listing_id: str
    content_hash: Optional[str] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    status: str = "active"  # active | removed


class StateStore:
    """
    Simple JSON-based state store per source_key.
    Stores per listing_id:
      - content_hash
      - first_seen_at
      - last_seen_at
      - status
    """

    def __init__(self, path: Path, source_key: str):
        self.path = path
        self.source_key = source_key
        self.data: Dict[str, Any] = {
            "source_key": source_key,
            "last_run_id": None,
            "items": {},  # listing_id -> row dict
        }

    def load(self) -> None:
        if not self.path.exists():
            # fresh store
            self._ensure_shape()
            return

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = raw
            else:
                self.data = {}
        except Exception:
            self.data = {}

        self._ensure_shape()

    def save(self) -> None:
        self._ensure_shape()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _ensure_shape(self) -> None:
        if not isinstance(self.data, dict):
            self.data = {}
        self.data.setdefault("source_key", self.source_key)
        self.data.setdefault("last_run_id", None)
        self.data.setdefault("items", {})
        if not isinstance(self.data["items"], dict):
            self.data["items"] = {}

    def get(self, listing_id: str) -> Optional[StateRow]:
        self._ensure_shape()
        items = self.data.get("items") or {}
        row = items.get(listing_id)
        if not isinstance(row, dict):
            return None

        return StateRow(
            listing_id=listing_id,
            content_hash=row.get("content_hash"),
            first_seen_at=row.get("first_seen_at"),
            last_seen_at=row.get("last_seen_at"),
            status=row.get("status") or "active",
        )

    def upsert(
        self,
        listing_id: str,
        content_hash: Optional[str] = None,
        first_seen_at: Optional[str] = None,
        last_seen_at: Optional[str] = None,
        status: str = "active",
    ) -> None:
        self._ensure_shape()
        items = self.data["items"]

        existing = items.get(listing_id)
        if not isinstance(existing, dict):
            existing = {}

        # preserve first_seen_at if already present
        if existing.get("first_seen_at") and not first_seen_at:
            first_seen_at = existing.get("first_seen_at")

        items[listing_id] = {
            "content_hash": content_hash if content_hash is not None else existing.get("content_hash"),
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
            "status": status or existing.get("status") or "active",
        }

    def all_active_ids(self) -> Set[str]:
        self._ensure_shape()
        items = self.data.get("items") or {}
        out: Set[str] = set()

        for lid, row in items.items():
            if not isinstance(row, dict):
                continue
            if (row.get("status") or "active") == "active":
                out.add(lid)

        return out