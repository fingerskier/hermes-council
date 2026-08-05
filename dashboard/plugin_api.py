"""Council dashboard / desktop backend API.

Mounted at ``/api/plugins/council/`` when the council plugin is enabled.
Thin wrappers over the engine so the desktop seat-column UI and the agent
tool share one protocol.
"""

from __future__ import annotations

import importlib
import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter()

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_PKG = "hermes_council_plugin_api"
_lock = threading.Lock()
_busy: Dict[str, str] = {}  # session_id -> action


def _ensure_pkg() -> None:
    """Register the plugin root as a package without executing register()."""
    if _PKG in sys.modules and getattr(sys.modules[_PKG], "__path__", None) is not None:
        return
    import types

    pkg = types.ModuleType(_PKG)
    pkg.__path__ = [str(PLUGIN_ROOT)]  # type: ignore[attr-defined]
    pkg.__package__ = _PKG
    sys.modules[_PKG] = pkg


def _import(name: str):
    _ensure_pkg()
    return importlib.import_module(f"{_PKG}.{name}")


def _engine_session():
    return _import("engine.session")


def _engine_convene():
    return _import("engine.convene")


def _engine_view():
    return _import("engine.view")


def _engine_editor():
    return _import("engine.editor")


def _engine_info():
    return _import("engine.info")


def _resolve_root(root: Optional[str]) -> Path:
    if root and str(root).strip():
        p = Path(root).expanduser().resolve()
    else:
        p = Path.cwd().resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"invalid root: {p}")
    return p


def _llm_ctx() -> Any:
    """Best-effort host LLM for seat turns outside an agent tool call."""
    try:
        from agent.plugin_llm import PluginLlm

        return SimpleNamespace(llm=PluginLlm(plugin_id="council"), subagent_lifecycle=None)
    except Exception as exc:
        log.warning("council plugin_api: PluginLlm unavailable (%s); stub seats", exc)
        return None


class RootBody(BaseModel):
    root: Optional[str] = None


class ConveneBody(BaseModel):
    root: Optional[str] = None
    template: str = "software-team"
    force: bool = False


class MeetingStartBody(BaseModel):
    root: Optional[str] = None
    task: str = Field(..., min_length=1)


class MeetingRoundBody(BaseModel):
    root: Optional[str] = None
    session_id: str = Field(..., min_length=1)
    user_steer: str = ""


class MeetingConcludeBody(BaseModel):
    root: Optional[str] = None
    session_id: str = Field(..., min_length=1)


class SessionActionBody(BaseModel):
    root: Optional[str] = None
    session_id: str = Field(..., min_length=1)


class EditorSaveBody(BaseModel):
    root: Optional[str] = None
    seats: List[Dict[str, Any]]
    models: Optional[List[str]] = None


@router.get("/health")
async def health():
    return {"ok": True, "plugin": "council", "root": str(PLUGIN_ROOT)}


