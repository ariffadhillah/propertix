# # scripts/cli.py
# from __future__ import annotations

# import argparse
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Callable
# from typing import Sequence
# from scraper.core.runner import run_site_stream


# # ----------------------------
# # Registry: map "site name" -> adapter factory + start_url
# # Nanti tambah site baru cukup tambah 1 entry di sini.
# # ----------------------------




# # @dataclass(frozen=True)
# # class SiteConfig:
# #     key: str
# #     start_url: str
# #     adapter_factory: Callable[[], object]


# # SITE_REGISTRY: dict[str, SiteConfig] = {
# #     "bali-home-immo": SiteConfig(
# #         key="bali-home-immo",
# #         start_url="https://bali-home-immo.com/realestate-property/for-sale",
# #         start_url="https://bali-home-immo.com/realestate-property/for-rent",
# #         adapter_factory=_bhi_adapter,
# #     ),
# #     # "propertia": SiteConfig(
# #     #     key="propertia",
# #     #     start_url="https://propertia.com/wp-admin/admin-ajax.php?paged=1&listing_page_id=23498&ne_lat=&ne_lng=&sw_lat=&sw_lng=&zoom=&keyword=&bedrooms=&min-price=&max-price=&min-land-area=&max-land-area=&min-area=&search_args=eyJwb3N0X3R5cGUiOiJwcm9wZXJ0eSIsInBvc3RzX3Blcl9wYWdlIjo1MCwicGFnZWQiOjIsInBvc3Rfc3RhdHVzIjpbInB1Ymxpc2giLCJob3V6ZXpfc29sZCJdLCJvcmRlcmJ5IjoiZGF0ZSIsIm9yZGVyIjoiREVTQyJ9&search_URI=paged%3D2&search_geolocation=&houzez_save_search_ajax=f2d7bb2f80&action=houzez_half_map_listings&sortby=d_date&item_layout=v1&layout_css=listing-view+grid-view+row+row-cols-1+row-cols-md-2+gy-4+gx-4+mx-0&layout_view=grid&is_pagination_request=false",
# #     #     adapter_factory=_propertia_adapter,
# #     # ),

# #         # contoh nanti:
# #     "propertia": SiteConfig(
# #         key="propertia",
# #         start_url="https://propertia.com/search-results-3/?listing_page_id=23498",
# #         adapter_factory=_propertia_adapter,
# #     ),
# # }





# @dataclass(frozen=True)
# class SiteConfig:
#     key: str
#     start_urls: Sequence[str]
#     adapter_factory: Callable[[], object]

# def _bhi_adapter():
#     from scraper.sites.bali_home_immo.adapter import BaliHomeImmoAdapter
#     return BaliHomeImmoAdapter()

# def _propertia_adapter():
#     from scraper.sites.propertia.adapter import PropertiaAdapter
#     return PropertiaAdapter()

# SITE_REGISTRY: dict[str, SiteConfig] = {
#     "bali-home-immo": SiteConfig(
#         key="bali-home-immo",
#         start_urls=[
#             "https://bali-home-immo.com/realestate-property/for-sale",
#             "https://bali-home-immo.com/realestate-property/for-rent",
#         ],
#         adapter_factory=_bhi_adapter,
#     ),

#     "propertia": SiteConfig(
#         key="propertia",
#         start_urls=[
#             "https://propertia.com/search-results-3/?listing_page_id=23498"
#         ],
#         adapter_factory=_propertia_adapter,
#     ),
# }

# def safe_filename(run_id: str) -> str:
#     # 2026-02-26T10:11:12.123456+00:00 -> 2026-02-26T10_11_12_123456_00_00
#     return run_id.replace(":", "_").replace(".", "_").replace("+", "_")


# def build_paths(site_key: str, run_id: str, env: str) -> tuple[str, str]:
#     """
#     env:
#       - "prod": out/ + state/
#       - "test": out_test/ + state_test/
#     """
#     if env == "test":
#         out_dir = Path("out_test")
#         state_dir = Path("state_test")
#     else:
#         out_dir = Path("out")
#         state_dir = Path("state")

#     out_dir.mkdir(parents=True, exist_ok=True)
#     state_dir.mkdir(parents=True, exist_ok=True)

#     out_path = out_dir / f"{site_key}_{safe_filename(run_id)}.jsonl"
#     state_path = state_dir / f"{site_key}.json"

