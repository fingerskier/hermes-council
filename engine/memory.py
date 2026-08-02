"""Two-tier council memory: manifest pointers + per-topic files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .paths import memory_dir


def list_topics(root: Path) -> List[str]:
    d = memory_dir(root)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


def build_manifest(root: Path, max_bytes: int = 8000) -> str:
    """One-line-per-topic manifest injected at seat spawn."""
    d = memory_dir(root)
    if not d.exists():
        return "(no council memory yet)"

    lines: List[str] = ["# Council memory manifest", ""]
    for path in sorted(d.glob("*.md")):
        first = _first_decision_line(path)
        lines.append(f"- `{path.name}`: {first}")
    text = "\n".join(lines) + "\n"
    if max_bytes and len(text.encode("utf-8")) > max_bytes:
        # Truncate whole topics from the end
        encoded = text.encode("utf-8")[: max(0, max_bytes - 32)]
        text = encoded.decode("utf-8", errors="ignore").rstrip() + "\n…(truncated)\n"
    return text


def _first_decision_line(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "(unreadable)"
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("→"):
            continue
        return s[:160]
    return "(empty)"


def update_topic(
    root: Path,
    topic: str,
    *,
    decision: str,
    why: str,
    record_id: str,
    dissents: str = "",
) -> Path:
    """Create or append a memory topic file. Returns path."""
    d = memory_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9-]+", "-", topic.lower()).strip("-") or "topic"
    path = d / f"{slug}.md"

    block = (
        f"## Decision\n"
        f"{decision.strip()}\n"
        f"→ record: `records/{record_id}.md`\n"
        f"\n"
        f"## Why\n"
        f"{why.strip()}\n"
    )
    if dissents.strip():
        block += f"\n## Standing dissent\n{dissents.strip()}\n"

    if path.exists():
        existing = path.read_text(encoding="utf-8").rstrip() + "\n\n"
        path.write_text(existing + f"---\n\n{block}", encoding="utf-8")
    else:
        title = topic.replace("-", " ").strip().title()
        path.write_text(
            f"# Memory: {title}\n\n{block}",
            encoding="utf-8",
        )
    return path


def read_topic(root: Path, topic: str) -> Optional[str]:
    path = memory_dir(root) / f"{topic}.md"
    if not path.exists():
        # try loose match
        matches = list(memory_dir(root).glob(f"*{topic}*.md"))
        if not matches:
            return None
        path = matches[0]
    return path.read_text(encoding="utf-8")
