"""Read models for the council UI — seat columns from scratch + session."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .council_io import load_council, load_seat
from .info import council_info
from .paths import council_yaml, scratch_path, sessions_dir
from . import scratchpad
from .session import SessionError, load_session, status as session_status

_TURN_RE = re.compile(
    r"^## Turn\s+(\d+)\s+—\s+"
    r"(?:"
    r"USER STEER"
    r"|"
    r"(?P<seat>[^\s(]+)\s+\((?P<title>[^)]*)\)\s+\[(?P<kind>[^\]]+)\]"
    r")"
    r"(?:\s+—\s+(?P<stamp>.+))?"
    r"\s*$",
    re.MULTILINE,
)


def parse_scratch_turns(text: str) -> List[Dict[str, Any]]:
    """Parse scratchpad markdown into ordered turn dicts."""
    if not text or not text.strip():
        return []
    matches = list(_TURN_RE.finditer(text))
    if not matches:
        return []

    turns: List[Dict[str, Any]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        turn_n = int(m.group(1))
        stamp = (m.group("stamp") or "").strip()
        if m.group(0).find("USER STEER") != -1 and m.group("seat") is None:
            turns.append(
                {
                    "turn": turn_n,
                    "kind": "user",
                    "seat": "user",
                    "title": "You",
                    "stamp": stamp,
                    "content": body,
                }
            )
        else:
            content = body
            ok = True
            error = None
            if content.startswith("(") and "ERROR" in content[:80]:
                ok = False
                error = content.strip("() ")
            turns.append(
                {
                    "turn": turn_n,
                    "kind": (m.group("kind") or "seat").strip(),
                    "seat": (m.group("seat") or "").strip(),
                    "title": (m.group("title") or "").strip(),
                    "stamp": stamp,
                    "content": content,
                    "ok": ok,
                    "error": error,
                }
            )
    return turns


def _latest_per_seat(
    turns: List[Dict[str, Any]], seats: List[str]
) -> Dict[str, Optional[Dict[str, Any]]]:
    latest: Dict[str, Optional[Dict[str, Any]]] = {s: None for s in seats}
    for t in turns:
        if t.get("kind") in {"seat", "chair"} or (
            t.get("seat") in latest and t.get("kind") != "user"
        ):
            seat = t.get("seat")
            if seat in latest:
                latest[seat] = t
    return latest


def _history_per_seat(
    turns: List[Dict[str, Any]], seats: List[str], *, limit: int = 12
) -> Dict[str, List[Dict[str, Any]]]:
    hist: Dict[str, List[Dict[str, Any]]] = {s: [] for s in seats}
    for t in turns:
        seat = t.get("seat")
        if seat in hist and t.get("kind") != "user":
            hist[seat].append(t)
    for s in seats:
        hist[s] = hist[s][-limit:]
    return hist


def build_snapshot(
    root: Path,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """UI-facing snapshot: roster + per-seat columns + steers + session."""
    root = root.resolve()
    if not council_yaml(root).exists():
        return {
            "ok": False,
            "error": "not_convened",
            "root": str(root),
            "message": "No council convened at this root. Convene a template first.",
            "seats": [],
            "steers": [],
            "session": None,
        }

    info = council_info(root)
    cfg = load_council(root)
    st_status = session_status(root, session_id)

    # Pick session: explicit, else most recent non-concluded meeting, else latest
    chosen_id = session_id
    session: Optional[Dict[str, Any]] = None
    if chosen_id:
        try:
            session = load_session(root, chosen_id)
        except SessionError as exc:
            return {
                "ok": False,
                "error": "unknown_session",
                "root": str(root),
                "message": str(exc),
                "seats": [],
                "steers": [],
                "session": None,
                "recent_sessions": st_status.get("recent_sessions") or [],
            }
    else:
        recent = st_status.get("recent_sessions") or []
        pick = None
        for row in recent:
            if row.get("mode") == "meeting" and row.get("status") not in {
                "concluded",
                "stopped",
            }:
                pick = row.get("id")
                break
        if not pick and recent:
            pick = recent[0].get("id")
        if pick:
            try:
                session = load_session(root, pick)
                chosen_id = pick
            except SessionError:
                session = None

    seat_names = list(cfg.seats)
    if not seat_names and session:
        seat_names = [str(s) for s in (session.get("seats") or [])]
    if not seat_names and session:
        seat_names = [str(s) for s in (session.get("active_seats") or [])]

    seats_meta: List[Dict[str, Any]] = []
    chair = cfg.chair or (session or {}).get("chair") or ""
    for name in seat_names:
        try:
            seat = load_seat(root, name)
            seats_meta.append(
                {
                    "name": seat.name,
                    "title": seat.title,
                    "voice": seat.voice,
                    "chair": name == chair,
                }
            )
        except FileNotFoundError:
            seats_meta.append(
                {
                    "name": name,
                    "title": name,
                    "voice": "",
                    "chair": name == chair,
                }
            )

    turns: List[Dict[str, Any]] = []
    steers: List[Dict[str, Any]] = []
    scratch_text = ""
    if session and chosen_id:
        sp = scratch_path(root, chosen_id)
        scratch_text = scratchpad.read_scratch(sp)
        if not scratch_text.strip():
            # Concluded sessions archive scratch next to the record
            archived = root / ".council" / "records" / f"{chosen_id}.scratch.md"
            if archived.exists():
                scratch_text = archived.read_text(encoding="utf-8")
        turns = parse_scratch_turns(scratch_text)
        steers = [t for t in turns if t.get("kind") == "user"]

    seat_names = [s["name"] for s in seats_meta]
    latest = _latest_per_seat(turns, seat_names)
    history = _history_per_seat(turns, seat_names)

    columns = []
    for meta in seats_meta:
        name = meta["name"]
        columns.append(
            {
                **meta,
                "latest": latest.get(name),
                "history": history.get(name) or [],
            }
        )

    # Merge contribution ok/error from session state when available
    if session:
        by_turn = {
            int(c["turn"]): c
            for c in (session.get("contributions") or [])
            if isinstance(c, dict) and c.get("turn") is not None
        }
        for col in columns:
            lat = col.get("latest")
            if not lat:
                continue
            meta_c = by_turn.get(int(lat["turn"]))
            if meta_c:
                if "ok" in meta_c:
                    lat["ok"] = meta_c.get("ok")
                if meta_c.get("error"):
                    lat["error"] = meta_c.get("error")
                if meta_c.get("via"):
                    lat["via"] = meta_c.get("via")
                if meta_c.get("chars") is not None:
                    lat["chars"] = meta_c.get("chars")

    return {
        "ok": True,
        "root": str(root),
        "convened": True,
        "council": info.get("council"),
        "chair": chair,
        "description": info.get("description") or "",
        "table": info.get("table") or "",
        "session": session,
        "session_id": chosen_id,
        "recent_sessions": st_status.get("recent_sessions") or [],
        "interrupted_scratchpads": st_status.get("interrupted_scratchpads") or [],
        "seats": columns,
        "steers": steers[-8:],
        "turns": turns[-40:],
        "scratch_chars": len(scratch_text),
    }
