from pathlib import Path
from scraper.core.runner import run_adapter
from scraper.sites.bali_home_immo.adapter import BaliHomeImmoAdapter

if __name__ == "__main__":
    adapter = BaliHomeImmoAdapter(
        # WAJIB ganti ke halaman list yang berisi banyak listing
        # start_url="https://bali-home-immo.com/realestate-property"
            start_url="https://bali-home-immo.com/realestate-property/for-sale/villa/all?ref_tab=sale&property_category=villa&min_price=0&max_price=0&price_on_request=false&page=1"
    )

    summary = run_adapter(
        adapter=adapter,
        out_dir=Path("scraper/out"),
        state_path=Path("scraper/state/bali_home_immo_state.json"),
        max_pages=1,
    )
    print(summary)