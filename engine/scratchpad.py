"""Shared scratchpad for meeting/work sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def init_scratch(
    path: Path,
    *,
    session_id: str,
    mode: str,
    task: str,
    chair: str,
    seats: list[str],
    started_epoch: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.fromtimestamp(started_epoch, tz=timezone.utc).astimezone()
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
    block = (
        f"## Turn {turn} — {seat} ({title}) [{kind}] — {stamp}\n"
        f"\n"
        f"{content.strip()}\n"
        f"\n"
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)


def append_user_steer(path: Path, *, turn: int, content: str) -> None:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    block = (
        f"## Turn {turn} — USER STEER — {stamp}\n"
        f"\n"
        f"{content.strip()}\n"
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
