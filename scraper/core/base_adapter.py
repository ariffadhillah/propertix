from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Dict, Any

class BaseAdapter(ABC):
    source_name: str

    @abstractmethod
    def iter_list_pages(self) -> Iterable[str]:
        ...

    @abstractmethod
    def parse_list_page(self, url: str) -> list[Dict[str, Any]]:
        """Return list of minimal items: {source_listing_id, url}"""
        ...

    @abstractmethod
    def parse_detail_page(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Return normalized listing dict (without content_hash)"""
        ...