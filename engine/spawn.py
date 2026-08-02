"""Seat workers — subagent lifecycle when available, else host LLM."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .council_io import Seat
from .memory import build_manifest

logger = logging.getLogger(__name__)

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "next_seat": {
            "type": "string",
            "description": "Seat name to act next, or empty if done",
        },
        "instruction": {
            "type": "string",
            "description": "Specific instruction for that seat this turn",
        },
        "done": {
            "type": "boolean",
            "description": "True if the task is complete enough to stop",
        },
        "reason": {
            "type": "string",
            "description": "Why this seat / why done",
        },
    },
    "required": ["done", "reason"],
}

SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendation": {"type": "string"},
        "reasoning": {"type": "string"},
        "dissents": {
            "type": "string",
            "description": (
                "Preserved dissent in each seat's voice. "
                "Use '_No dissent recorded._' only if truly unanimous."
            ),
        },
        "follow_ups": {"type": "string"},
        "memory_topic": {
            "type": "string",
            "description": "Short kebab topic slug for long-term memory, or empty",
        },
        "memory_decision": {"type": "string"},
        "memory_why": {"type": "string"},
    },
    "required": ["recommendation", "reasoning", "dissents"],
}


def _toolsets_for_mode(mode: str, seat: Seat) -> tuple[str, ...]:
    # Map seat frontmatter loosely onto Hermes toolsets
    declared = {t.lower() for t in seat.tools}
    if mode == "work":
        base = ["file", "terminal"]
        if "web_search" in declared or "web" in declared:
            base.append("web")
        return tuple(base)
    # meeting: read-only by default
    base = ["file"]
    if "web_search" in declared or "web" in declared:
        base.append("web")
    return tuple(base)


def speak_as_seat(
    ctx: Any,
    *,
    seat: Seat,
    task: str,
    scratch: str,
    root: str,
    mode: str,
    session_id: str,
    turn: int,
    instruction: str = "",
    worktree_path: Optional[str] = None,
    memory_budget: int = 8000,
) -> Dict[str, Any]:
    """Run one seat contribution. Returns {ok, text, via, error?}."""
    manifest = build_manifest(Path(root), memory_budget)
    goal = (
        f"[Council seat: {seat.name} / {seat.title}]\n"
        f"Mode: {mode}\n"
        f"Task: {task}\n"
    )
    if instruction:
        goal += f"Chair instruction this turn: {instruction}\n"
    if worktree_path:
        goal += (
            f"\nAll file edits MUST stay under the worktree absolute path:\n"
            f"  {worktree_path}\n"
            f"Treat that directory as the project root. Do not modify files outside it.\n"
        )
    else:
        goal += (
            "\nThis is a meeting turn: read-only. Do not edit project files. "
            "Offer judgment, risks, and concrete recommendations.\n"
        )

    context = (
        f"{seat.system_prompt}\n\n"
        f"---\n"
        f"Council memory manifest (Read full topic files on demand under "
        f"{root}/.council/memory/):\n{manifest}\n\n"
        f"---\n"
        f"Shared scratchpad so far:\n{scratch[-24000:]}\n\n"
        f"---\n"
        f"Respond in your seat's voice. Be concrete. Name dissent explicitly "
        f"when you disagree. Do not speak for other seats.\n"
    )

    # Prefer full subagent when available (needs active parent turn)
    lifecycle = getattr(ctx, "subagent_lifecycle", None) if ctx is not None else None
    if lifecycle is not None and mode == "work":
        try:
            from agent.subagent_lifecycle import SubagentLaunchRequest

            handle = lifecycle.launch(
                SubagentLaunchRequest(
                    goal=goal[:16000],
                    context=context[:32000],
                    role="leaf",
                    allowed_toolsets=_toolsets_for_mode(mode, seat),
                    correlation_id=f"council-{session_id}-{seat.name}-{turn}",
                    metadata={
                        "council_session": session_id,
                        "council_seat": seat.name,
                        "council_mode": mode,
                    },
                )
            )
            terminal = lifecycle.wait(handle, timeout_seconds=900)
            if terminal.timed_out:
                return {
                    "ok": False,
                    "via": "subagent",
                    "error": "seat_timeout",
                    "text": f"({seat.name} timed out)",
                }
            result = lifecycle.result(handle)
            text = (result.summary or "").strip() or f"({seat.name} returned empty)"
            return {
                "ok": bool(result.ready),
                "via": "subagent",
                "text": text,
                "state": str(result.terminal_state),
            }
        except Exception as exc:
            logger.warning("subagent seat spawn failed (%s); falling back to llm", exc)

    # Meeting (or fallback): single-shot host LLM call — persona judgment
    llm = getattr(ctx, "llm", None) if ctx is not None else None
    if llm is not None:
        try:
            result = llm.complete(
                messages=[
                    {"role": "system", "content": seat.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"{goal}\n\nMemory manifest:\n{manifest}\n\n"
                            f"Scratchpad:\n{scratch[-20000:]}\n\n"
                            "Give your seat's contribution now."
                        ),
                    },
                ],
                purpose=f"council.seat.{seat.name}",
                max_tokens=2048,
            )
            text = (getattr(result, "text", None) or str(result) or "").strip()
            return {"ok": True, "via": "llm", "text": text or f"({seat.name} silent)"}
        except Exception as exc:
            logger.exception("llm seat call failed")
            return {"ok": False, "via": "llm", "error": str(exc), "text": ""}

    # Last resort: deterministic stub so offline tests / dry runs work
    stub = (
        f"[{seat.name}] Considering: {task[:200]}. "
        f"(No LLM/subagent available in this context — stub contribution.)"
    )
    return {"ok": True, "via": "stub", "text": stub}


def route_next(
    ctx: Any,
    *,
    chair: Seat,
    task: str,
    scratch: str,
    seats: List[str],
    seat_turns: int,
    max_turns: int,
) -> Dict[str, Any]:
    """Chair routing judgment. Returns done/next_seat/instruction/reason."""
    llm = getattr(ctx, "llm", None) if ctx is not None else None
    fallback_seat = seats[seat_turns % len(seats)] if seats else ""

    if llm is not None:
        try:
            result = llm.complete_structured(
                instructions=(
                    f"You are the council chair ({chair.name} / {chair.title}). "
                    "Decide whether the autonomous work task is done, or which "
                    "seat should act next and what they should do. "
                    f"Seats available: {', '.join(seats)}. "
                    f"Seat turns used: {seat_turns}/{max_turns}."
                ),
                input=[
                    {
                        "type": "text",
                        "text": (
                            f"Task: {task}\n\nScratchpad tail:\n{scratch[-12000:]}"
                        ),
                    }
                ],
                json_schema=ROUTE_SCHEMA,
                purpose="council.chair.route",
                temperature=0.2,
                max_tokens=400,
            )
            parsed = getattr(result, "parsed", None) or {}
            if isinstance(parsed, dict) and parsed:
                done = bool(parsed.get("done"))
                next_seat = str(parsed.get("next_seat") or "").strip()
                if not done and next_seat not in seats:
                    next_seat = fallback_seat
                return {
                    "done": done,
                    "next_seat": "" if done else next_seat,
                    "instruction": str(parsed.get("instruction") or ""),
                    "reason": str(parsed.get("reason") or ""),
                    "via": "llm",
                }
        except Exception as exc:
            logger.warning("chair route structured call failed: %s", exc)

    # Round-robin fallback
    if seat_turns >= max_turns:
        return {
            "done": True,
            "next_seat": "",
            "instruction": "",
            "reason": "max_turns reached (fallback router)",
            "via": "fallback",
        }
    return {
        "done": False,
        "next_seat": fallback_seat,
        "instruction": "Advance the task; leave clear notes on the scratchpad.",
        "reason": "round-robin fallback",
        "via": "fallback",
    }


def synthesize(
    ctx: Any,
    *,
    chair: Seat,
    task: str,
    scratch: str,
    mode: str,
) -> Dict[str, Any]:
    """Chair synthesis into structured record fields."""
    llm = getattr(ctx, "llm", None) if ctx is not None else None
    if llm is not None:
        try:
            result = llm.complete_structured(
                instructions=(
                    f"You are the council chair ({chair.name}). Synthesize the "
                    f"{mode} session into one recommendation. Preserve dissent "
                    "in each disagreeing seat's own voice — never flatten into "
                    "false consensus. Be concrete and merciful in tone."
                ),
                input=[
                    {
                        "type": "text",
                        "text": f"Task: {task}\n\nFull scratchpad:\n{scratch[-28000:]}",
                    }
                ],
                json_schema=SYNTHESIS_SCHEMA,
                purpose="council.chair.synthesize",
                temperature=0.3,
                max_tokens=2048,
            )
            parsed = getattr(result, "parsed", None) or {}
            if isinstance(parsed, dict) and parsed.get("recommendation"):
                return {
                    "ok": True,
                    "via": "llm",
                    "recommendation": str(parsed.get("recommendation") or ""),
                    "reasoning": str(parsed.get("reasoning") or ""),
                    "dissents": str(
                        parsed.get("dissents") or "_No dissent recorded._"
                    ),
                    "follow_ups": str(parsed.get("follow_ups") or ""),
                    "memory_topic": str(parsed.get("memory_topic") or ""),
                    "memory_decision": str(parsed.get("memory_decision") or ""),
                    "memory_why": str(parsed.get("memory_why") or ""),
                }
        except Exception as exc:
            logger.warning("chair synthesis failed: %s", exc)

    # Offline / fallback synthesis from scratch tail
    tail = scratch[-4000:] if scratch else "(empty scratchpad)"
    return {
        "ok": True,
        "via": "fallback",
        "recommendation": f"See scratchpad for deliberation on: {task}",
        "reasoning": tail,
        "dissents": (
            "_Synthesis ran without LLM; re-check scratchpad for seat-level dissent._"
        ),
        "follow_ups": "",
        "memory_topic": "",
        "memory_decision": "",
        "memory_why": "",
    }
