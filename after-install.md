# Council plugin installed

Enable it (if you skipped `--enable`):

```bash
hermes plugins enable council
```

Then in any project:

```text
/council convene software-team
/council meeting <your decision>
```

Project state lives in `.council/`. The chair never auto-merges work sessions — you own the merge.

Docs: https://github.com/fingerskier/hermes-council
