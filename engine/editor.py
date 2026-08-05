"""Single guarded write path for the council editor."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import simple_yaml as yaml
from .council_io import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_MODELS,
    CouncilConfig,
    load_council,
    load_seat,
    parse_frontmatter,
)
from .paths import council_yaml, seats_dir
from .scratchpad import scrub_text

SEAT_ID_RE = re.compile(r"^[a-z0-9-]+$")
MODEL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class EditorError(ValueError):
    """A user-visible editor validation or save error."""


def _validate_seat_id(name: str) -> str:
    name = str(name or "")
    if not SEAT_ID_RE.fullmatch(name):
        raise EditorError(
            f"invalid seat name {name!r}; expected lowercase letters, digits, and hyphens"
        )
    return name


def _seat_path(root: Path, name: str) -> Path:
    name = _validate_seat_id(name)
    base = seats_dir(root).resolve()
    candidate = base / f"{name}.md"
    if candidate.is_symlink():
        raise EditorError(f"seat path may not be a symlink: {name}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise EditorError(f"seat path escapes .council/seats: {name}") from exc
    return resolved


def _content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _serialize_seat(meta: Dict[str, Any], persona: str) -> str:
    frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).rstrip()
    body = scrub_text(persona)
    return f"---\n{frontmatter}\n---\n{body.rstrip()}\n"


def _stage_bytes(path: Path, content: bytes, suffix: str) -> Path:
    """Write and fsync a sibling temp file without touching its destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode: Optional[int] = None
    if path.exists():
        mode = path.stat().st_mode & 0o777
    fd, raw_tmp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=suffix, dir=path.parent
    )
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        return tmp
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _replace_transaction(changes: List[tuple[Path, str]]) -> None:
    """Stage all files, then roll back the whole editor save if replace fails."""
    new_files: Dict[Path, Path] = {}
    backups: Dict[Path, Optional[Path]] = {}
    try:
        for path, text in changes:
            if path in new_files:
                raise EditorError(f"duplicate editor destination: {path}")
            new_files[path] = _stage_bytes(path, text.encode("utf-8"), ".new")
            backups[path] = (
                _stage_bytes(path, path.read_bytes(), ".backup")
                if path.exists()
                else None
            )
    except Exception:
        for tmp in [*new_files.values(), *(p for p in backups.values() if p)]:
            tmp.unlink(missing_ok=True)
        raise

    replaced: List[Path] = []
    try:
        for path, _ in changes:
            os.replace(new_files[path], path)
            replaced.append(path)
    except Exception as commit_error:
        rollback_errors: List[str] = []
        for path in reversed(replaced):
            backup = backups[path]
            try:
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    os.replace(backup, path)
            except Exception as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        for tmp in [*new_files.values(), *(p for p in backups.values() if p)]:
            tmp.unlink(missing_ok=True)
        if rollback_errors:
            raise RuntimeError(
                "editor save failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            ) from commit_error
        raise
    else:
        for backup in backups.values():
            if backup is not None:
                backup.unlink(missing_ok=True)


def _editor_seat(root: Path, name: str) -> Dict[str, Any]:
    path = _seat_path(root, name)
    seat = load_seat(root, name)
    hash_path = path if path.exists() else seat.path
    return {
        "name": seat.name,
        "title": seat.title,
        "voice": seat.voice,
        "provider": seat.provider,
        "model": seat.model,
        "persona": seat.body,
        "content_hash": _content_hash(hash_path) if hash_path else "",
    }


def load_editor(root: Path) -> Dict[str, Any]:
    """Return the editor projection in configured seat order."""
    root = root.resolve()
    cfg = load_council(root)
    return {
        "ok": True,
        "root": str(root),
        "schema_version": cfg.schema_version,
        "models": list_model_options(root),
        "warnings": list(cfg.warnings),
        "seats": [_editor_seat(root, name) for name in cfg.seats],
    }


def list_model_options(root: Path) -> List[str]:
    """Suggested model ids for seat pickers (council + host + defaults)."""
    root = root.resolve()
    cfg = load_council(root)
    out: List[str] = []

    def _add(value: Any) -> None:
        if not isinstance(value, str):
            return
        model = value.strip()
        if not model or model in out:
            return
        if not MODEL_RE.fullmatch(model):
            return
        # Skip Claude Code tier aliases — not Hermes model ids.
        if model.lower() in {"opus", "sonnet", "haiku", "claude"}:
            return
        out.append(model)

    for value in cfg.models:
        _add(value)
    for value in DEFAULT_MODELS:
        _add(value)

    for name in cfg.seats:
        try:
            seat = load_seat(root, name)
        except FileNotFoundError:
            continue
        _add(seat.model)

    # Host profile suggestions (best-effort).
    try:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
        cfg_path = home / "config.yaml"
        if cfg_path.is_file():
            try:
                import yaml as _yaml  # type: ignore
            except Exception:
                from . import simple_yaml as _yaml  # type: ignore

            host_cfg = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            if not isinstance(host_cfg, dict):
                host_cfg = {}
            model_block = host_cfg.get("model") or {}
            if isinstance(model_block, dict):
                _add(model_block.get("default"))
                aliases = model_block.get("aliases") or {}
                if isinstance(aliases, dict):
                    for k, v in aliases.items():
                        _add(k)
                        if isinstance(v, str):
                            # short form "provider/model" → model tail
                            _add(v)
                            if "/" in v:
                                _add(v.split("/")[-1])
            top_aliases = host_cfg.get("model_aliases") or {}
            if isinstance(top_aliases, dict):
                for k, v in top_aliases.items():
                    _add(k)
                    if isinstance(v, dict):
                        _add(v.get("model"))
                    elif isinstance(v, str):
                        _add(v)
                        if "/" in v:
                            _add(v.split("/")[-1])
    except Exception:
        pass

    return out


def update_seat_model(root: Path, seat_name: str, model: Any) -> Dict[str, Any]:
    """Set one seat's model in frontmatter without rewriting the full editor form."""
    root = root.resolve()
    name = _validate_seat_id(str(seat_name or ""))
    cfg = load_council(root)
    if name not in cfg.seats:
        raise EditorError(f"unknown seat {name!r}")

    path = _seat_path(root, name)
    if not path.exists():
        raise EditorError(f"seat file not found: {name}")

    seat = load_seat(root, name)
    original = path.read_text(encoding="utf-8")
    meta, _body = parse_frontmatter(original)
    meta = dict(meta)
    meta["name"] = name
    meta["title"] = meta.get("title") or seat.title
    meta["voice"] = meta.get("voice") or seat.voice
    if seat.provider and not meta.get("provider"):
        meta["provider"] = seat.provider
    if seat.tools and not meta.get("tools"):
        meta["tools"] = list(seat.tools)
    meta["model"] = _validate_model(model, name)
    text = _serialize_seat(meta, seat.body)
    _replace_transaction([(path, text)])
    seat = load_seat(root, name)
    return {
        "ok": True,
        "name": seat.name,
        "title": seat.title,
        "model": seat.model,
        "provider": seat.provider,
        "message": f"Updated model for {seat.name}",
        "models": list_model_options(root),
    }


def _normalize_models(models: Optional[Iterable[Any]], cfg: CouncilConfig) -> List[str]:
    source = list(cfg.models) if models is None else list(models)
    out: List[str] = []
    for value in source:
        if not isinstance(value, str):
            continue
        model = value.strip()
        if not model or model in out:
            continue
        if not MODEL_RE.fullmatch(model):
            raise EditorError(f"invalid model option {model!r}")
        out.append(model)
    return out or list(cfg.models)


def _validate_model(model: Any, seat_name: str) -> str:
    value = str(model or "").strip()
    # Empty means the Hermes host default; custom values use the strict F3 syntax.
    if value and not MODEL_RE.fullmatch(value):
        raise EditorError(
            f"invalid model for seat {seat_name}: use 1-128 characters from "
            "A-Z, a-z, 0-9, dot, underscore, colon, or hyphen"
        )
    return value


def save_editor(
    root: Path,
    *,
    seats: List[Dict[str, Any]],
    models: Optional[Iterable[Any]] = None,
) -> Dict[str, Any]:
    """Validate and atomically save order, per-seat model, and persona markdown."""
    root = root.resolve()
    cfg = load_council(root)
    if not seats:
        raise EditorError("a council must contain at least one seat")

    names = [_validate_seat_id(str(row.get("name") or "")) for row in seats]
    if len(names) != len(set(names)):
        raise EditorError("seat names must be unique")
    if set(names) != set(cfg.seats):
        raise EditorError("editor may reorder existing seats but may not add or remove them")

    prepared: List[tuple[Path, str]] = []
    for row, name in zip(seats, names):
        path = _seat_path(root, name)
        if not path.exists():
            raise EditorError(f"seat file not found: {name}")
        original = path.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(original)
        meta = dict(meta)
        meta["name"] = name
        meta["model"] = _validate_model(row.get("model"), name)
        persona = scrub_text(str(row.get("persona") or ""))
        if not persona.strip():
            raise EditorError(f"empty persona for seat {name}")
        prepared.append((path, _serialize_seat(meta, persona)))

    raw = dict(cfg.raw)
    raw["schema_version"] = CURRENT_SCHEMA_VERSION
    raw["models"] = _normalize_models(models, cfg)
    raw["seats"] = names
    config_text = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)

    # council.yaml commits last, after all corresponding seat files. If any
    # replacement fails, staged backups restore every destination already moved.
    _replace_transaction([*prepared, (council_yaml(root), config_text)])

    result = load_editor(root)
    result["message"] = "Council configuration saved"
    return result