#     return str(out_path), str(state_path)


# def parse_args() -> argparse.Namespace:
#     p = argparse.ArgumentParser(
#         prog="propetix-cli",
#         description="Propetix multi-site scraper runner (prod/test, delta/snapshot, sinks)."
#     )

#     mode_group = p.add_mutually_exclusive_group(required=True)
#     mode_group.add_argument("--start", metavar="SITE", help="Run site in production mode (writes to out/ and state/).")
#     mode_group.add_argument("--start-test", metavar="SITE", help="Run site in test/dev mode (writes to out_test/ and state_test/).")

#     # NEW: sink multi
#     p.add_argument(
#         "--sink",
#         choices=["auto", "jsonl", "sqlite", "multi"],
#         default="auto",
#         help="Output sink. auto=prod->jsonl, test->multi (sqlite+jsonl)."
#     )
#     p.add_argument(
#         "--db-path",
#         default=None,
#         help="SQLite path (e.g. state_test/bali-home-immo.sqlite). If omitted uses per-site default."
#     )

#     p.add_argument("--limit", type=int, default=None, help="Max items to process (e.g. --limit 10).")
#     p.add_argument("--mode", choices=["delta", "snapshot"], default="delta",
#                    help="delta=write only new/updated/removed, snapshot=write all items each run.")
#     p.add_argument("--dry-run", action="store_true",
#                    help="Do not write out/state. Useful for quick debugging.")
#     p.add_argument("--start-url", default=None,
#                    help="Override start URL (optional).")

#     return p.parse_args()


# def _build_sink(env: str, sink_choice: str, site_key: str, out_path: str, db_path: str | None):
#     """
#     Build sink instance based on CLI args.
#     test + auto -> multi (sqlite + jsonl) so user can inspect JSONL easily.
#     """
#     if sink_choice == "auto":
#         sink_choice = "jsonl" if env == "prod" else "multi"

#     if sink_choice == "jsonl":
#         from scraper.sinks.jsonl_sink import JsonlSink
#         return JsonlSink(out_path)

#     if sink_choice == "sqlite":
#         from scraper.sinks.sqlite_sink import SQLiteSink
#         if not db_path:
#             db_dir = "state_test" if env == "test" else "state"
#             db_path = str(Path(db_dir) / f"{site_key}.sqlite")
#         return SQLiteSink(db_path)

#     if sink_choice == "multi":
#         from scraper.sinks.jsonl_sink import JsonlSink
#         from scraper.sinks.sqlite_sink import SQLiteSink
#         from scraper.sinks.multi_sink import MultiSink

#         if not db_path:
#             db_dir = "state_test" if env == "test" else "state"
#             db_path = str(Path(db_dir) / f"{site_key}.sqlite")

#         return MultiSink([SQLiteSink(db_path), JsonlSink(out_path)], strict=False)

#     raise ValueError(f"Unknown sink_choice: {sink_choice}")


# # def main() -> None:
# #     args = parse_args()

# #     env = "prod" if args.start else "test"
# #     site_key = args.start or args.start_test

# #     cfg = SITE_REGISTRY.get(site_key)
# #     if not cfg:
# #         known = ", ".join(sorted(SITE_REGISTRY.keys()))
# #         raise SystemExit(f"Unknown site '{site_key}'. Known sites: {known}")

# #     adapter = cfg.adapter_factory()
# #     start_url = args.start_url or cfg.start_url

# #     run_id = getattr(adapter, "scrape_run_id", None)
# #     if not run_id:
# #         from datetime import datetime, timezone
# #         run_id = datetime.now(timezone.utc).isoformat()

# #     out_path, state_path = build_paths(site_key, run_id, env=env)

# #     if args.dry_run:
# #         out_path = str(Path(out_path).with_suffix(".dryrun.jsonl"))
# #         state_path = str(Path(state_path).with_suffix(".dryrun.json"))

# #     sink = _build_sink(env, args.sink, site_key, out_path, args.db_path)

# #     stats = run_site_stream(
# #         adapter=adapter,
# #         start_url=start_url,
# #         out_path=out_path,
# #         state_path=state_path,
# #         limit=args.limit,
# #         output_mode=args.mode,   # delta/snapshot
# #         sink=sink,
# #     )

