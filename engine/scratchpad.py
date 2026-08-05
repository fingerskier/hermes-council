"""Shared scratchpad for meeting/work sessions."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_C0_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def scrub_text(text: str) -> str:
    """Remove terminal controls and bare CR without damaging Unicode text."""
    normalized = str(text).replace("\r\n", "\n").replace("\r", "")
    return _C0_RE.sub("", normalized)


def _safe_content(text: str) -> str:
    """Scrub controls, then prevent model text from forging turn headers."""
    clean = scrub_text(text).strip()
    return "\n".join(
        f" {line}" if line.startswith("## Turn") else line
        for line in clean.split("\n")
    )


def init_scratch(
    path: Path,
    *,
    session_id: str,
    mode: str,
    task: str,
    chair: str,
    seats: list[str],
    started_epoch: int,
    seat_snapshots: Optional[list[Dict[str, Any]]] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.fromtimestamp(started_epoch, tz=timezone.utc).astimezone()
    snapshot_lines = ""
    for row in seat_snapshots or []:
        model = str(row.get("model") or "<host-default>")
        digest = str(row.get("content_hash") or "")
        snapshot_lines += (
            f"- **Seat snapshot:** {row.get('name')} model={model} "
            f"sha256={digest}\n"
        )
    header = (
        f"# Scratchpad — {session_id}\n"
        f"\n"
        f"- **Session:** {session_id}\n"
        f"- **Mode:** {mode}\n"
        f"- **Task:** {task}\n"
        f"- **Chair:** {chair}\n"
        f"- **Seats:** {', '.join(seats)}\n"
        f"- **Started:** {started.strftime('%Y-%m-%d %H:%M')}\n"
        f"- **Started(epoch):** {started_epoch}\n"
        f"{snapshot_lines}"
        f"\n"
        f"---\n"
        f"\n"
    )
    path.write_text(header, encoding="utf-8")


def append_turn(
    path: Path,
    *,
    seat: str,
    title: str,
    turn: int,
    content: str,
    kind: str = "seat",
) -> None:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    safe_content = _safe_content(content)
    block = (
        f"## Turn {turn} — {seat} ({title}) [{kind}] — {stamp}\n"
        f"\n"
        f"{safe_content}\n"
        f"\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)


def append_user_steer(path: Path, *, turn: int, content: str) -> None:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    safe_content = _safe_content(content)
    block = (
        f"## Turn {turn} — USER STEER — {stamp}\n"
        f"\n"
        f"{safe_content}\n"
        f"\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)


def read_scratch(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def scratch_size(path: Path) -> int:
    if not path.exists():
        return 0
    return path.stat().st_size


def parse_header_field(text: str, field: str) -> Optional[str]:
    """Read a field from the header block only (above the first ---)."""
    header = text.split("\n---\n", 1)[0]
    needle = f"- **{field}:** "
    for line in header.splitlines():
        if line.startswith(needle):
            return line[len(needle) :].strip()
    return None
