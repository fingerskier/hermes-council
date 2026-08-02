"""Tool schemas for the council plugin."""

COUNCIL_SCHEMA = {
    "name": "council",
    "description": (
        "Multi-perspective council engine. Convene named seats, run interactive "
        "meetings or autonomous work sessions, and preserve dissent in "
        ".council/records/. Prefer this tool over role-playing seats yourself.\n\n"
        "Typical flows:\n"
        "1) action=convene (template=software-team)\n"
        "2) action=meeting_start with task, then meeting_round until ready, "
        "then meeting_conclude\n"
        "3) action=work_start with task, then work_tick until finished "
        "(or work_stop). Never auto-merge worktrees.\n"
        "Use action=info / status / list_templates anytime."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Council verb to run",
                "enum": [
                    "list_templates",
                    "convene",
                    "info",
                    "status",
                    "meeting_start",
                    "meeting_round",
                    "meeting_conclude",
                    "work_start",
                    "work_tick",
                    "work_stop",
                ],
            },
            "root": {
                "type": "string",
                "description": (
                    "Absolute project root containing or receiving .council/. "
                    "Defaults to the current working directory."
                ),
            },
            "template": {
                "type": "string",
                "description": "Template name for convene (default: software-team)",
            },
            "force": {
                "type": "boolean",
                "description": (
                    "For convene: overwrite council.yaml + seats/ if a council "
                    "already exists. Memory and records are preserved."
                ),
            },
            "task": {
                "type": "string",
                "description": "Task/topic for meeting_start or work_start",
            },
            "session_id": {
                "type": "string",
                "description": "Session id for round/tick/conclude/stop/status",
            },
            "user_steer": {
                "type": "string",
                "description": "Optional user input injected before a meeting_round",
            },
            "reason": {
                "type": "string",
                "description": "Optional stop reason for work_stop",
            },
        },
        "required": ["action"],
    },
}
