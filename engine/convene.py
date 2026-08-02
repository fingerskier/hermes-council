"""Convene a council from a template into project-local .council/."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import simple_yaml as yaml
from .council_io import list_library_templates, load_template
from .paths import (
    PERSONALITIES_DIR,
    council_dir,
    council_yaml,
    memory_dir,
    records_dir,
    scratch_dir,
    seats_dir,
    sessions_dir,
    worktrees_dir,
)


def list_templates() -> List[Dict[str, str]]:
    return list_library_templates()


def convene(
    root: Path,
    template: str = "software-team",
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Stamp a template into ``root/.council/``.

    Recreate overwrites ``council.yaml`` + ``seats/`` only when ``force=True``.
    ``memory/``, ``records/``, and ``scratch/`` are never wiped.
    """
    root = root.resolve()
    tpl = load_template(template)
    seats = [str(s) for s in (tpl.get("seats") or [])]
    if not seats:
        raise ValueError(f"Template {template!r} has no seats")

    cdir = council_dir(root)
    yaml_path = council_yaml(root)
    if yaml_path.exists() and not force:
        return {
            "ok": False,
            "error": "council_exists",
            "message": (
                f"Council already exists at {yaml_path}. "
                "Pass force=true to recreate roster/seats "
                "(memory and records are preserved)."
            ),
            "path": str(yaml_path),
        }

    # Ensure tree (non-destructive)
    for d in (
        seats_dir(root),
        memory_dir(root),
        scratch_dir(root),
        records_dir(root),
        worktrees_dir(root),
        sessions_dir(root),
    ):
        d.mkdir(parents=True, exist_ok=True)

    # Write council.yaml from template
    yaml_path.write_text(
        yaml.safe_dump(tpl, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    # Copy seats (overwrite on force/recreate)
    missing: List[str] = []
    copied: List[str] = []
    for seat in seats:
        src = PERSONALITIES_DIR / f"{seat}.md"
        dst = seats_dir(root) / f"{seat}.md"
        if not src.exists():
            missing.append(seat)
            continue
        shutil.copyfile(src, dst)
        copied.append(seat)

    gitignore = cdir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("scratch/\nworktrees/\nsessions/\n", encoding="utf-8")

    return {
        "ok": True,
        "council": str(tpl.get("name") or template),
        "description": str(tpl.get("description") or ""),
        "chair": str(tpl.get("chair") or ""),
        "seats": copied,
        "missing_personalities": missing,
        "path": str(cdir),
        "message": (
            f"Convened {tpl.get('name') or template} at {cdir}. "
            "Edit .council/seats/*.md and .council/council.yaml freely."
        ),
    }
