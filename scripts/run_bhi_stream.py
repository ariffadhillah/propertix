# import re
# from scraper.sites.bali_home_immo.adapter import BaliHomeImmoAdapter
# from scraper.core.runner import run_site_stream

# def main(limit=None):
#     adapter = BaliHomeImmoAdapter()

#     start_url = "https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false"

#     # sanitize run id biar aman untuk Windows filename
#     run_id = re.sub(r"[^\w\-]", "_", adapter.scrape_run_id)

#     stats = run_site_stream(
#         adapter=adapter,
#         start_url=start_url,
#         out_path=f"out/bhi_{run_id}.jsonl",
#         state_path="state/bhi.json",
#         limit=limit
#     )

#     print(stats)

# if __name__ == "__main__":
#     main(limit=10)


from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from scraper.sites.bali_home_immo.adapter import BaliHomeImmoAdapter
from scraper.core.runner import run_site_stream


START_URL = "https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false"


def safe_filename(s: str) -> str:
    # contoh: 2026-02-26T10:11:12.123456+00:00 -> 2026-02-26T10_11_12_123456_00_00
    return (
        s.replace(":", "_")
        .replace(".", "_")
        .replace("+", "_")
        .replace("-", "-")
    )


def main(limit: int | None = 30, output_mode: str = "delta") -> None:
    adapter = BaliHomeImmoAdapter()

    run_id = adapter.scrape_run_id
    out_dir = Path("out")
    out_path = out_dir / f"bhi_{safe_filename(run_id)}.jsonl"

    state_dir = Path("state")
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = str(state_dir / "bhi.json")

    stats = run_site_stream(
        adapter=adapter,
        start_url=START_URL,
        out_path=str(out_path),
        state_path=state_path,
        limit=limit,
        output_mode=output_mode,  # "delta" atau "snapshot"
    )

    print(stats)


if __name__ == "__main__":
    # default: delta (hemat, hanya new/updated/removed)
    main(limit=30, output_mode="delta")

    # kalau mau selalu ada output untuk unchanged juga:
    # main(limit=30, output_mode="snapshot")