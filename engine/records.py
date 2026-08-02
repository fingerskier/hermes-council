"""Durable session records — synthesis with preserved dissent."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import record_path, scratch_dir


def write_record(
    root: Path,
    *,
    session_id: str,
    mode: str,
    chair: str,
    seats: List[str],
    task: str,
    recommendation: str,
    reasoning: str,
    dissents: str,
    follow_ups: str = "",
    memory_topics: Optional[List[str]] = None,
    archive_scratch: bool = True,
) -> Dict[str, Any]:
    """Write a record and optionally archive the scratchpad."""
    concluded = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    title = _title_from_task(task)
    mem_lines = []
    if memory_topics:
        for t in memory_topics:
            mem_lines.append(f"→ memory updated: `memory/{t}.md`")
    else:
        mem_lines.append("→ memory updated: none")

    body = (
        f"# Record — {title}\n"
        f"\n"
        f"- **Session:** {session_id}\n"
        f"- **Mode:** {mode}\n"
        f"- **Concluded:** {concluded}\n"
        f"- **Chair:** {chair}\n"
        f"- **Seats:** {', '.join(seats)}\n"
        f"- **Task:** {task}\n"
        f"\n"
        f"## Recommendation\n"
        f"{recommendation.strip()}\n"
        f"\n"
        f"## Reasoning trail\n"
        f"{reasoning.strip()}\n"
        f"\n"
        f"## Dissents (preserved)\n"
        f"{(dissents.strip() or '_No dissent recorded._')}\n"
        f"\n"
        f"## Follow-ups\n"
        f"{(follow_ups.strip() or '_None._')}\n"
        f"\n"
        + "\n".join(mem_lines)
        + "\n"
    )

    out = record_path(root, session_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")

    scratch_src = scratch_dir(root) / f"{session_id}.md"
    scratch_dst = None
    if archive_scratch and scratch_src.exists():
        scratch_dst = out.with_suffix(".scratch.md")
        shutil.move(str(scratch_src), str(scratch_dst))

    return {
        "ok": True,
        "record": str(out),
        "scratch_archive": str(scratch_dst) if scratch_dst else None,
        "session_id": session_id,
    }


def validate_record_text(text: str) -> List[str]:
    """Return a list of format problems (empty if ok)."""
    problems: List[str] = []
    for field in ("Session", "Mode", "Concluded", "Chair", "Seats", "Task"):
        if f"- **{field}:** " not in text:
            problems.append(f"missing field: {field}")
    for heading in (
        "## Recommendation",
        "## Reasoning trail",
        "## Dissents (preserved)",
        "## Follow-ups",
    ):
        if heading not in text:
            problems.append(f"missing section: {heading}")
    # Dissents section must exist and be non-empty (Gate 1)
    m = re.search(
        r"## Dissents \(preserved\)\n(.*?)(?:\n## |\n→ |\Z)",
        text,
        re.DOTALL,
    )
    if not m or not m.group(1).strip():
        problems.append("dissents section empty")
    return problems


def _title_from_task(task: str) -> str:
    t = task.strip()
    if len(t) > 80:
        t = t[:77] + "..."
    return t[0].upper() + t[1:] if t else "Session"
