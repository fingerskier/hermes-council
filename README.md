# hermes-council

**Multi-seat deliberation engine for [Hermes Agent](https://hermes-agent.nousresearch.com/).**

A council of named **seats** (personalities) deliberates under a **chair**.  
Interactive **meetings** keep you in the loop; autonomous **work** sessions grind in a git worktree.  
The chair synthesizes one answer and **preserves dissent** in an auditable `.council/` record.  
**Never auto-merges.**

This is a port of the [council-ai-plugin](https://github.com/fingerskier/council-ai-plugin) idea from Claude/Codex skill-orchestration into a **real Hermes plugin**: Python owns the protocol; the model owns judgment.

## Install

```bash
hermes plugins install fingerskier/hermes-council --enable
# or from a clone:
hermes plugins install /path/to/hermes-council --enable
```

Enable if needed:

```bash
hermes plugins enable council
```

Dev symlink into the active profile:

```bash
ln -sfn ~/fingerskier/hermes-council ~/.hermes/profiles/fingerskier/plugins/council
hermes plugins enable council
```

Requires nothing beyond Hermes itself (PyYAML is used when present; a small built-in YAML subset covers bundled templates otherwise).

## Quick start

Inside a project directory:

```text
/council convene software-team
/council info
/council meeting Should we adopt a job queue?
```

Or via the agent tool:

```json
{"action": "convene", "template": "software-team"}
{"action": "meeting_start", "task": "Should we adopt a job queue?"}
{"action": "meeting_round", "session_id": "..."}
{"action": "meeting_conclude", "session_id": "..."}
```

Autonomous work (git repo required):

```text
/council work implement the retry helper and preserve dissents
```

Then `work_tick` until done. Review the worktree; merge yourself.

CLI helpers:

```bash
hermes council templates
hermes council convene software-team
hermes council info
hermes council status
```

## Verbs

| Action | Purpose |
|--------|---------|
| `list_templates` | Bundled templates |
| `convene` | Stamp template → `.council/` |
| `info` | Roster table |
| `status` | Sessions + interrupted scratchpads |
| `meeting_start` / `meeting_round` / `meeting_conclude` | Human-in-the-loop |
| `work_start` / `work_tick` / `work_stop` | Autonomous worktree loop |
| `session_cancel` | Stop either mode without synthesis, record, or worktree commit |

## Layout

**Plugin (library):**

```text
data/personalities/*.md   # seat library
data/templates/*.yaml     # presets
engine/                   # deterministic protocol
skills/council/SKILL.md   # thin agent guidance
```

**Project (user-owned):**

```text
.council/
├── council.yaml
├── seats/*.md
├── memory/*.md
├── scratch/          # ephemeral (gitignored)
├── records/          # durable synthesis + archived scratch
├── sessions/         # engine state JSON
└── worktrees/        # work isolation (gitignored)
```

## Templates

- `software-team` (default)
- `product-engineering-team`
- `c-suite`
- `solo-founder`
- `writing-lab`
- `hedge-fund-team`
- `research-lab` — pure research (maths, computing, architecture, controls, methodology)

Add a seat: drop markdown in `data/personalities/` (or `.council/seats/` after convene) and list it in the template / `council.yaml`.

## Desktop UI

Seat columns + steer input for Hermes Desktop:

```bash
# Desktop plugin (renderer) — folder name must be council
mkdir -p "$HERMES_HOME/desktop-plugins/council"
ln -sfn /path/to/hermes-council/desktop-plugins/council/plugin.js \
  "$HERMES_HOME/desktop-plugins/council/plugin.js"
```

With the fingerskier profile:

```bash
mkdir -p ~/.hermes/profiles/fingerskier/desktop-plugins/council
ln -sfn ~/fingerskier/hermes-council/desktop-plugins/council/plugin.js \
  ~/.hermes/profiles/fingerskier/desktop-plugins/council/plugin.js
```

Backend API lives in the Python plugin (`dashboard/plugin_api.py`) and mounts only
when `council` is in `plugins.enabled`. **Restart the gateway / desktop backend**
after installing so `/api/plugins/council/*` is available.

In Desktop: **⌘K → Reload desktop plugins**, then open **Council** in the sidebar
(or palette “Open Council”). Start either a meeting or work session; every active
session exposes **Cancel** and **Conclude**, and every concluded/stopped session
shows the new-session launcher again. Open **Council Editor** to reorder seats,
choose or enter models, and edit persona Markdown. Editor changes are explicit-save
only and retain an unsaved warning after validation or persistence failures.

## Design principles

1. **Personalities are data**, not registered agents.  
2. **Engine owns stop triggers** (`max_turns`, scratch size, wall clock, user stop, chair done).  
3. **Dissent is sacred** — records require a Dissents section.  
4. **Human owns the merge** after `work`.  
5. **Same `.council/` schema** spirit as the original Claude plugin for portability of artifacts.

## Tests

```bash
cd ~/fingerskier/hermes-council
python3 -m unittest discover -s tests -v
```

## Status

v0.1.0 — spine complete:

- convene / info / meeting / work engines  
- stub + host-LLM + subagent seat backends  
- slash command, agent tool, CLI  
- bundled personalities/templates from council-ai-plugin  

Next: richer seat tool policies, optional dual-write compatibility helpers.

## License

MIT (see LICENSE). Personalities/templates adapted from council-ai-plugin.
