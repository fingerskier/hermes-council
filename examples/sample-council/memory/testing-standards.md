# Memory: Testing standards

## Decision
New features land with tests written first (TDD). The qa-engineer seat blocks
synthesis if a `work` session produced code without a failing-then-passing test.
→ record: STANDING (standing council practice; predates the recorded sessions,
no single record sets it)

## Why
Two regressions in Q1 shipped because "we'll add tests later" never happened.

## Practice
- Unit tests colocated with the module; integration tests under `test/integration/`.
- A bugfix starts with a test that reproduces the bug.
