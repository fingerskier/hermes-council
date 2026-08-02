# Memory: Background job queue

One memory file per topic. The chair creates or updates the relevant file when a
meeting or work session concludes — durable context the seats read on later
invocations. Keep it short: decisions and their *why*, not transcripts.

## Decision
Adopt a Redis-backed job queue (BullMQ) for background work (email, exports,
webhook fan-out). Decided in the 2026-06-03 meeting.
→ record: `records/20260603-093000-adopt-job-queue.md`

## Why
- Synchronous request handlers were timing out on bulk exports.
- We already run Redis for sessions, so no new infra to operate.

## Constraints the seats agreed on
- Jobs must be idempotent (retries are expected).
- A dead-letter queue is required before any job touches money or email.

## Standing dissent (security-engineer)
Redis is now a correctness dependency, not just a cache. If we don't add
persistence + auth on the Redis instance, a flush loses in-flight jobs silently.
Revisit before launch.
