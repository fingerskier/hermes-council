"""Path helpers for plugin library and project-local .council/ trees."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PLUGIN_ROOT / "data"
TEMPLATES_DIR = DATA_ROOT / "templates"
PERSONALITIES_DIR = DATA_ROOT / "personalities"


def resolve_root(root: Optional[str] = None) -> Path:
    """Absolute project root. Defaults to cwd."""
    base = Path(root).expanduser() if root else Path.cwd()
    return base.resolve()


def council_dir(root: Path) -> Path:
    return root / ".council"


def seats_dir(root: Path) -> Path:
    return council_dir(root) / "seats"


def memory_dir(root: Path) -> Path:
    return council_dir(root) / "memory"


def scratch_dir(root: Path) -> Path:
    return council_dir(root) / "scratch"


def records_dir(root: Path) -> Path:
    return council_dir(root) / "records"


def worktrees_dir(root: Path) -> Path:
    return council_dir(root) / "worktrees"


def sessions_dir(root: Path) -> Path:
    return council_dir(root) / "sessions"


def council_yaml(root: Path) -> Path:
    return council_dir(root) / "council.yaml"


def session_path(root: Path, session_id: str) -> Path:
    return sessions_dir(root) / f"{session_id}.json"


def scratch_path(root: Path, session_id: str) -> Path:
    return scratch_dir(root) / f"{session_id}.md"


def record_path(root: Path, session_id: str) -> Path:
    return records_dir(root) / f"{session_id}.md"


def slugify(text: str, max_len: int = 40) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")[:max_len].strip("-")
    return s or "session"


def new_session_id(task: str, when: Optional[datetime] = None) -> str:
    when = when or datetime.now(timezone.utc).astimezone()
    stamp = when.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{slugify(task)}"
