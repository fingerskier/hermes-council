"""Hermes Council plugin — multi-seat deliberation with a real engine.

Personalities and templates are data. The protocol (convene / meeting / work,
scratchpads, records, worktrees, budgets) runs in Python so sessions are
auditable and stop triggers are enforced — not hoped for.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .schemas import COUNCIL_SCHEMA
from .tools import (
    cli_handler,
    handle_council,
    handle_slash,
    set_plugin_ctx,
    setup_cli,
)

logger = logging.getLogger(__name__)

PLUGIN_ROOT = Path(__file__).resolve().parent


def register(ctx) -> None:
    """Register tools, slash command, CLI, and bundled skill."""
    set_plugin_ctx(ctx)

    ctx.register_tool(
        name="council",
        toolset="council",
        schema=COUNCIL_SCHEMA,
        handler=handle_council,
        description=(
            "Convene a multi-seat council; run meetings or autonomous work; "
            "preserve dissent in .council/records/"
        ),
        emoji="🏛️",
    )

    ctx.register_command(
        name="council",
        handler=handle_slash,
        description="Council: convene | info | meeting | work | status",
        args_hint="convene [template] | info | meeting <task> | work <task> | ...",
    )

    ctx.register_cli_command(
        name="council",
        help="Multi-seat council (convene, info, templates, status)",
        setup_fn=setup_cli,
        handler_fn=cli_handler,
        description="Deterministic multi-perspective deliberation for a project.",
    )

    skill_path = PLUGIN_ROOT / "skills" / "council" / "SKILL.md"
    if skill_path.exists():
        try:
            ctx.register_skill("council", str(skill_path))
        except Exception as exc:
            logger.warning("Failed to register council skill: %s", exc)

    logger.info("council plugin registered")
