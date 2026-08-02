"""Minimal YAML subset loader/dumper for council templates and frontmatter.

Prefers PyYAML when available; otherwise handles the small dialect we ship:
mappings, nested mappings, inline lists, scalars, comments.
"""

from __future__ import annotations

from typing import Any, List


def _try_pyyaml():
    try:
        import yaml  # type: ignore

        return yaml
    except Exception:
        return None


def safe_load(text: str) -> Any:
    y = _try_pyyaml()
    if y is not None:
        return y.safe_load(text)
    return _mini_load(text)


def safe_dump(data: Any, *, sort_keys: bool = False, allow_unicode: bool = True) -> str:
    del allow_unicode
    y = _try_pyyaml()
    if y is not None:
        return y.safe_dump(data, sort_keys=sort_keys, allow_unicode=True)
    return _mini_dump(data, sort_keys=sort_keys)


def _mini_load(text: str) -> Any:
    lines = text.splitlines()
    root: dict = {}
    stack: List[tuple[int, dict]] = [(-1, root)]
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        # strip inline comments carefully
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if content.startswith("- "):
            # list item under previous key — not used in our templates at root
            continue

        if ":" not in content:
            continue
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            # nested mapping
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(rest)
    return root


def _parse_scalar(val: str) -> Any:
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        parts = []
        buf = []
        depth = 0
        for ch in inner:
            if ch == "[":
                depth += 1
                buf.append(ch)
            elif ch == "]":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf).strip())
        return [_parse_scalar(p) if p else "" for p in parts]

    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    low = val.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    if low in {"null", "~", ""}:
        return None
    try:
        if val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
            return int(val)
        return float(val)
    except ValueError:
        return val


def _mini_dump(data: Any, *, sort_keys: bool = False, indent: int = 0) -> str:
    if not isinstance(data, dict):
        return str(data) + "\n"
    keys = sorted(data.keys()) if sort_keys else list(data.keys())
    lines: List[str] = []
    pad = "  " * indent
    for k in keys:
        v = data[k]
        if isinstance(v, dict):
            lines.append(f"{pad}{k}:")
            nested = _mini_dump(v, sort_keys=sort_keys, indent=indent + 1).rstrip("\n")
            if nested:
                lines.append(nested)
        elif isinstance(v, list):
            items = ", ".join(_format_scalar(x) for x in v)
            lines.append(f"{pad}{k}: [{items}]")
        else:
            lines.append(f"{pad}{k}: {_format_scalar(v)}")
    return "\n".join(lines) + "\n"


def _format_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(c in s for c in ":#[]{},\n"):
        return json_escape(s)
    return s


def json_escape(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
