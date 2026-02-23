from __future__ import annotations
from pathlib import Path
import json
from typing import Dict, Any

class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"listings": {}}, indent=2), encoding="utf-8")

    def load(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_listing(self, key: str) -> Dict[str, Any] | None:
        data = self.load()
        return data["listings"].get(key)

    def upsert_listing(self, key: str, record: Dict[str, Any]) -> None:
        data = self.load()
        data["listings"][key] = record
        self.save(data)

    def all_keys(self):
        data = self.load()
        return set(data["listings"].keys())