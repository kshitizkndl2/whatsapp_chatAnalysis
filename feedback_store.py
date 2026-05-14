"""
Save user feedback as .txt files on the server.

Set ``FEEDBACK_LOG_DIR`` as an environment variable (e.g. on Render: path on a
persistent disk), or optionally in ``.streamlit/secrets.toml`` for local runs.
If unset, files go under ``./feedback_logs`` next to this package (ephemeral on
many PaaS hosts).
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path


def _feedback_log_dir_override() -> str:
    root = os.environ.get("FEEDBACK_LOG_DIR", "").strip()
    if root:
        return root
    try:
        import streamlit as st

        sec = getattr(st, "secrets", None)
        if sec is not None and "FEEDBACK_LOG_DIR" in sec:
            return str(sec["FEEDBACK_LOG_DIR"]).strip()
    except Exception:
        pass
    return ""


def feedback_dir() -> Path:
    root = _feedback_log_dir_override()
    p = Path(root).expanduser() if root else Path(__file__).resolve().parent / "feedback_logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_feedback(user_message: str, error_text: str) -> Path:
    """Write one UTF-8 .txt file; return path (for logging only, not shown to end users)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    token = secrets.token_hex(4)
    path = feedback_dir() / f"feedback_{ts}_{token}.txt"
    msg = (user_message or "").strip()
    err = (error_text or "").strip()
    body = "\n".join(
        [
            "=== WhatsApp Chat Analysis — user feedback ===",
            f"Saved (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "--- User message ---",
            msg if msg else "(empty)",
            "",
            "--- Error / technical details (user pasted) ---",
            err if err else "(empty)",
            "",
            "=== End ===",
        ]
    )
    path.write_text(body, encoding="utf-8")
    return path


def list_feedback_files() -> list[Path]:
    d = feedback_dir()
    files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".txt" and p.name.startswith("feedback_")]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def read_feedback(path: Path) -> str:
    return path.read_text(encoding="utf-8")
