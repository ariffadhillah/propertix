
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from pathlib import Path
from scraper.core.runner import run_adapter
from scraper.sites.propertia.propertia import PropertiaAdapter

if __name__ == "__main__":
    adapter = PropertiaAdapter(
        start_url="https://propertia.com/"  # TODO: ganti ke URL list yang benar
    )

    summary = run_adapter(
        adapter=adapter,
        out_dir=Path("scraper/out"),
        state_path=Path("scraper/state/propertia_state.json"),
        max_pages=1,
    )

    print(summary)