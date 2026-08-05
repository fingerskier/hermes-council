"""Convene a council from a template into project-local .council/."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import simple_yaml as yaml
from .council_io import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_MODELS,
    list_library_templates,
    load_template,
)
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
    tpl = dict(tpl)
    tpl["schema_version"] = CURRENT_SCHEMA_VERSION
    tpl.setdefault("models", list(DEFAULT_MODELS))
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

    # Copy seats (overwrite on force/recreate); strip legacy model aliases
    missing: List[str] = []
    copied: List[str] = []
    normalized_models: List[str] = []
    for seat in seats:
        src = PERSONALITIES_DIR / f"{seat}.md"
        dst = seats_dir(root) / f"{seat}.md"
        if not src.exists():
            missing.append(seat)
            continue
        text = src.read_text(encoding="utf-8")
        cleaned, changed = _strip_legacy_model_alias(text)
        dst.write_text(cleaned, encoding="utf-8")
        copied.append(seat)
        if changed:
            normalized_models.append(seat)

    gitignore = cdir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("scratch/\nworktrees/\nsessions/\n", encoding="utf-8")

    out = {
        "ok": True,
        "council": str(tpl.get("name") or template),
        "description": str(tpl.get("description") or ""),
        "chair": str(tpl.get("chair") or ""),
        "seats": copied,
        "missing_personalities": missing,
        "normalized_legacy_models": normalized_models,
        "path": str(cdir),
        "message": (
            f"Convened {tpl.get('name') or template} at {cdir}. "
            "Edit .council/seats/*.md and .council/council.yaml freely."
        ),
    }
    if normalized_models:
        out["message"] += (
            " Stripped Claude-tier model aliases (opus/sonnet/haiku) from: "
            + ", ".join(normalized_models)
            + " (host default model will be used unless you set a real model id)."
        )
    return out


_LEGACY_MODEL_LINE = re.compile(
    r"(?im)^model:\s*[\"']?(opus|sonnet|haiku)[\"']?\s*$"
)


def _strip_legacy_model_alias(text: str) -> tuple[str, bool]:
    """Blank Claude Code tier aliases in seat frontmatter only."""
    if not text.startswith("---"):
        return text, False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text, False
    # parts[0] empty, parts[1] fm, parts[2] body (may lack leading newline handling)
    fm = parts[1]
    new_fm, n = _LEGACY_MODEL_LINE.subn('model: ""', fm)
    if n == 0:
        return text, False
    # Reassemble with standard fences
    body = parts[2]
    if not body.startswith("\n"):
        body = "\n" + body
    return f"---{new_fm}---{body}", True
