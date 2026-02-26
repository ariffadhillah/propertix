from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class Sink(ABC):
    """
    Sink menerima 'record' (nested schema client) dan stats change-type.
    Sink boleh memutuskan mau simpan apa.
    """

    @abstractmethod
    def write(self, record: Dict[str, Any], change_type: str) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...