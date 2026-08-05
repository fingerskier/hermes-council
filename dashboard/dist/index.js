/**
 * Hermes Council — Dashboard Plugin
 *
 * Web UI for multi-seat deliberation. Backend: /api/plugins/council/*
 * Plain IIFE (no build). Uses window.__HERMES_PLUGIN_SDK__ like kanban.
 */
(function () {
  "use strict";

  try {
    var SDK = window.__HERMES_PLUGIN_SDK__;
    if (!SDK || !SDK.React) {
      console.warn("[council] __HERMES_PLUGIN_SDK__ missing");
      return;
    }

    var React = SDK.React;
    var h = React.createElement;
    var C = SDK.components || {};
    var hooks = SDK.hooks || {};
    var useState = hooks.useState;
    var useEffect = hooks.useEffect;
    var useCallback = hooks.useCallback;
    var useRef = hooks.useRef;

    if (!useState || !useEffect || !useCallback || !useRef) {
      console.warn("[council] SDK.hooks incomplete");
      return;
    }

    var Card = C.Card || "div";
    var CardContent = C.CardContent || "div";
    var Badge = C.Badge || "span";
    var Button = C.Button || "button";
    var Input = C.Input || "input";
    var Label = C.Label || "label";
    var Select = C.Select || "select";

    function Textarea(props) {
      props = props || {};
      if (C.Textarea) return h(C.Textarea, props);
      var attrs = {};
      for (var k in props) {
        if (Object.prototype.hasOwnProperty.call(props, k)) attrs[k] = props[k];
      }
      attrs.className = (props.className || "") +
        " flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm";
      return h("textarea", attrs);
    }

    function CardHeader(props) {
      if (C.CardHeader) return h(C.CardHeader, props);
      return h("div", Object.assign({ className: "flex flex-col space-y-1.5 p-6" }, props || {}));
    }

    function CardTitle(props) {
      if (C.CardTitle) return h(C.CardTitle, props);
      return h("h3", Object.assign({
        className: "text-lg font-semibold leading-none tracking-tight",
      }, props || {}));
    }

    function SelectOption(props) {
      if (C.SelectOption) return h(C.SelectOption, props);
      return h("option", props);
    }

    function cn() {
      var out = [];
      for (var i = 0; i < arguments.length; i++) {
        if (arguments[i]) out.push(arguments[i]);
      }
      return out.join(" ");
    }

    function selectChangeHandler(setter) {
      return {
        onValueChange: function (v) { setter(v == null ? "" : v); },
        onChange: function (e) {
          var v = e && e.target ? e.target.value : e;
          setter(v == null ? "" : v);
        },
      };
    }

    var API = "/api/plugins/council";
    var ROOT_KEY = "hermes.council.root";

    function readStoredRoot() {
      try { return window.localStorage.getItem(ROOT_KEY) || ""; }
      catch (e) { return ""; }
    }

    function storeRoot(root) {
      try {
        if (root) window.localStorage.setItem(ROOT_KEY, root);
        else window.localStorage.removeItem(ROOT_KEY);
      } catch (e) { /* ignore */ }
    }

    function qs(params) {
      var u = new URLSearchParams();
      Object.keys(params || {}).forEach(function (k) {
        var v = params[k];
        if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
      });
      var s = u.toString();
      return s ? ("?" + s) : "";
    }

    function apiError(err) {
      var raw = (err && err.message) ? String(err.message) : String(err || "error");
      var m = raw.match(/^(\d{3}):\s*([\s\S]*)$/);
      var body = m ? m[2] : raw;
      try {
        var parsed = JSON.parse(body);
        if (parsed && parsed.detail) {
          return typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
        }
      } catch (e) { /* ignore */ }
      return body || raw;
    }

    function seatColor(name) {
      var hash = 0;
      var s = String(name || "");
      for (var i = 0; i < s.length; i++) hash = ((hash << 5) - hash) + s.charCodeAt(i);
      return "hsl(" + (Math.abs(hash) % 360) + " 55% 55%)";
    }

    function fetchJSON(url, opts) {
      if (SDK.fetchJSON) return SDK.fetchJSON(url, opts);
      opts = opts || {};
      return fetch(url, Object.assign({ credentials: "same-origin" }, opts)).then(function (r) {
        return r.text().then(function (text) {
          if (!r.ok) throw new Error(r.status + ": " + text);
          try { return text ? JSON.parse(text) : {}; }
          catch (e) { return { raw: text }; }
        });
      });
    }

    function SeatColumn(props) {
      var seat = props.seat || {};
      var modelOptions = props.modelOptions || [];
      var locked = !!props.locked;
      var saving = !!props.saving;
      var onModelChange = props.onModelChange;
      var color = seatColor(seat.name);
      var latest = seat.latest;
      var empty = !latest || !(latest.content || "").trim();
      var errored = latest && latest.ok === false;
      var history = seat.history || [];
      var settingsState = useState(false);
      var settingsOpen = settingsState[0];
      var setSettingsOpen = settingsState[1];
      var model = seat.model || "";
      var options = modelOptions.slice();
      if (model && options.indexOf(model) === -1) options.unshift(model);
      var disabled = locked || saving;
      var seatStatus = seat.status || (errored ? "error" : empty ? "idle" : "done");
      var statusLabel = seatStatus;
      var statusClass =
        seatStatus === "thinking" ? "bg-blue-500/15 text-blue-600" :
        seatStatus === "waiting" ? "bg-muted text-muted-foreground" :
        seatStatus === "ready" ? "bg-emerald-500/15 text-emerald-700" :
        seatStatus === "done" ? "bg-emerald-500/10 text-emerald-700" :
        seatStatus === "error" ? "bg-destructive/15 text-destructive" :
        "bg-muted/60 text-muted-foreground";

      return h("section", {
        className: cn(
          "flex min-w-[220px] max-w-[380px] flex-1 flex-col overflow-hidden rounded-md border border-border bg-card",
          (seat.active || seatStatus === "thinking") ? "ring-1 ring-primary/40" : ""
        ),
        style: { borderTopColor: color, borderTopWidth: 2 },
      },
        h("header", { className: "flex items-start gap-2 border-b border-border px-3 py-2" },
          h("div", {
            className: "mt-1 h-2 w-2 shrink-0 rounded-full",
            style: { background: color },
          }),
          h("div", { className: "min-w-0 flex-1" },
            h("div", { className: "flex flex-wrap items-center gap-2" },
              h("span", { className: "truncate text-sm font-medium" }, seat.name || "seat"),
              seat.chair ? h(Badge, { variant: "secondary", className: "text-[10px]" }, "chair") : null,
              h("span", {
                className: "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] uppercase tracking-wide " + statusClass,
              }, statusLabel)
            ),
            seat.title
              ? h("div", { className: "truncate text-xs text-muted-foreground" }, seat.title)
              : null,
            h("div", {
              className: "truncate font-mono text-[10px] text-muted-foreground",
              title: model || "host default",
            }, model || "model: host default")
          ),
          h(Button, {
            size: "sm",
            variant: "ghost",
            type: "button",
            className: "h-7 w-7 shrink-0 p-0 text-xs",
            disabled: disabled && !settingsOpen,
            title: disabled ? "Locked while council is working" : "Seat model",
            onClick: function () {
              if (disabled) return;
              setSettingsOpen(!settingsOpen);
            },
          }, "⚙")
        ),
        settingsOpen
          ? h("div", { className: "space-y-1 border-b border-border px-3 py-2" },
              h(Label, { className: "text-[10px] text-muted-foreground" }, "Model"),
              h("select", {
                className: "h-8 w-full rounded-md border border-input bg-background px-2 font-mono text-xs",
                value: model,
                disabled: disabled,
                onChange: function (e) {
                  if (onModelChange) onModelChange(seat.name, e.target.value);
                },
              },
                h("option", { value: "" }, "Host default"),
                options.map(function (m) {
                  return h("option", { key: m, value: m }, m);
                })
              ),
              h("div", { className: "text-[10px] text-muted-foreground" },
                disabled
                  ? "Disabled while a round / work turn is running."
                  : "Writes model into .council/seats/" + (seat.name || "seat") + ".md")
            )
          : null,
        h("div", { className: "flex-1 space-y-2 overflow-y-auto p-3 text-sm" },
          empty
            ? h("p", { className: "text-xs text-muted-foreground" }, "No contribution yet.")
            : h("div", { className: "space-y-2" },
                errored
                  ? h("div", {
                      className: "rounded border border-destructive/40 bg-destructive/10 px-2 py-1 text-xs text-destructive",
                    }, latest.error || "Seat error")
                  : null,
                h("div", { className: "whitespace-pre-wrap leading-relaxed text-foreground/90" },
                  latest.content || ""),
                latest.turn != null
                  ? h("div", { className: "text-[10px] text-muted-foreground" },
                      "turn " + latest.turn + (latest.via ? (" · " + latest.via) : ""))
                  : null
              ),
          history.length > 1
            ? h("details", { className: "pt-2 text-xs text-muted-foreground" },
                h("summary", { className: "cursor-pointer select-none" },
                  "Earlier (" + (history.length - 1) + ")"),
                h("div", { className: "mt-2 space-y-2" },
                  history.slice(0, -1).reverse().map(function (turn, i) {
                    return h("div", {
                      key: i,
                      className: "whitespace-pre-wrap rounded bg-muted/40 p-2",
                    }, turn.content || "");
                  })
                )
              )
            : null
        )
      );
    }

    function DirectoryPicker(props) {
      var initialPath = props.initialPath || "";
      var onSelect = props.onSelect;
      var onCancel = props.onCancel;
      var pathState = useState(initialPath);
      var path = pathState[0];
      var setPath = pathState[1];
      var dataState = useState(null);
      var data = dataState[0];
      var setData = dataState[1];
      var errState = useState("");
      var err = errState[0];
      var setErr = errState[1];
      var loadingState = useState(true);
      var loading = loadingState[0];
      var setLoading = loadingState[1];

      var load = useCallback(function (p) {
        setLoading(true);
        setErr("");
        var url = API + "/browse" + qs({ path: p || undefined });
        return fetchJSON(url)
          .then(function (res) {
            setData(res);
            setPath((res && res.path) || p || "");
            setLoading(false);
          })
          .catch(function (e) {
            setErr(apiError(e));
            setLoading(false);
          });
      }, []);

      useEffect(function () {
        load(initialPath);
      }, [initialPath, load]);

      var children = (data && data.children) || [];

      return h("div", {
        className:
          "mt-2 w-full max-w-xl rounded-md border border-border bg-card p-3 shadow-sm",
      },
        h("div", { className: "mb-2 flex items-center justify-between gap-2" },
          h("div", { className: "text-sm font-medium" }, "Choose project folder"),
          h(Button, {
            size: "sm",
            variant: "ghost",
            type: "button",
            onClick: onCancel,
          }, "Close")
        ),
        h("div", { className: "mb-2 flex gap-2" },
          h(Input, {
            className: "h-8 flex-1 font-mono text-xs",
            value: path,
            onChange: function (e) { setPath(e.target.value); },
            onKeyDown: function (e) {
              if (e.key === "Enter") load(path);
            },
          }),
          h(Button, {
            size: "sm",
            variant: "outline",
            type: "button",
            onClick: function () { load(path); },
          }, "Go")
        ),
        err
          ? h("div", {
              className: "mb-2 text-xs text-destructive",
            }, err)
          : null,
        h("div", {
          className:
            "mb-2 max-h-56 overflow-y-auto rounded border border-border",
        },
          loading
            ? h("div", { className: "p-3 text-xs text-muted-foreground" }, "Loading…")
            : h("div", { className: "divide-y divide-border" },
                data && data.parent
                  ? h("button", {
                      type: "button",
                      className:
                        "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-muted/50",
                      onClick: function () { load(data.parent); },
                    }, "‥  (parent)")
                  : null,
                children.length
                  ? children.map(function (ch) {
                      return h("button", {
                        key: ch.path,
                        type: "button",
                        className:
                          "flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-muted/50",
                        onClick: function () { load(ch.path); },
                        onDoubleClick: function () {
                          if (onSelect) onSelect(ch.path);
                        },
                      },
                        h("span", { className: "truncate font-mono" }, ch.name),
                        ch.has_council
                          ? h(Badge, {
                              variant: "secondary",
                              className: "shrink-0 text-[10px]",
                            }, ".council")
                          : null
                      );
                    })
                  : h("div", {
                      className: "p-3 text-xs text-muted-foreground",
                    }, "No subfolders")
              )
        ),
        h("div", { className: "flex flex-wrap items-center justify-between gap-2" },
          h("div", { className: "min-w-0 flex-1 truncate font-mono text-[11px] text-muted-foreground" },
            path || "",
            data && data.has_council ? "  · has .council/" : ""
          ),
          h("div", { className: "flex gap-2" },
            h(Button, {
              size: "sm",
              variant: "ghost",
              type: "button",
              onClick: onCancel,
            }, "Cancel"),
            h(Button, {
              size: "sm",
              type: "button",
              disabled: !path,
              onClick: function () {
                if (path && onSelect) onSelect(path);
              },
            }, "Use this folder")
          )
        )
      );
    }

    function CouncilPage() {
      var rootState = useState(readStoredRoot);
      var root = rootState[0];
      var setRoot = rootState[1];
      var rootDraftState = useState(readStoredRoot);
      var rootDraft = rootDraftState[0];
      var setRootDraft = rootDraftState[1];
      var snapState = useState(null);
      var snap = snapState[0];
      var setSnap = snapState[1];
      var templatesState = useState([]);
      var templates = templatesState[0];
      var setTemplates = templatesState[1];
      var templateState = useState("software-team");
      var template = templateState[0];
      var setTemplate = templateState[1];
      var taskState = useState("");
      var task = taskState[0];
      var setTask = taskState[1];
      var steerState = useState("");
      var steer = steerState[0];
      var setSteer = steerState[1];
      var modeState = useState("meeting");
      var mode = modeState[0];
      var setMode = modeState[1];
      var errorState = useState(null);
      var error = errorState[0];
      var setError = errorState[1];
      var busyState = useState("");
      var busy = busyState[0];
      var setBusy = busyState[1];
      var loadingState = useState(true);
      var loading = loadingState[0];
      var setLoading = loadingState[1];
      var pickerOpenState = useState(false);
      var pickerOpen = pickerOpenState[0];
      var setPickerOpen = pickerOpenState[1];
      var modelSavingState = useState("");
      var modelSaving = modelSavingState[0];
      var setModelSaving = modelSavingState[1];
      var pollRef = useRef(null);

      var loadTemplates = useCallback(function () {
        return fetchJSON(API + "/templates")
          .then(function (data) {
            var list = (data && data.templates) || [];
            setTemplates(list);
          })
          .catch(function () { /* optional */ });
      }, []);

      var loadSnapshot = useCallback(function () {
        setError(null);
        var url = API + "/snapshot" + qs({ root: root || undefined });
        return fetchJSON(url)
          .then(function (data) {
            setSnap(data);
            setLoading(false);
            return data;
          })
          .catch(function (err) {
            setError(apiError(err));
            setLoading(false);
          });
      }, [root]);

      useEffect(function () {
        loadTemplates();
        loadSnapshot();
      }, [loadTemplates, loadSnapshot]);

      useEffect(function () {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(function () {
          if (!busy) loadSnapshot();
        }, (snap && (snap.busy || snap.phase === "running_round" || snap.current_seat)) ? 1500 : 8000);
        return function () {
          if (pollRef.current) clearInterval(pollRef.current);
        };
      }, [busy, loadSnapshot]);

      function applyRoot() {
        var next = (rootDraft || "").trim();
        setRoot(next);
        storeRoot(next);
      }

      function pickNativeDirectory() {
        var desktop = window.hermesDesktop;
        if (!desktop || typeof desktop.selectPaths !== "function") {
          return Promise.resolve(null);
        }
        return desktop
          .selectPaths({
            directories: true,
            multiple: false,
            defaultPath: rootDraft || root || undefined,
          })
          .then(function (paths) {
            if (Array.isArray(paths) && paths[0]) return String(paths[0]);
            return null;
          })
          .catch(function () {
            return null;
          });
      }

      function onBrowseRoot() {
        var desktop = window.hermesDesktop;
        if (desktop && typeof desktop.selectPaths === "function") {
          pickNativeDirectory().then(function (dir) {
            if (dir) {
              setRootDraft(dir);
              setRoot(dir);
              storeRoot(dir);
            }
            // cancel → no-op (do not open fallback over native cancel)
          });
          return;
        }
        setPickerOpen(true);
      }

      function setSeatModel(seatName, model) {
        if (!seatName) return;
        setModelSaving(seatName);
        setError(null);
        fetchJSON(API + "/seat/model", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            root: root || null,
            seat: seatName,
            model: model || "",
          }),
        })
          .then(function () {
            return loadSnapshot();
          })
          .catch(function (err) {
            setError(apiError(err));
          })
          .finally(function () {
            setModelSaving("");
          });
      }

      function runAction(label, method, path, body) {
        setBusy(label);
        setError(null);
        var opts = { method: method || "POST" };
        if (body !== undefined) {
          opts.headers = { "Content-Type": "application/json" };
          opts.body = JSON.stringify(body);
        }
        return fetchJSON(API + path, opts)
          .then(function (data) {
            if (data && data.snapshot) setSnap(data.snapshot);
            else return loadSnapshot();
            return data;
          })
          .catch(function (err) {
            setError(apiError(err));
          })
          .finally(function () {
            setBusy("");
          });
      }

      var session = snap && snap.session;
      var seats = (snap && snap.seats) || [];
      var modelOptions = (snap && snap.models) || [];
      var sessionBusy = !!(snap && snap.busy) || !!busy;
      var notConvened = snap && snap.ok === false && snap.error === "not_convened";
      var sessionStatus = session && session.status;
      var canRound = session && (session.mode === "meeting" || !session.mode) &&
        sessionStatus !== "concluded" && sessionStatus !== "stopped";

      return h("div", { className: "flex h-full min-h-0 flex-col gap-4 p-4" },
        h("div", { className: "flex flex-wrap items-end justify-between gap-3" },
          h("div", null,
            h("h1", { className: "text-xl font-semibold tracking-tight" }, "Council"),
            h("p", { className: "text-sm text-muted-foreground" },
              "Multi-seat deliberation — convene a table, start a meeting, steer rounds.")
          ),
          h("div", { className: "flex flex-wrap items-end gap-2" },
            h("div", { className: "flex flex-col gap-1" },
              h(Label, { className: "text-xs text-muted-foreground" }, "Project root"),
              h("div", { className: "flex gap-2" },
                h(Input, {
                  className: "h-8 w-72 font-mono text-xs",
                  placeholder: "empty = dashboard cwd (usually ~/.hermes)",
                  value: rootDraft,
                  onChange: function (e) { setRootDraft(e.target.value); },
                  onKeyDown: function (e) {
                    if (e.key === "Enter") applyRoot();
                  },
                }),
                h(Button, {
                  size: "sm",
                  variant: "outline",
                  type: "button",
                  onClick: onBrowseRoot,
                  title: "Browse for a project folder",
                }, "Browse"),
                h(Button, { size: "sm", variant: "secondary", onClick: applyRoot }, "Set")
              ),
              pickerOpen
                ? h(DirectoryPicker, {
                    initialPath: rootDraft || root || "",
                    onCancel: function () { setPickerOpen(false); },
                    onSelect: function (path) {
                      setRootDraft(path);
                      setRoot(path);
                      storeRoot(path);
                      setPickerOpen(false);
                    },
                  })
                : null
            ),
            h(Button, {
              size: "sm",
              variant: "outline",
              disabled: !!busy,
              onClick: function () { loadSnapshot(); },
            }, busy ? busy + "…" : "Refresh")
          )
        ),

        error
          ? h("div", {
              className: "rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive",
            }, error)
          : null,

        loading && !snap
          ? h("div", { className: "text-sm text-muted-foreground" }, "Loading council…")
          : null,

        notConvened
          ? h(Card, null,
              h(CardHeader, null,
                h(CardTitle, { className: "text-base" }, "No council at this root")
              ),
              h(CardContent, { className: "space-y-3" },
                h("p", { className: "text-sm text-muted-foreground" },
                  (snap && snap.message) ||
                  "Convene a template to create .council/ under the project root."),
                h("div", { className: "flex flex-wrap items-end gap-2" },
                  h("div", { className: "flex flex-col gap-1" },
                    h(Label, { className: "text-xs text-muted-foreground" }, "Template"),
                    h(Select, Object.assign({
                      value: template,
                      className: "h-8 w-56",
                    }, selectChangeHandler(setTemplate)),
                      (templates.length ? templates : [{ name: "software-team" }]).map(function (t) {
                        var id = t.id || t.name || t;
                        var label = t.label || t.name || id;
                        return h(SelectOption, { key: id, value: id }, label);
                      })
                    )
                  ),
                  h(Button, {
                    size: "sm",
                    disabled: !!busy,
                    onClick: function () {
                      runAction("Convening", "POST", "/convene", {
                        root: root || null,
                        template: template,
                        force: false,
                      });
                    },
                  }, busy === "Convening" ? "Convening…" : "Convene")
                ),
                h("p", { className: "font-mono text-[11px] text-muted-foreground" },
                  "root: " + ((snap && snap.root) || root || "(server cwd)"))
              )
            )
          : null,

        snap && snap.ok
          ? h(React.Fragment, null,
              h(Card, null,
                h(CardContent, { className: "flex flex-wrap items-start justify-between gap-3 pt-4" },
                  h("div", { className: "space-y-1" },
                    h("div", { className: "flex flex-wrap items-center gap-2" },
                      h("span", { className: "font-medium" },
                        (snap.council && (snap.council.name || snap.council.template)) || "Council"),
                      snap.chair
                        ? h(Badge, { variant: "outline" }, "chair: " + snap.chair)
                        : null,
                      session
                        ? h(Badge, { variant: "secondary" },
                            (session.mode || "meeting") + " · " + (session.status || "?"))
                        : h(Badge, { variant: "outline" }, "idle")
                    ),
                    snap.description
                      ? h("p", { className: "max-w-2xl text-sm text-muted-foreground" }, snap.description)
                      : null,
                    h("p", { className: "font-mono text-[11px] text-muted-foreground" },
                      snap.root + (snap.session_id ? (" · " + snap.session_id) : ""))
                  ),
                  h("div", { className: "flex flex-wrap gap-2" },
                    !session || sessionStatus === "concluded" || sessionStatus === "stopped"
                      ? h(React.Fragment, null,
                          h(Select, Object.assign({
                            value: mode,
                            className: "h-8 w-32",
                          }, selectChangeHandler(setMode)),
                            h(SelectOption, { value: "meeting" }, "Meeting"),
                            h(SelectOption, { value: "work" }, "Work")
                          ),
                          h(Input, {
                            className: "h-8 w-72 text-sm",
                            placeholder: "Task / decision for the table…",
                            value: task,
                            onChange: function (e) { setTask(e.target.value); },
                          }),
                          h(Button, {
                            size: "sm",
                            disabled: !!busy || !(task || "").trim(),
                            onClick: function () {
                              runAction("Starting", "POST", "/" + mode + "/start", {
                                root: root || null,
                                task: task.trim(),
                              }).then(function () { setTask(""); });
                            },
                          }, busy === "Starting" ? "Starting…" : ("Start " + mode))
                        )
                      : null,
                    session && sessionStatus !== "concluded" && sessionStatus !== "stopped"
                      ? h(Button, {
                          size: "sm",
                          variant: "outline",
                          disabled: !!busy,
                          onClick: function () {
                            if (!window.confirm("Cancel this session?")) return;
                            runAction("Canceling", "POST", "/session/cancel", {
                              root: root || null,
                              session_id: snap.session_id,
                            });
                          },
                        }, "Cancel session")
                      : null
                  )
                )
              ),

              h("div", { className: "flex min-h-[320px] flex-1 gap-3 overflow-x-auto pb-2" },
                seats.length
                  ? seats.map(function (seat) {
                      return h(SeatColumn, {
                        key: seat.name,
                        seat: seat,
                        modelOptions: modelOptions,
                        locked: sessionBusy,
                        saving: modelSaving === seat.name,
                        onModelChange: setSeatModel,
                      });
                    })
                  : h("div", { className: "text-sm text-muted-foreground" }, "No seats in roster.")
              ),

              canRound
                ? h(Card, null,
                    h(CardContent, { className: "space-y-3 pt-4" },
                      h(Label, { className: "text-xs text-muted-foreground" }, "Your steer (optional)"),
                      h(Textarea, {
                        className: "min-h-[72px] text-sm",
                        placeholder: "Guidance for the next round…",
                        value: steer,
                        onChange: function (e) { setSteer(e.target.value); },
                      }),
                      h("div", { className: "flex flex-wrap gap-2" },
                        h(Button, {
                          size: "sm",
                          disabled: !!busy,
                          onClick: function () {
                            runAction("Round", "POST", "/meeting/round", {
                              root: root || null,
                              session_id: snap.session_id,
                              user_steer: steer || "",
                            }).then(function () { setSteer(""); });
                          },
                        }, busy === "Round" ? "Running round…" : "Run round"),
                        h(Button, {
                          size: "sm",
                          variant: "secondary",
                          disabled: !!busy,
                          onClick: function () {
                            if (!window.confirm("Conclude this meeting and write the record?")) return;
                            runAction("Concluding", "POST", "/meeting/conclude", {
                              root: root || null,
                              session_id: snap.session_id,
                            });
                          },
                        }, busy === "Concluding" ? "Concluding…" : "Conclude meeting"),
                        session && session.mode === "work"
                          ? h(Button, {
                              size: "sm",
                              disabled: !!busy,
                              onClick: function () {
                                runAction("Tick", "POST", "/work/tick", {
                                  root: root || null,
                                  session_id: snap.session_id,
                                  user_steer: steer || "",
                                });
                              },
                            }, busy === "Tick" ? "Ticking…" : "Work tick")
                          : null
                      )
                    )
                  )
                : null,

              (snap.recent_sessions || []).length
                ? h("div", { className: "text-xs text-muted-foreground" },
                    h("div", { className: "mb-1 font-medium text-foreground/80" }, "Recent sessions"),
                    h("ul", { className: "space-y-1 font-mono" },
                      snap.recent_sessions.slice(0, 8).map(function (s) {
                        return h("li", { key: s.id },
                          (s.id || "?") + " · " + (s.mode || "?") + " · " + (s.status || "?"));
                      })
                    )
                  )
                : null
            )
          : null,

        h("div", { className: "mt-auto border-t border-border pt-2 text-[11px] text-muted-foreground" },
          "API " + API + " · set project root to a repo that should own .council/")
      );
    }

    if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
      window.__HERMES_PLUGINS__.register("council", CouncilPage);
    } else {
      console.warn("[council] __HERMES_PLUGINS__.register unavailable");
    }
  } catch (err) {
    console.error("[council] plugin bootstrap failed", err);
  }
})();
