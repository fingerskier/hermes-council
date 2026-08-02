"""Read-only council roster table."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .council_io import load_council, load_seat
from .paths import council_yaml


def council_info(root: Path) -> Dict[str, Any]:
    root = root.resolve()
    if not council_yaml(root).exists():
        return {
            "ok": False,
            "error": "not_convened",
            "message": "No council convened yet. Run council convene first.",
        }

    cfg = load_council(root)
    rows: List[Dict[str, Any]] = []
    for name in cfg.seats:
        try:
            seat = load_seat(root, name)
            rows.append(
                {
                    "seat": seat.name,
                    "title": seat.title,
                    "voice": seat.voice,
                    "chair": name == cfg.chair,
                }
            )
        except FileNotFoundError:
            rows.append(
                {
                    "seat": name,
                    "title": "(missing seat file)",
                    "voice": "",
                    "chair": name == cfg.chair,
                }
            )

    # Plain text table for humans
    lines = [
        f"Council: {cfg.name} — chair: {cfg.chair}",
        (
            f"Budget: max_turns {cfg.max_turns} · "
            f"scratch {cfg.scratch_max_bytes} · "
            f"memory {cfg.manifest_max_bytes}"
        ),
        "",
        f"{'Seat':<22} {'Title':<28} {'Voice':<32} Chair",
        f"{'─'*22} {'─'*28} {'─'*32} ─────",
    ]
    for r in rows:
        mark = "★" if r["chair"] else ""
        lines.append(
            f"{r['seat']:<22} {r['title']:<28} {str(r['voice'])[:32]:<32} {mark}"
        )

    return {
        "ok": True,
        "council": cfg.name,
        "description": cfg.description,
        "chair": cfg.chair,
        "seats": rows,
        "work_budget": cfg.work_budget,
        "memory_budget": cfg.memory_budget,
        "table": "\n".join(lines),
    }
