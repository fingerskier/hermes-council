# Record — Extract the duplicated retry logic into one helper

Durable synthesis the chair writes when a `work` session concludes. The seats
did this autonomously in a worktree; the chair declared done and handed the
merge to the user (it never auto-merges).

- **Session:** 20260606-101500-extract-retry-helper
- **Mode:** work
- **Concluded:** 2026-06-06 10:41
- **Chair:** staff-engineer
- **Seats:** staff-engineer, qa-engineer
- **Task:** Extract the retry-with-backoff logic copy-pasted in the email and webhook clients into one shared helper.

## Recommendation
Added `src/util/retry.ts` — a single `withRetry(fn, opts)` wrapping the
exponential-backoff-with-jitter loop. Rewired `EmailClient.send` and
`WebhookClient.deliver` to call it; deleted both inline copies. Behavior is
unchanged: same default of 3 attempts and same base delay, now expressed once.

## Reasoning trail
- The two copies had already drifted — the webhook client capped backoff at 30s,
  the email client didn't. The helper takes the cap as an option so each caller
  keeps its own value; no behavior change was smuggled into the refactor.
- Kept the signature minimal (`fn`, `{ attempts, baseMs, maxMs, jitter }`) rather
  than a config object class — there are two callers, not twenty.
- Considered pulling in a library (`p-retry`) and rejected it: a new dependency
  for ~15 lines we already own and test isn't worth the supply-chain surface.

## Dissents (preserved)
- **qa-engineer:** The shared helper is only as safe as its test. I will not
  call this done until there's a test that asserts the backoff *schedule* (delays
  per attempt), not just that it eventually succeeds — otherwise a regression in
  the timing math passes silently. Added `test/util/retry.test.ts` with a faked
  clock; merge is fine once that's green.

## Follow-ups
- [ ] Review and merge the worktree branch `council/work-20260606-101500-extract-retry-helper` (owner: user)
- [ ] Backfill a jitter-distribution test if flake reappears in CI (owner: qa-engineer)

→ memory updated: none
