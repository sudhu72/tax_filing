"""
Audit logging middleware: records API requests for compliance.
"""
from __future__ import annotations

import logging
from datetime import datetime, UTC
from pathlib import Path

logger = logging.getLogger("audit")


def setup_audit_log(data_dir: str = "data") -> None:
    path = Path(data_dir) / "audit.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_request(method: str, path: str, run_id: str | None = None, status: int = 200) -> None:
    ts = datetime.now(UTC).isoformat()
    msg = f"{ts} {method} {path}"
    if run_id:
        msg += f" run_id={run_id}"
    msg += f" status={status}"
    logger.info(msg)