@router.get("/browse")
async def browse(path: Optional[str] = None):
    """List subdirectories for the dashboard folder picker.

    Returns the resolved path, its parent (if any), whether ``.council/``
    exists here, and child directory names (non-hidden first).
    """
    try:
        if path and str(path).strip():
            p = Path(path).expanduser().resolve()
        else:
            p = Path.home().resolve()
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"path does not exist: {p}")
        if not p.is_dir():
            raise HTTPException(status_code=400, detail=f"not a directory: {p}")

        # Soft sandbox: stay under home or common project roots; still allow
        # absolute navigation the user types (picker is opt-in).
        children: List[Dict[str, Any]] = []
        try:
            entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=f"permission denied: {p}") from exc

        for ent in entries:
            if not ent.is_dir():
                continue
            name = ent.name
            if name.startswith(".") and name not in {".council"}:
                continue
            children.append(
                {
                    "name": name,
                    "path": str(ent.resolve()),
                    "has_council": (ent / ".council").is_dir(),
                }
            )

        parent = None
        if p.parent != p:
            parent = str(p.parent)

        return {
            "ok": True,
            "path": str(p),
            "parent": parent,
            "has_council": (p / ".council").is_dir(),
            "children": children[:500],
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("browse failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/templates")
async def templates():
    try:
        items = _engine_convene().list_templates()
        return {"ok": True, "templates": items}
    except Exception as exc:
        log.exception("list_templates failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/snapshot")
async def snapshot(root: Optional[str] = None, session_id: Optional[str] = None):
    try:
        r = _resolve_root(root)
        snap = _engine_view().build_snapshot(r, session_id)
        snap["busy"] = _busy.get(session_id or (snap.get("session_id") or ""))
        return snap
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("snapshot failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/info")
async def info(root: Optional[str] = None):
    try:
        r = _resolve_root(root)
        return _engine_info().council_info(r)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("info failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/editor")
async def editor(root: Optional[str] = None):
    try:
        r = _resolve_root(root)
        return _engine_editor().load_editor(r)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("editor load failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/editor/save")
async def editor_save(body: EditorSaveBody):
    try:
        r = _resolve_root(body.root)
        return _engine_editor().save_editor(
            r,
            seats=body.seats,
            models=body.models,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("editor save failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status")
async def status(root: Optional[str] = None, session_id: Optional[str] = None):
    try:
        r = _resolve_root(root)
        return _engine_session().status(r, session_id)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("status failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/convene")
async def convene(body: ConveneBody):
    try:
        r = _resolve_root(body.root)
        return _engine_convene().convene(r, body.template, force=body.force)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("convene failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/meeting/start")
async def meeting_start(body: MeetingStartBody):
    try:
        r = _resolve_root(body.root)
        return _engine_session().meeting_start(r, body.task.strip(), ctx=_llm_ctx())
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("meeting_start failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/meeting/round")
async def meeting_round(body: MeetingRoundBody):
    sid = body.session_id.strip()
    with _lock:
        if sid in _busy:
            raise HTTPException(
                status_code=409,
                detail=f"session busy with {_busy[sid]}",
            )
        _busy[sid] = "meeting_round"
    try:
        r = _resolve_root(body.root)
        result = _engine_session().meeting_round(
            r,
            sid,
            ctx=_llm_ctx(),
            user_steer=body.user_steer or "",
        )
        # Attach fresh snapshot so the UI can paint in one round-trip
        try:
            result["snapshot"] = _engine_view().build_snapshot(r, sid)
        except Exception:
            pass
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("meeting_round failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        with _lock:
            _busy.pop(sid, None)


@router.post("/meeting/conclude")
async def meeting_conclude(body: MeetingConcludeBody):
    sid = body.session_id.strip()
    with _lock:
        if sid in _busy:
            raise HTTPException(
                status_code=409,
                detail=f"session busy with {_busy[sid]}",
            )
        _busy[sid] = "meeting_conclude"
    try:
        r = _resolve_root(body.root)
        result = _engine_session().conclude_meeting(r, sid, ctx=_llm_ctx())
        try:
            result["snapshot"] = _engine_view().build_snapshot(r, sid)
        except Exception:
            pass
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("meeting_conclude failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        with _lock:
            _busy.pop(sid, None)


@router.post("/session/cancel")
async def session_cancel(body: SessionActionBody):
    sid = body.session_id.strip()
    with _lock:
        if sid in _busy:
            raise HTTPException(status_code=409, detail=f"session busy with {_busy[sid]}")
        _busy[sid] = "session_cancel"
    try:
        r = _resolve_root(body.root)
        result = _engine_session().cancel_session(r, sid)
        result["snapshot"] = _engine_view().build_snapshot(r, sid)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("session_cancel failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        with _lock:
            _busy.pop(sid, None)


@router.post("/work/start")
async def work_start(body: MeetingStartBody):
    try:
        r = _resolve_root(body.root)
        return _engine_session().work_start(r, body.task.strip(), ctx=_llm_ctx())
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("work_start failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/work/tick")
async def work_tick(body: SessionActionBody):
    sid = body.session_id.strip()
    with _lock:
        if sid in _busy:
            raise HTTPException(status_code=409, detail=f"session busy with {_busy[sid]}")
        _busy[sid] = "work_tick"
    try:
        r = _resolve_root(body.root)
        result = _engine_session().work_tick(r, sid, ctx=_llm_ctx())
        result["snapshot"] = _engine_view().build_snapshot(r, sid)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("work_tick failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        with _lock:
            _busy.pop(sid, None)


@router.post("/work/conclude")
async def work_conclude(body: SessionActionBody):
    sid = body.session_id.strip()
    with _lock:
        if sid in _busy:
            raise HTTPException(status_code=409, detail=f"session busy with {_busy[sid]}")
        _busy[sid] = "work_conclude"
    try:
        r = _resolve_root(body.root)
        result = _engine_session().work_stop(
            r,
            sid,
            ctx=_llm_ctx(),
            reason="user_concluded",
        )
        result["snapshot"] = _engine_view().build_snapshot(r, sid)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("work_conclude failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        with _lock:
            _busy.pop(sid, None)
