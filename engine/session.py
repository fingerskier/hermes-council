"""Session state machine for meeting and work verbs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .council_io import load_council, load_seat
from .memory import update_topic
from .paths import (
    council_yaml,
    new_session_id,
    scratch_path,
    session_path,
    sessions_dir,
)
from . import scratchpad
from . import records as records_mod
from . import worktree as wt
from .spawn import route_next, speak_as_seat, synthesize


class SessionError(RuntimeError):
    pass


def _save(root: Path, state: Dict[str, Any]) -> None:
    sessions_dir(root).mkdir(parents=True, exist_ok=True)
    path = session_path(root, state["id"])
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def load_session(root: Path, session_id: str) -> Dict[str, Any]:
    path = session_path(root, session_id)
    if not path.exists():
        raise SessionError(f"Unknown session: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def status(root: Path, session_id: Optional[str] = None) -> Dict[str, Any]:
    root = root.resolve()
    if not council_yaml(root).exists():
        return {
            "ok": False,
            "error": "not_convened",
            "message": "No council convened.",
        }

    interrupted = []
    scratch_dir = root / ".council" / "scratch"
    records = root / ".council" / "records"
    if scratch_dir.exists():
        for sp in scratch_dir.glob("*.md"):
            sid = sp.stem
            if not (records / f"{sid}.md").exists():
                interrupted.append(sid)

    sessions = []
    sdir = sessions_dir(root)
    if sdir.exists():
        for p in sorted(sdir.glob("*.json"), reverse=True)[:20]:
            try:
                st = json.loads(p.read_text(encoding="utf-8"))
                sessions.append(
                    {
                        "id": st.get("id"),
                        "mode": st.get("mode"),
                        "status": st.get("status"),
                        "task": st.get("task"),
                        "seat_turns": st.get("seat_turns"),
                    }
                )
            except Exception:
                continue

    out: Dict[str, Any] = {
        "ok": True,
        "root": str(root),
        "interrupted_scratchpads": interrupted,
        "recent_sessions": sessions,
    }
    if session_id:
        try:
            out["session"] = load_session(root, session_id)
        except SessionError as exc:
            out["session_error"] = str(exc)
    return out


def _base_state(
    root: Path,
    *,
    mode: str,
    task: str,
    cfg,
) -> Dict[str, Any]:
    started = int(time.time())
    sid = new_session_id(task)
    return {
        "id": sid,
        "mode": mode,
        "task": task,
        "root": str(root.resolve()),
        "chair": cfg.chair,
        "seats": list(cfg.seats),
        "active_seats": list(cfg.seats),
        "turn": 0,
        "seat_turns": 0,
        "status": "active",
        "started_epoch": started,
        "max_turns": cfg.max_turns,
        "scratch_max_bytes": cfg.scratch_max_bytes,
        "max_wall_seconds": cfg.max_wall_seconds,
        "memory_budget": cfg.manifest_max_bytes,
        "worktree": None,
        "last_route": None,
        "done": False,
        "stop_reason": None,
        "contributions": [],
    }


def meeting_start(root: Path, task: str, ctx: Any = None) -> Dict[str, Any]:
    del ctx  # reserved
    root = root.resolve()
    cfg = load_council(root)
    state = _base_state(root, mode="meeting", task=task, cfg=cfg)
    sp = scratch_path(root, state["id"])
    scratchpad.init_scratch(
        sp,
        session_id=state["id"],
        mode="meeting",
        task=task,
        chair=cfg.chair,
        seats=cfg.seats,
        started_epoch=state["started_epoch"],
    )
    state["status"] = "awaiting_round"
    _save(root, state)
    return {
        "ok": True,
        "session_id": state["id"],
        "mode": "meeting",
        "task": task,
        "seats": cfg.seats,
        "chair": cfg.chair,
        "scratch": str(sp),
        "message": (
            f"Meeting {state['id']} opened. Call meeting_round to let every "
            "seat speak, then steer or conclude."
        ),
        "next": "meeting_round",
    }


def meeting_round(
    root: Path,
    session_id: str,
    ctx: Any = None,
    *,
    user_steer: str = "",
) -> Dict[str, Any]:
    root = root.resolve()
    state = load_session(root, session_id)
    if state["mode"] != "meeting":
        raise SessionError("Session is not a meeting")
    if state["status"] in {"concluded", "stopped"}:
        raise SessionError(f"Session already {state['status']}")

    sp = scratch_path(root, session_id)
    if user_steer.strip():
        state["turn"] += 1
        scratchpad.append_user_steer(sp, turn=state["turn"], content=user_steer)

    # Budget checks
    if scratchpad.scratch_size(sp) > int(state["scratch_max_bytes"]):
        state["status"] = "stopped"
        state["stop_reason"] = "scratch_max_bytes"
        _save(root, state)
        return {
            "ok": False,
            "error": "scratch_max_bytes",
            "session_id": session_id,
            "message": "Scratchpad exceeded size budget; conclude or stop.",
        }

    wall = state.get("max_wall_seconds")
    if wall and (time.time() - state["started_epoch"]) > wall:
        state["status"] = "stopped"
        state["stop_reason"] = "max_wall_seconds"
        _save(root, state)
        return {
            "ok": False,
            "error": "max_wall_seconds",
            "session_id": session_id,
            "message": "Wall-clock budget reached.",
        }

    contributions = []
    for seat_name in state["seats"]:
        state["turn"] += 1
        state["seat_turns"] += 1
        seat = load_seat(root, seat_name)
        scratch_text = scratchpad.read_scratch(sp)
        result = speak_as_seat(
            ctx,
            seat=seat,
            task=state["task"],
            scratch=scratch_text,
            root=str(root),
            mode="meeting",
            session_id=session_id,
            turn=state["turn"],
            memory_budget=int(state.get("memory_budget") or 8000),
        )
        text = result.get("text") or ""
        scratchpad.append_turn(
            sp,
            seat=seat.name,
            title=seat.title,
            turn=state["turn"],
            content=text,
            kind="seat",
        )
        entry = {
            "seat": seat.name,
            "turn": state["turn"],
            "via": result.get("via"),
            "ok": result.get("ok"),
            "chars": len(text),
        }
        contributions.append(entry)
        state["contributions"].append(entry)

    state["status"] = "awaiting_user"
    _save(root, state)

    return {
        "ok": True,
        "session_id": session_id,
        "round_contributions": contributions,
        "seat_turns": state["seat_turns"],
        "status": state["status"],
        "scratch": str(sp),
        "message": (
            "Round complete. Provide a steer via meeting_round(user_steer=...) "
            "for another round, or meeting_conclude."
        ),
        "next_options": ["meeting_round", "meeting_conclude"],
    }


def conclude_meeting(
    root: Path,
    session_id: str,
    ctx: Any = None,
) -> Dict[str, Any]:
    root = root.resolve()
    state = load_session(root, session_id)
    if state["mode"] != "meeting":
        raise SessionError("Session is not a meeting")

    sp = scratch_path(root, session_id)
    scratch_text = scratchpad.read_scratch(sp)
    chair = load_seat(root, state["chair"])
    synth = synthesize(
        ctx,
        chair=chair,
        task=state["task"],
        scratch=scratch_text,
        mode="meeting",
    )

    memory_topics: List[str] = []
    topic = (synth.get("memory_topic") or "").strip()
    if topic and synth.get("memory_decision"):
        path = update_topic(
            root,
            topic,
            decision=str(synth.get("memory_decision") or synth["recommendation"]),
            why=str(synth.get("memory_why") or synth.get("reasoning") or ""),
            record_id=session_id,
            dissents=str(synth.get("dissents") or ""),
        )
        memory_topics.append(path.stem)

    rec = records_mod.write_record(
        root,
        session_id=session_id,
        mode="meeting",
        chair=state["chair"],
        seats=state["seats"],
        task=state["task"],
        recommendation=synth["recommendation"],
        reasoning=synth["reasoning"],
        dissents=synth["dissents"],
        follow_ups=synth.get("follow_ups") or "",
        memory_topics=memory_topics,
        archive_scratch=True,
    )

    state["status"] = "concluded"
    state["done"] = True
    state["stop_reason"] = "user_concluded"
    state["record"] = rec.get("record")
    _save(root, state)

    problems = []
    try:
        text = Path(rec["record"]).read_text(encoding="utf-8")
        problems = records_mod.validate_record_text(text)
    except Exception:
        pass

    return {
        "ok": True,
        "session_id": session_id,
        "record": rec.get("record"),
        "scratch_archive": rec.get("scratch_archive"),
        "memory_topics": memory_topics,
        "synthesis_via": synth.get("via"),
        "format_problems": problems,
        "recommendation": synth["recommendation"],
        "dissents": synth["dissents"],
        "message": f"Meeting concluded. Record: {rec.get('record')}",
    }


def work_start(root: Path, task: str, ctx: Any = None) -> Dict[str, Any]:
    del ctx
    root = root.resolve()
    cfg = load_council(root)
    state = _base_state(root, mode="work", task=task, cfg=cfg)

    try:
        winfo = wt.create_worktree(root, state["id"])
    except wt.WorktreeError as exc:
        return {"ok": False, "error": "worktree", "message": str(exc)}

    state["worktree"] = winfo
    sp = scratch_path(root, state["id"])
    scratchpad.init_scratch(
        sp,
        session_id=state["id"],
        mode="work",
        task=task,
        chair=cfg.chair,
        seats=cfg.seats,
        started_epoch=state["started_epoch"],
    )
    # Note worktree in scratch
    scratchpad.append_turn(
        sp,
        seat="system",
        title="System",
        turn=0,
        content=(
            f"Worktree ready at `{winfo['path']}` on branch `{winfo['branch']}`. "
            "Chair never auto-merges."
        ),
        kind="system",
    )
    state["status"] = "active"
    _save(root, state)
    return {
        "ok": True,
        "session_id": state["id"],
        "mode": "work",
        "task": task,
        "worktree": winfo,
        "max_turns": state["max_turns"],
        "message": (
            f"Work session {state['id']} started in worktree. "
            "Call work_tick repeatedly until done, or work_stop."
        ),
        "next": "work_tick",
    }


def _stop_checks(state: Dict[str, Any], sp: Path) -> Optional[str]:
    if state["seat_turns"] >= int(state["max_turns"]):
        return "max_turns"
    if scratchpad.scratch_size(sp) > int(state["scratch_max_bytes"]):
        return "scratch_max_bytes"
    wall = state.get("max_wall_seconds")
    if wall and (time.time() - state["started_epoch"]) > float(wall):
        return "max_wall_seconds"
    return None


def work_tick(root: Path, session_id: str, ctx: Any = None) -> Dict[str, Any]:
    root = root.resolve()
    state = load_session(root, session_id)
    if state["mode"] != "work":
        raise SessionError("Session is not a work session")
    if state["status"] in {"concluded", "stopped"}:
        return {
            "ok": False,
            "error": "already_finished",
            "status": state["status"],
            "stop_reason": state.get("stop_reason"),
            "session_id": session_id,
        }

    sp = scratch_path(root, session_id)
    reason = _stop_checks(state, sp)
    if reason:
        return _finish_work(root, state, ctx, stop_reason=reason)

    chair = load_seat(root, state["chair"])
    scratch_text = scratchpad.read_scratch(sp)

    # Inline chair routing (not a counted seat turn)
    route = route_next(
        ctx,
        chair=chair,
        task=state["task"],
        scratch=scratch_text,
        seats=state["active_seats"] or state["seats"],
        seat_turns=state["seat_turns"],
        max_turns=int(state["max_turns"]),
    )
    state["last_route"] = route
    state["turn"] += 1
    scratchpad.append_turn(
        sp,
        seat=state["chair"],
        title="Chair routing",
        turn=state["turn"],
        content=(
            f"done={route.get('done')} next={route.get('next_seat')} "
            f"reason={route.get('reason')}\n"
            f"instruction: {route.get('instruction')}"
        ),
        kind="routing",
    )

    if route.get("done"):
        return _finish_work(
            root, state, ctx, stop_reason="chair_done", route_reason=route.get("reason")
        )

    next_seat = route.get("next_seat") or (state["seats"][0] if state["seats"] else "")
    if not next_seat:
        return _finish_work(root, state, ctx, stop_reason="no_seat")

    seat = load_seat(root, next_seat)
    state["turn"] += 1
    state["seat_turns"] += 1
    wpath = (state.get("worktree") or {}).get("path")
    result = speak_as_seat(
        ctx,
        seat=seat,
        task=state["task"],
        scratch=scratchpad.read_scratch(sp),
        root=str(root),
        mode="work",
        session_id=session_id,
        turn=state["turn"],
        instruction=str(route.get("instruction") or ""),
        worktree_path=wpath,
        memory_budget=int(state.get("memory_budget") or 8000),
    )
    text = result.get("text") or ""
    scratchpad.append_turn(
        sp,
        seat=seat.name,
        title=seat.title,
        turn=state["turn"],
        content=text,
        kind="seat",
    )
    entry = {
        "seat": seat.name,
        "turn": state["turn"],
        "via": result.get("via"),
        "ok": result.get("ok"),
        "chars": len(text),
    }
    state["contributions"].append(entry)

    wt_status = None
    if wpath:
        wt_status = wt.worktree_status(Path(wpath))

    # Re-check budgets after the seat
    reason = _stop_checks(state, sp)
    _save(root, state)
    if reason:
        return _finish_work(root, state, ctx, stop_reason=reason)

    return {
        "ok": True,
        "session_id": session_id,
        "status": "active",
        "seat_turns": state["seat_turns"],
        "max_turns": state["max_turns"],
        "routed_to": next_seat,
        "route_reason": route.get("reason"),
        "contribution": entry,
        "worktree_status": wt_status,
        "message": (
            f"Turn complete ({state['seat_turns']}/{state['max_turns']}). "
            "Call work_tick again, or work_stop."
        ),
        "next": "work_tick",
    }


def work_stop(
    root: Path,
    session_id: str,
    ctx: Any = None,
    *,
    reason: str = "user_stop",
) -> Dict[str, Any]:
    root = root.resolve()
    state = load_session(root, session_id)
    if state["mode"] != "work":
        raise SessionError("Session is not a work session")
    if state["status"] in {"concluded", "stopped"}:
        return {
            "ok": True,
            "already_finished": True,
            "session_id": session_id,
            "status": state["status"],
            "record": state.get("record"),
        }
    return _finish_work(root, state, ctx, stop_reason=reason)


def _finish_work(
    root: Path,
    state: Dict[str, Any],
    ctx: Any,
    *,
    stop_reason: str,
    route_reason: str = "",
) -> Dict[str, Any]:
    session_id = state["id"]
    sp = scratch_path(root, session_id)
    scratch_text = scratchpad.read_scratch(sp)
    chair = load_seat(root, state["chair"])

    wpath = (state.get("worktree") or {}).get("path")
    branch = (state.get("worktree") or {}).get("branch")
    commit_info = None
    if wpath:
        commit_info = wt.commit_worktree(
            Path(wpath),
            f"council work {session_id}: {state['task'][:60]}",
        )

    synth = synthesize(
        ctx,
        chair=chair,
        task=state["task"],
        scratch=scratch_text,
        mode="work",
    )
    if route_reason and stop_reason == "chair_done":
        synth["reasoning"] = (
            f"Chair stopped: {route_reason}\n\n{synth.get('reasoning') or ''}"
        )

    memory_topics: List[str] = []
    topic = (synth.get("memory_topic") or "").strip()
    if topic and synth.get("memory_decision"):
        path = update_topic(
            root,
            topic,
            decision=str(synth.get("memory_decision") or synth["recommendation"]),
            why=str(synth.get("memory_why") or synth.get("reasoning") or ""),
            record_id=session_id,
            dissents=str(synth.get("dissents") or ""),
        )
        memory_topics.append(path.stem)

    rec = records_mod.write_record(
        root,
        session_id=session_id,
        mode="work",
        chair=state["chair"],
        seats=state["seats"],
        task=state["task"],
        recommendation=synth["recommendation"],
        reasoning=synth["reasoning"],
        dissents=synth["dissents"],
        follow_ups=synth.get("follow_ups") or "",
        memory_topics=memory_topics,
        archive_scratch=True,
    )

    state["status"] = "concluded" if stop_reason == "chair_done" else "stopped"
    state["done"] = True
    state["stop_reason"] = stop_reason
    state["record"] = rec.get("record")
    _save(root, state)

    merge_cmds = []
    if branch and wpath:
        merge_cmds = wt.merge_commands(root, branch, Path(wpath))

    return {
        "ok": True,
        "session_id": session_id,
        "status": state["status"],
        "stop_reason": stop_reason,
        "record": rec.get("record"),
        "scratch_archive": rec.get("scratch_archive"),
        "memory_topics": memory_topics,
        "worktree": state.get("worktree"),
        "commit": commit_info,
        "merge_commands": merge_cmds,
        "recommendation": synth["recommendation"],
        "dissents": synth["dissents"],
        "message": (
            f"Work session finished ({stop_reason}). "
            "Chair does NOT auto-merge. Review the worktree, then run merge_commands "
            "when you are ready."
        ),
    }
