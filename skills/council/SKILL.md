---
name: council
description: >
  Multi-seat deliberation for Hermes. Use when the user wants a council
  meeting, multi-perspective review, or autonomous council work session.
  Prefer the council tool over role-playing seats yourself.
---

# Council

You have the **`council` tool** (and `/council` slash command). The engine owns
the protocol — you call actions; you do **not** voice every seat yourself.

## When to use

- Design / ship decisions that need dissent preserved
- Multi-role review (security, QA, PM, staff eng, …)
- Autonomous bounded implementation with a chair and worktree isolation

## Flow

### Setup
1. `council` action=`list_templates` if unsure
2. `council` action=`convene` template=`software-team` (or other)
3. `council` action=`info` to confirm roster

### Interactive meeting
1. `meeting_start` with `task`
2. `meeting_round` (optionally with `user_steer`) until the human is ready
3. `meeting_conclude` → writes `.council/records/` and may update memory

### Autonomous work
1. `work_start` with `task` (requires git repo)
2. `work_tick` until status is concluded/stopped
3. **Never merge** — show `merge_commands` to the user and wait for approval
4. Or `work_stop` to halt early

## Rules

- Do not flatten dissent into false consensus.
- Project state lives under **`.council/`** in the project root.
- Seat personalities are editable markdown in `.council/seats/`.
- For `work`, all edits belong in the session worktree; the human owns the merge.
- If a session dies mid-flight, `status` lists interrupted scratchpads — offer
  resume (continue with same scratch via a new round) or archive, never silent delete.

## Templates bundled

software-team (default), product-engineering-team, c-suite, solo-founder,
writing-lab, hedge-fund-team, research-lab (maths / computing / architecture / controls).
