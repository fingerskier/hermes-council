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

### Desktop seat board

```bash
mkdir -p "$HERMES_HOME/desktop-plugins/council"
ln -sfn ~/fingerskier/hermes-council/desktop-plugins/council/plugin.js \
  "$HERMES_HOME/desktop-plugins/council/plugin.js"
```

Restart gateway/desktop so `dashboard/plugin_api.py` mounts, then
**⌘K → Reload desktop plugins** and open **Council** in the sidebar.

Project state lives in `.council/`. The chair never auto-merges work sessions — you own the merge.

Docs: https://github.com/fingerskier/hermes-council

### Web dashboard tab

The web dashboard loads `dashboard/dist/index.js` (see `dashboard/manifest.json`).
Open **Council** in the left nav after enabling the plugin and restarting
`hermes-dashboard` if needed. Set **Project root** to the repo that should own
`.council/` (empty = server cwd, usually `~/.hermes`).
