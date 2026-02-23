from pathlib import Path
import orjson
from typing import Any, Dict, Iterable

# run_id = datetime.utcnow().isoformat()

# "ScrapeRunId": run_id,
# "ScrapedAt": now_iso,
# "SourceKey": "bali-home-immo"

def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for row in rows:
            f.write(orjson.dumps(row))
            f.write(b"\n")


def append_jsonl(path: str, record: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("ab") as f:
        f.write(orjson.dumps(record))
        f.write(b"\n")