# #     print(f"[{site_key}] env={env} mode={args.mode} limit={args.limit} dry_run={args.dry_run} sink={args.sink}")
# #     print(f"out_path={out_path}")
# #     print(f"state_path={state_path}")
# #     if env == "test" and args.sink in ("auto", "multi", "sqlite") and (args.sink != "jsonl"):
# #         # helpful hint: where sqlite likely is
# #         if args.db_path:
# #             print(f"db_path={args.db_path}")
# #         else:
# #             print(f"db_path={(Path('state_test') / f'{site_key}.sqlite')}")
# #     print(stats)

# def main() -> None:
#     args = parse_args()

#     env = "prod" if args.start else "test"
#     site_key = args.start or args.start_test

#     cfg = SITE_REGISTRY.get(site_key)
#     if not cfg:
#         known = ", ".join(sorted(SITE_REGISTRY.keys()))
#         raise SystemExit(f"Unknown site '{site_key}'. Known sites: {known}")

#     adapter = cfg.adapter_factory()

#     # ✅ multi start urls + override
#     if args.start_url:
#         urls = [args.start_url]
#     else:
#         urls = list(cfg.start_urls)

#     # ✅ one run_id for the whole CLI run (so all urls share same output file/run)
#     run_id = getattr(adapter, "scrape_run_id", None)
#     if not run_id:
#         from datetime import datetime, timezone
#         run_id = datetime.now(timezone.utc).isoformat()

#     out_path, state_path = build_paths(site_key, run_id, env=env)

#     if args.dry_run:
#         out_path = str(Path(out_path).with_suffix(".dryrun.jsonl"))
#         state_path = str(Path(state_path).with_suffix(".dryrun.json"))

#     sink = _build_sink(env, args.sink, site_key, out_path, args.db_path)

#     # ✅ run each url sequentially
#     all_stats = []
#     for i, start_url in enumerate(urls, start=1):
#         print(f"[{site_key}] ({i}/{len(urls)}) start_url={start_url}")

#         stats = run_site_stream(
#             adapter=adapter,
#             start_url=start_url,
#             out_path=out_path,
#             state_path=state_path,
#             limit=args.limit,
#             output_mode=args.mode,   # delta/snapshot
#             sink=sink,
#         )
#         all_stats.append(stats)

#     print(f"[{site_key}] env={env} mode={args.mode} limit={args.limit} dry_run={args.dry_run} sink={args.sink}")
#     print(f"out_path={out_path}")
#     print(f"state_path={state_path}")

#     if env == "test" and args.sink in ("auto", "multi", "sqlite") and (args.sink != "jsonl"):
#         if args.db_path:
#             print(f"db_path={args.db_path}")
#         else:
#             print(f"db_path={(Path('state_test') / f'{site_key}.sqlite')}")

#     # print stats summary
#     print(all_stats)

# if __name__ == "__main__":
#     main()

# # v3

# scripts/cli.py
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from scraper.core.runner import run_site_stream_multi


@dataclass(frozen=True)
class SiteConfig:
    key: str
    start_urls: Sequence[str]
    adapter_factory: Callable[[], object]


def _bhi_adapter():
    from scraper.sites.bali_home_immo.adapter import BaliHomeImmoAdapter
    return BaliHomeImmoAdapter()


def _propertia_adapter():
    from scraper.sites.propertia.adapter import PropertiaAdapter
    return PropertiaAdapter()


SITE_REGISTRY: dict[str, SiteConfig] = {
    "bali-home-immo": SiteConfig(
        key="bali-home-immo",
        start_urls=(
            "https://bali-home-immo.com/realestate-property/for-sale",
            "https://bali-home-immo.com/realestate-property/for-rent",
        ),
        adapter_factory=_bhi_adapter,
    ),
    "propertia": SiteConfig(
        key="propertia",
        start_urls=(
            "https://propertia.com/search-results-3/?listing_page_id=23498",
        ),
        adapter_factory=_propertia_adapter,
    ),
}


def safe_filename(run_id: str) -> str:
    return run_id.replace(":", "_").replace(".", "_").replace("+", "_")


