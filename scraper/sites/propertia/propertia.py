from __future__ import annotations
import re
from typing import Iterable, Dict, Any, List
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

class PropertiaAdapter:
    source_name = "propertia"

    def __init__(self, start_url: str):
        self.start_url = start_url
        self.sess = requests.Session()
        self.sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PropertixBot/0.1"
        })

    def iter_list_pages(self) -> Iterable[str]:
        # MVP: start from 1 list page only, nanti kamu perlu tambah pagination.
        yield self.start_url

    def parse_list_page(self, url: str) -> List[Dict[str, Any]]:
        r = self.sess.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        items = []

        # TODO: ganti selector ini sesuai HTML propertia
        # contoh:
        # for card in soup.select(".listing-card a.listing-link"):
        #     href = card.get("href")
        #     items.append({"url": href, "source_listing_id": extract_id(href)})

        return items

    def parse_detail_page(self, item: Dict[str, Any]) -> Dict[str, Any]:
        url = item["url"]
        r = self.sess.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # TODO: ganti selector sesuai detail page
        title = None

        listing_id = item.get("source_listing_id") or self._extract_id(url) or url

        return {
            "source_listing_id": listing_id,
            "source_url": url,
            "title": title,
            "description": None,
            "intent": "unknown",
            "property_type": "unknown",
            "price": None,
            "bedrooms": None,
            "bathrooms": None,
            "land_size_sqm": None,
            "building_size_sqm": None,
            "location": None,
            "images": [],
            "broker_name": None,
            "broker_phone": None,
            "broker_email": None,
            "raw": {
                "debug": {
                    "fetched_url": url,
                }
            }
        }

    def _extract_id(self, url: str) -> str | None:
        # contoh: ambil angka/slug terakhir
        m = re.search(r"/(\d+)(?:/)?$", url)
        return m.group(1) if m else None