from __future__ import annotations
from pathlib import Path
from typing import Any, Dict

from scraper.core.jsonl import append_jsonl
from .base import Sink


class JsonlSink(Sink):
    def __init__(self, out_path: str):
        self.out_path = out_path
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)

    def write(self, record: Dict[str, Any], change_type: str) -> None:
        append_jsonl(self.out_path, record)

    def close(self) -> None:
        pass