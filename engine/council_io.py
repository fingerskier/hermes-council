"""Read/write council.yaml and seat personality files."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import simple_yaml as yaml
from .paths import (
    PERSONALITIES_DIR,
    TEMPLATES_DIR,
    council_yaml,
    seats_dir,
)


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
CURRENT_SCHEMA_VERSION = 1
DEFAULT_MODELS = (
    "claude-opus-4-1",
    "claude-sonnet-4",
    "claude-haiku-3-5",
    "gpt-5",
    "gemini-2.5-pro",
)


@dataclass
class Seat:
    name: str
    title: str = ""
    voice: str = ""
    provider: str = ""
    model: str = ""
    tools: List[str] = field(default_factory=list)
    body: str = ""
    path: Optional[Path] = None

    @property
    def system_prompt(self) -> str:
        header = f"You are {self.title or self.name} on this council."
        if self.voice:
            header += f" Voice: {self.voice}."
        return f"{header}\n\n{self.body.strip()}".strip()


@dataclass
class CouncilConfig:
    name: str
    schema_version: int = CURRENT_SCHEMA_VERSION
    description: str = ""
    chair: str = ""
    seats: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    warnings: List[str] = field(default_factory=list)
    work_budget: Dict[str, Any] = field(default_factory=dict)
    memory_budget: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def max_turns(self) -> int:
        return int(self.work_budget.get("max_turns") or 12)

    @property
    def scratch_max_bytes(self) -> int:
        return int(self.work_budget.get("scratch_max_bytes") or 200_000)

    @property
    def max_wall_seconds(self) -> Optional[int]:
        val = self.work_budget.get("max_wall_seconds")
        if val is None:
            return None
        try:
            n = int(val)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    @property
    def manifest_max_bytes(self) -> int:
        return int(self.memory_budget.get("manifest_max_bytes") or 8000)


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, m.group(2)


def load_seat_file(path: Path) -> Seat:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    name = str(meta.get("name") or path.stem)
    tools = meta.get("tools") or []
    if isinstance(tools, str):
        tools = [tools]
    return Seat(
        name=name,
        title=str(meta.get("title") or name),
        voice=str(meta.get("voice") or ""),
        provider=str(meta.get("provider") or ""),
        model=str(meta.get("model") or ""),
        tools=[str(t) for t in tools],
        body=body.strip(),
        path=path,
    )


def load_template(name: str) -> Dict[str, Any]:
    path = TEMPLATES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown template: {name}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid template: {name}")
    return data


def load_council(root: Path) -> CouncilConfig:
    path = council_yaml(root)
    if not path.exists():
        raise FileNotFoundError(
            f"No council convened at {path}. Run council convene first."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid council.yaml at {path}")
    raw_version = data.get("schema_version", CURRENT_SCHEMA_VERSION)
    try:
        schema_version = int(raw_version)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid schema_version in {path}: {raw_version!r}") from exc
    if schema_version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported council schema_version {schema_version}; "
            f"this plugin supports up to {CURRENT_SCHEMA_VERSION}"
        )

    seats = data.get("seats") or []
    if isinstance(seats, str):
        seats = [seats]
    warnings: List[str] = []
    raw_models = data.get("models")
    models: List[str]
    if raw_models is None or raw_models == []:
        models = list(DEFAULT_MODELS)
        if raw_models == []:
            warnings.append("models is empty; using built-in suggestions")
    elif not isinstance(raw_models, list):
        models = list(DEFAULT_MODELS)
        warnings.append("models must be a list; using built-in suggestions")
    else:
        models = []
        for value in raw_models:
            if not isinstance(value, str) or not value.strip():
                warnings.append("ignored a blank or non-string models entry")
                continue
            model = value.strip()
            if model not in models:
                models.append(model)
        if not models:
            models = list(DEFAULT_MODELS)
            warnings.append("models has no usable entries; using built-in suggestions")
    return CouncilConfig(
        name=str(data.get("name") or "council"),
        schema_version=schema_version,
        description=str(data.get("description") or ""),
        chair=str(data.get("chair") or ""),
        seats=[str(s) for s in seats],
        models=models,
        warnings=warnings,
        work_budget=dict(data.get("work_budget") or {}),
        memory_budget=dict(data.get("memory_budget") or {}),
        raw=data,
    )


def load_seat(root: Path, name: str) -> Seat:
    path = seats_dir(root) / f"{name}.md"
    if not path.exists():
        # fall back to library
        lib = PERSONALITIES_DIR / f"{name}.md"
        if not lib.exists():
            raise FileNotFoundError(f"Seat not found: {name}")
        return load_seat_file(lib)
    return load_seat_file(path)


def snapshot_seat(root: Path, name: str) -> Dict[str, Any]:
    """Capture the complete functional seat content for a reproducible session."""
    source = seats_dir(root) / f"{name}.md"
    if not source.exists():
        raise FileNotFoundError(f"Missing council seat file: {source}")
    seat = load_seat_file(source)
    content_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "name": seat.name,
        "title": seat.title,
        "voice": seat.voice,
        "provider": seat.provider,
        "model": seat.model,
        "tools": list(seat.tools),
        "body": seat.body,
        "content_hash": content_hash,
    }


def seat_from_snapshot(data: Dict[str, Any]) -> Seat:
    """Rehydrate a session-pinned seat without touching live config files."""
    return Seat(
        name=str(data.get("name") or ""),
        title=str(data.get("title") or data.get("name") or ""),
        voice=str(data.get("voice") or ""),
        provider=str(data.get("provider") or ""),
        model=str(data.get("model") or ""),
        tools=[str(value) for value in (data.get("tools") or [])],
        body=str(data.get("body") or ""),
        path=None,
    )


def list_library_templates() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not TEMPLATES_DIR.exists():
        return out
    for path in sorted(TEMPLATES_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        out.append(
            {
                "name": str(data.get("name") or path.stem),
                "description": str(data.get("description") or ""),
                "chair": str(data.get("chair") or ""),
                "seats": ", ".join(str(s) for s in (data.get("seats") or [])),
            }
        )
    return out


def list_library_personalities() -> List[str]:
    if not PERSONALITIES_DIR.exists():
        return []
    return sorted(p.stem for p in PERSONALITIES_DIR.glob("*.md"))