def build_paths(site_key: str, run_id: str, env: str) -> tuple[str, str]:
    if env == "test":
        out_dir = Path("out_test")
        state_dir = Path("state_test")
    else:
        out_dir = Path("out")
        state_dir = Path("state")

    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{site_key}_{safe_filename(run_id)}.jsonl"
    state_path = state_dir / f"{site_key}.json"
    return str(out_path), str(state_path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="propetix-cli",
        description="Propetix multi-site scraper runner (prod/test, delta/snapshot, sinks).",
    )

    mode_group = p.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--start", metavar="SITE", help="Run site in production mode (out/ + state/).")
    mode_group.add_argument("--start-test", metavar="SITE", help="Run site in test mode (out_test/ + state_test/).")

    p.add_argument(
        "--schema",
        choices=["legacy", "v3"],
        default="legacy",
        help="Output schema version. legacy=default, v3=client v3 exporter.",
    )
    p.add_argument("--v3", action="store_true", help="Shortcut for --schema v3")

    p.add_argument("--sink", choices=["auto", "jsonl", "sqlite", "multi"], default="auto")
    p.add_argument("--db-path", default=None)

    p.add_argument("--limit", type=int, default=None, help="Max items to process (global across all start_urls).")
    p.add_argument("--mode", choices=["delta", "snapshot"], default="delta")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--start-url", default=None, help="Override start URL (single).")

    return p.parse_args()


def build_sink(env: str, sink_choice: str, site_key: str, out_path: str, db_path: str | None):
    if sink_choice == "auto":
        sink_choice = "jsonl" if env == "prod" else "multi"

    if sink_choice == "jsonl":
        from scraper.sinks.jsonl_sink import JsonlSink
        return JsonlSink(out_path)

    if sink_choice == "sqlite":
        from scraper.sinks.sqlite_sink import SQLiteSink
        if not db_path:
            db_dir = "state_test" if env == "test" else "state"
            db_path = str(Path(db_dir) / f"{site_key}.sqlite")
        return SQLiteSink(db_path)

    if sink_choice == "multi":
        from scraper.sinks.jsonl_sink import JsonlSink
        from scraper.sinks.sqlite_sink import SQLiteSink
        from scraper.sinks.multi_sink import MultiSink

        if not db_path:
            db_dir = "state_test" if env == "test" else "state"
            db_path = str(Path(db_dir) / f"{site_key}.sqlite")

        return MultiSink([SQLiteSink(db_path), JsonlSink(out_path)], strict=False)

    raise ValueError(f"Unknown sink_choice: {sink_choice}")


def main() -> None:
    args = parse_args()

    env = "prod" if args.start else "test"
    site_key = args.start or args.start_test

    cfg = SITE_REGISTRY.get(site_key)
    if not cfg:
        known = ", ".join(sorted(SITE_REGISTRY.keys()))
        raise SystemExit(f"Unknown site '{site_key}'. Known sites: {known}")

    adapter = cfg.adapter_factory()

    schema_version = "v3" if args.v3 else (args.schema or "legacy")

    urls = [args.start_url] if args.start_url else list(cfg.start_urls)

    run_id = getattr(adapter, "scrape_run_id", None)
    if not run_id:
        from datetime import datetime, timezone
        run_id = datetime.now(timezone.utc).isoformat()

    out_path, state_path = build_paths(site_key, run_id, env=env)

    if args.dry_run:
        out_path = str(Path(out_path).with_suffix(".dryrun.jsonl"))
        state_path = str(Path(state_path).with_suffix(".dryrun.json"))

    sink = build_sink(env, args.sink, site_key, out_path, args.db_path)

    print(
        f"[{site_key}] env={env} mode={args.mode} limit={args.limit} dry_run={args.dry_run} "
        f"sink={args.sink} schema={schema_version}"
    )
    print(f"[{site_key}] start_urls={len(urls)}")
    for i, u in enumerate(urls, start=1):
        print(f"[{site_key}] ({i}/{len(urls)}) start_url={u}")

    stats = run_site_stream_multi(
        adapter=adapter,
        start_urls=urls,
        out_path=out_path,
        state_path=state_path,
        limit=args.limit,
        output_mode=args.mode,
        sink=sink,
        schema_version=schema_version,
    )

    print(f"out_path={out_path}")
    print(f"state_path={state_path}")

    if env == "test" and args.sink in ("auto", "multi", "sqlite") and args.sink != "jsonl":
        if args.db_path:
            print(f"db_path={args.db_path}")
        else:
            print(f"db_path={Path('state_test') / f'{site_key}.sqlite'}")

    print(stats)


if __name__ == "__main__":
    main()