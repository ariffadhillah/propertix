from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from .base import Sink


class SQLiteSink(Sink):
    """
    Simple test DB sink.
    Simpan record JSON full + index fields minimal.

    Notes:
    - Upsert by listing_key (ListingKey)
    - commit batching untuk performa
    """

    def __init__(self, db_path: str, commit_every: int = 50):
        self.db_path = db_path
        self.commit_every = max(int(commit_every), 1)
        self._pending = 0

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
              listing_key TEXT PRIMARY KEY,
              source_key TEXT,
              source_listing_id TEXT,
              source_url TEXT,

              last_change_type TEXT,
              current_status TEXT,
              captured_at TEXT,

              canonical_content_hash TEXT,
              raw_payload_hash TEXT,

              record_json TEXT
            );
            """
        )

        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source_key);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_hash ON listings(canonical_content_hash);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(current_status);")
        self.conn.commit()

    def write(self, record: Dict[str, Any], change_type: str) -> None:
        listing = record.get("listing") or {}
        hashes = record.get("hashes") or {}
        ingestion = record.get("ingestion") or {}
        status = record.get("status") or {}

        listing_key = listing.get("ListingKey")
        if not listing_key:
            return

        payload = json.dumps(record, ensure_ascii=False)

        # Runner sudah set status.last_change_type, tapi fallback ke arg change_type
        last_change_type = status.get("last_change_type") or change_type

        self.conn.execute(
            """
            INSERT INTO listings (
              listing_key, source_key, source_listing_id, source_url,
              last_change_type, current_status, captured_at,
              canonical_content_hash, raw_payload_hash,
              record_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(listing_key) DO UPDATE SET
              source_key=excluded.source_key,
              source_listing_id=excluded.source_listing_id,
              source_url=excluded.source_url,
              last_change_type=excluded.last_change_type,
              current_status=excluded.current_status,
              captured_at=excluded.captured_at,
              canonical_content_hash=excluded.canonical_content_hash,
              raw_payload_hash=excluded.raw_payload_hash,
              record_json=excluded.record_json
            ;
            """,
            (
                listing_key,
                listing.get("source"),
                listing.get("source_listing_id"),
                listing.get("source_url"),
                last_change_type,
                status.get("current_status"),
                ingestion.get("captured_at"),
                hashes.get("canonical_content_hash"),
                hashes.get("raw_payload_hash"),
                payload,
            ),
        )

        self._pending += 1
        if self._pending >= self.commit_every:
            self.conn.commit()
            self._pending = 0

    def close(self) -> None:
        try:
            if self._pending:
                self.conn.commit()
                self._pending = 0
            self.conn.close()
        except Exception:
            pass