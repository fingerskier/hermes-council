"""Git worktree helpers for autonomous work sessions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class WorktreeError(RuntimeError):
    pass


def _run(args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def is_git_repo(root: Path) -> bool:
    r = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root)
    return r.returncode == 0 and r.stdout.strip() == "true"


def create_worktree(root: Path, session_id: str) -> Dict[str, Any]:
    """Create ``.council/worktrees/<id>`` on branch ``council/work-<id>``."""
    if not is_git_repo(root):
        raise WorktreeError(
            "work requires a git repository (run git init). "
            "meeting/info/convene work without git."
        )

    branch = f"council/work-{session_id}"
    path = root / ".council" / "worktrees" / session_id
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise WorktreeError(f"Worktree path already exists: {path}")

    r = _run(
        ["git", "worktree", "add", "-b", branch, str(path), "HEAD"],
        cwd=root,
    )
    if r.returncode != 0:
        raise WorktreeError(
            f"git worktree add failed: {r.stderr.strip() or r.stdout.strip()}"
        )

    return {
        "path": str(path.resolve()),
        "branch": branch,
        "session_id": session_id,
    }


def worktree_status(worktree_path: Path) -> Dict[str, Any]:
    r = _run(["git", "status", "--porcelain"], cwd=worktree_path)
    if r.returncode != 0:
        return {
            "ok": False,
            "error": r.stderr.strip() or "git status failed",
            "path": str(worktree_path),
        }
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    return {
        "ok": True,
        "path": str(worktree_path),
        "dirty": bool(lines),
        "changes": lines[:50],
        "change_count": len(lines),
    }


def commit_worktree(worktree_path: Path, message: str) -> Dict[str, Any]:
    _run(["git", "add", "-A"], cwd=worktree_path)
    r = _run(["git", "commit", "-m", message], cwd=worktree_path)
    # exit 1 with "nothing to commit" is fine
    nothing = "nothing to commit" in (r.stdout + r.stderr).lower()
    return {
        "ok": r.returncode == 0 or nothing,
        "nothing_to_commit": nothing,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
    }


def merge_commands(root: Path, branch: str, worktree_path: Path) -> List[str]:
    return [
        f"git -C {root} merge --no-ff {branch}",
        f"git -C {root} worktree remove {worktree_path}",
    ]


def verify_main_tree_clean_of_session(root: Path) -> Dict[str, Any]:
    """Best-effort note: does not prove isolation, just reports main status."""
    if not is_git_repo(root):
        return {"ok": True, "git": False}
    r = _run(["git", "status", "--porcelain"], cwd=root)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    # Ignore .council noise
    interesting = [
        ln
        for ln in lines
        if ".council/" not in ln and not ln.endswith(" .council")
    ]
    return {
        "ok": True,
        "git": True,
        "main_dirty_outside_council": bool(interesting),
        "sample": interesting[:20],
    }
