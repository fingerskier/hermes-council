# Scratchpad — work

Ephemeral, append-only working memory for a single session. Every turn reads
this before acting; the chair routes and synthesizes from it. Archived (not
deleted) to `records/<id>.scratch.md` at session end as the audit artifact.

- **Task:** Extract the retry-with-backoff logic copy-pasted in the email and webhook clients into one shared helper.
- **Session:** 20260606-101500-extract-retry-helper
- **Started:** 2026-06-06 10:15
- **Chair:** staff-engineer
- **Seats (chair-selected subset — work does not run all seats):** staff-engineer, qa-engineer

---

<!-- Chair selected staff-engineer and qa-engineer; security-engineer and
     product-manager sat out — a no-behavior-change refactor needs neither a
     threat model nor a scope call. -->

## Turn 1 — staff-engineer
Mapped the two copies. `EmailClient.send` and `WebhookClient.deliver` each have
their own backoff loop; they've drifted (webhook caps at 30s, email doesn't).
Plan: add `src/util/retry.ts` exporting `withRetry(fn, { attempts, baseMs, maxMs,
jitter })`, defaults matching today's email behavior, and pass `maxMs: 30000` from
the webhook caller so neither caller changes behavior. No new dependency.

## Turn 2 — staff-engineer
(chair routed back to staff-engineer to implement) Wrote `src/util/retry.ts`,
rewired both callers, deleted the inline loops. `npm run build` clean. The cap
difference is preserved via the per-caller `maxMs` option.

## Turn 3 — qa-engineer
(chair routed to qa-engineer) Holding "done": a retry helper with no schedule
test is a regression waiting to land silently. Added `test/util/retry.test.ts`
using a faked clock to assert the per-attempt delays (base, 2×base, capped), plus
the success-after-N-failures path. Green locally. **Dissent recorded:** don't
call this done without that test in the diff.

## Turn 4 — staff-engineer
(chair) Agreed and folded the test in — it's a fair gate, not scope creep. Diff
is: new helper, two call sites simplified, one test file. Behavior unchanged.
Declaring done; merge goes to the user.

---
<!-- Chair: done at Turn 4. max_turns (12) not reached; scratchpad well under
     scratch_max_bytes. Stop reason: chair-done. -->
