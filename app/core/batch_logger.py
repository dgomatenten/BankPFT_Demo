"""Shared batch-processing logger — writes timestamped entries to a per-batch file.

Usage::

    from app.core.batch_logger import BatchLogger

    logger = BatchLogger(batch_id)
    logger.log("START", "Batch initiated")
    ...
    logger.close()
"""

import os

from app.core.time_utils import utc_now

BATCH_LOG_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "instance", "batch_logs")
)


class BatchLogger:
    """Writes timestamped processing log entries to a per-batch file."""

    def __init__(self, batch_id: str):
        os.makedirs(BATCH_LOG_DIR, exist_ok=True)
        self.path = os.path.join(BATCH_LOG_DIR, f"batch_{batch_id}.log")
        self._fh = open(self.path, "w", encoding="utf-8")

    def log(self, level: str, msg: str) -> None:
        ts = utc_now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self._fh.write(f"[{ts}] [{level:<8}] {msg}\n")
        self._fh.flush()

    def info(self, msg: str) -> None:
        self.log("INFO", msg)

    def warning(self, msg: str) -> None:
        self.log("WARNING", msg)

    def error(self, msg: str) -> None:
        self.log("ERROR", msg)

    def close(self) -> None:
        self._fh.close()
