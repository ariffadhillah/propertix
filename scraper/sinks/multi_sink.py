# # # # scraper/sinks/multi_sink.py
# # # from __future__ import annotations

# # # from typing import Any, Dict, Iterable, List, Optional

# # # from .base import Sink


# # # class MultiSink(Sink):
# # #     """
# # #     Fan-out sink: write the same record to multiple sinks (e.g. SQLite + JSONL).
# # #     """

# # #     def __init__(self, sinks: Iterable[Sink]):
# # #         self.sinks: List[Sink] = [s for s in sinks if s is not None]

# # #     def write(self, record: Dict[str, Any], change_type: str) -> None:
# # #         for s in self.sinks:
# # #             s.write(record, change_type)

# # #     def close(self) -> None:
# # #         for s in self.sinks:
# # #             try:
# # #                 s.close()
# # #             except Exception:
# # #                 pass

# # # scraper/sinks/multi_sink.py
# # from __future__ import annotations

# # from typing import Any, Dict, Iterable, List, Optional, Tuple

# # from .base import Sink


# # class MultiSink(Sink):
# #     """
# #     Fan-out sink: write the same record to multiple sinks (e.g. SQLite + JSONL).

# #     strict=False:
# #       - if one sink fails, we keep writing to others.
# #     strict=True:
# #       - first error will be raised (fail fast).
# #     """

# #     def __init__(self, sinks: Iterable[Sink], *, strict: bool = False):
# #         self.sinks: List[Sink] = [s for s in sinks if s is not None]
# #         self.strict = strict

# #         if not self.sinks:
# #             raise ValueError("MultiSink requires at least 1 sink")

# #     def write(self, record: Dict[str, Any], change_type: str) -> None:
# #         errors: List[Tuple[str, Exception]] = []

# #         for s in self.sinks:
# #             try:
# #                 s.write(record, change_type)
# #             except Exception as e:
# #                 if self.strict:
# #                     raise
# #                 errors.append((s.__class__.__name__, e))

# #         # optional: you can log errors here if you have a logger
# #         # if errors:
# #         #     print("[MultiSink] write errors:", errors)

# #     def close(self) -> None:
# #         for s in self.sinks:
# #             try:
# #                 s.close()
# #             except Exception:
# #                 if self.strict:
# #                     raise
# #                 pass


# # scraper/sinks/multi_sink.py
# from __future__ import annotations

# from typing import Any, Dict, Iterable, List, Tuple

# from .base import Sink


# class MultiSink(Sink):
#     """
#     Fan-out sink: write the same record to multiple sinks (e.g. SQLite + JSONL).

#     strict=False:
#       - if one sink fails, we keep writing to others.
#     strict=True:
#       - first error will be raised (fail fast).
#     """

#     def __init__(self, sinks: Iterable[Sink], *, strict: bool = False):
#         self.sinks: List[Sink] = [s for s in sinks if s is not None]
#         self.strict = strict

#         if not self.sinks:
#             raise ValueError("MultiSink requires at least 1 sink")

#     def write(self, record: Dict[str, Any], change_type: str) -> None:
#         errors: List[Tuple[str, Exception]] = []

#         for s in self.sinks:
#             try:
#                 s.write(record, change_type)
#             except Exception as e:
#                 if self.strict:
#                     raise
#                 errors.append((s.__class__.__name__, e))

#         # Optional: print/log errors if you want:
#         # if errors:
#         #     print("[MultiSink] write errors:", [(n, str(e)) for n, e in errors])

#     def close(self) -> None:
#         for s in self.sinks:
#             try:
#                 s.close()
#             except Exception:
#                 if self.strict:
#                     raise


# scraper/sinks/multi_sink.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .base import Sink


class MultiSink(Sink):
    """
    Fan-out sink: write the same record to multiple sinks (e.g. SQLite + JSONL).

    strict=False:
      - kalau salah satu sink gagal, sink lain tetap jalan (lebih aman untuk dev/test)
    strict=True:
      - kalau salah satu sink gagal, raise error
    """

    def __init__(self, sinks: Iterable[Sink], strict: bool = True):
        self.sinks: List[Sink] = [s for s in sinks if s is not None]
        self.strict = strict

    def write(self, record: Dict[str, Any], change_type: str) -> None:
        errors: list[Exception] = []
        for s in self.sinks:
            try:
                s.write(record, change_type)
            except Exception as e:
                if self.strict:
                    raise
                errors.append(e)
        # strict=False -> kita abaikan errors (atau kamu bisa print log jika mau)

    def close(self) -> None:
        for s in self.sinks:
            try:
                s.close()
            except Exception:
                if self.strict:
                    raise
                pass