"""Tool handlers for the council plugin."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .engine.convene import convene, list_templates
from .engine.info import council_info
from .engine.paths import resolve_root
from .engine.session import (
    SessionError,
    cancel_session,
    conclude_meeting,
    meeting_round,
    meeting_start,
    status,
    work_start,
    work_stop,
    work_tick,
)

logger = logging.getLogger(__name__)

# Set by register(ctx)
_PLUGIN_CTX: Any = None


def set_plugin_ctx(ctx: Any) -> None:
    global _PLUGIN_CTX
    _PLUGIN_CTX = ctx


def _ctx() -> Any:
    return _PLUGIN_CTX


def _ok(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _err(message: str, **extra: Any) -> str:
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, default=str)


def handle_council(args: Dict[str, Any], **kwargs: Any) -> str:
    """Dispatch the multi-action council tool."""
    del kwargs  # Hermes may pass task_id etc.
    action = str(args.get("action") or "").strip().lower()
    if not action:
        return _err("action is required")

    try:
        root = resolve_root(args.get("root"))
    except Exception as exc:
        return _err(f"invalid root: {exc}")

    try:
        if action == "list_templates":
            return _ok({"ok": True, "templates": list_templates()})

        if action == "convene":
            template = str(args.get("template") or "software-team").strip()
            force = bool(args.get("force") or False)
            return _ok(convene(root, template, force=force))

        if action == "info":
            return _ok(council_info(root))

        if action == "status":
            sid = args.get("session_id")
            return _ok(status(root, str(sid) if sid else None))

        if action == "meeting_start":
            task = str(args.get("task") or "").strip()
            if not task:
                return _err("task is required for meeting_start")
            return _ok(meeting_start(root, task, ctx=_ctx()))

        if action == "meeting_round":
            sid = str(args.get("session_id") or "").strip()
            if not sid:
                return _err("session_id is required for meeting_round")
            steer = str(args.get("user_steer") or "")
            return _ok(
                meeting_round(root, sid, ctx=_ctx(), user_steer=steer)
            )

        if action == "meeting_conclude":
            sid = str(args.get("session_id") or "").strip()
            if not sid:
                return _err("session_id is required for meeting_conclude")
            return _ok(conclude_meeting(root, sid, ctx=_ctx()))

        if action == "session_cancel":
            sid = str(args.get("session_id") or "").strip()
            if not sid:
                return _err("session_id is required for session_cancel")
            return _ok(cancel_session(root, sid))

        if action == "work_start":
            task = str(args.get("task") or "").strip()
            if not task:
                return _err("task is required for work_start")
            return _ok(work_start(root, task, ctx=_ctx()))

        if action == "work_tick":
            sid = str(args.get("session_id") or "").strip()
            if not sid:
                return _err("session_id is required for work_tick")
            return _ok(work_tick(root, sid, ctx=_ctx()))

        if action == "work_stop":
            sid = str(args.get("session_id") or "").strip()
            if not sid:
                return _err("session_id is required for work_stop")
            reason = str(args.get("reason") or "user_stop")
            return _ok(work_stop(root, sid, ctx=_ctx(), reason=reason))

        return _err(
            f"unknown action: {action}",
            actions=[
                "list_templates",
                "convene",
                "info",
                "status",
                "meeting_start",
                "meeting_round",
                "meeting_conclude",
                "session_cancel",
                "work_start",
                "work_tick",
                "work_stop",
            ],
        )
    except SessionError as exc:
        return _err(str(exc))
    except FileNotFoundError as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("council tool failed")
        return _err(f"council failed: {exc}")


def handle_slash(raw_args: str) -> Optional[str]:
    """Slash command: /council <verb> [args...]."""
    text = (raw_args or "").strip()
    if not text:
        return (
            "Usage:\n"
            "  /council convene [template]\n"
            "  /council info\n"
            "  /council status [session_id]\n"
            "  /council meeting <task>\n"
            "  /council meeting_round <session_id> [steer...]\n"
            "  /council conclude <session_id>\n"
            "  /council cancel <session_id>\n"
            "  /council work <task>\n"
            "  /council tick <session_id>\n"
            "  /council stop <session_id>\n"
            "  /council templates"
        )

    parts = text.split(None, 1)
    verb = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    mapping = {
        "templates": ("list_templates", {}),
        "list_templates": ("list_templates", {}),
        "convene": ("convene", {"template": rest or "software-team"}),
        "info": ("info", {}),
        "status": ("status", {"session_id": rest} if rest else {}),
        "meeting": ("meeting_start", {"task": rest.strip("\"'")}),
        "meeting_start": ("meeting_start", {"task": rest.strip("\"'")}),
        "meeting_round": None,  # special
        "round": None,
        "conclude": ("meeting_conclude", {"session_id": rest.split()[0] if rest else ""}),
        "meeting_conclude": (
            "meeting_conclude",
            {"session_id": rest.split()[0] if rest else ""},
        ),
        "cancel": ("session_cancel", {"session_id": rest.split()[0] if rest else ""}),
        "session_cancel": (
            "session_cancel",
            {"session_id": rest.split()[0] if rest else ""},
        ),
        "work": ("work_start", {"task": rest.strip("\"'")}),
        "work_start": ("work_start", {"task": rest.strip("\"'")}),
        "tick": ("work_tick", {"session_id": rest.split()[0] if rest else ""}),
        "work_tick": ("work_tick", {"session_id": rest.split()[0] if rest else ""}),
        "stop": ("work_stop", {"session_id": rest.split()[0] if rest else ""}),
        "work_stop": ("work_stop", {"session_id": rest.split()[0] if rest else ""}),
    }

    if verb in {"meeting_round", "round"}:
        bits = rest.split(None, 1)
        sid = bits[0] if bits else ""
        steer = bits[1] if len(bits) > 1 else ""
        args = {
            "action": "meeting_round",
            "session_id": sid,
            "user_steer": steer,
        }
        result = handle_council(args)
        return _pretty(result)

    if verb not in mapping:
        return f"Unknown verb `{verb}`.\n" + (handle_slash("") or "")

    action, payload = mapping[verb]  # type: ignore[misc]
    args = {"action": action, **payload}
    result = handle_council(args)
    return _pretty(result)


def _pretty(raw_json: str) -> str:
    try:
        data = json.loads(raw_json)
    except Exception:
        return raw_json
    if data.get("table"):
        return data["table"]
    if data.get("message"):
        # include key fields
        lines = [str(data["message"])]
        for key in (
            "session_id",
            "record",
            "path",
            "recommendation",
            "merge_commands",
            "next",
            "next_options",
        ):
            if key in data and data[key] not in (None, "", []):
                lines.append(f"{key}: {data[key]}")
        return "\n".join(lines)
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def setup_cli(subparser) -> None:
    """``hermes council ...`` CLI."""
    sub = subparser.add_subparsers(dest="council_cmd")

    p_conv = sub.add_parser("convene", help="Stamp a template into .council/")
    p_conv.add_argument("template", nargs="?", default="software-team")
    p_conv.add_argument("--root", default=None)
    p_conv.add_argument("--force", action="store_true")

    p_info = sub.add_parser("info", help="Show convened roster")
    p_info.add_argument("--root", default=None)

    p_tpl = sub.add_parser("templates", help="List bundled templates")

    p_status = sub.add_parser("status", help="Session / interrupted status")
    p_status.add_argument("session_id", nargs="?", default=None)
    p_status.add_argument("--root", default=None)


def cli_handler(args) -> int:
    cmd = getattr(args, "council_cmd", None)
    root = resolve_root(getattr(args, "root", None))
    if cmd == "templates" or cmd is None:
        print(json.dumps({"templates": list_templates()}, indent=2))
        return 0
    if cmd == "convene":
        result = convene(
            root,
            getattr(args, "template", "software-team"),
            force=bool(getattr(args, "force", False)),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1
    if cmd == "info":
        result = council_info(root)
        print(result.get("table") or json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    if cmd == "status":
        result = status(root, getattr(args, "session_id", None))
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1
    print(f"Unknown council command: {cmd}")
    return 2
