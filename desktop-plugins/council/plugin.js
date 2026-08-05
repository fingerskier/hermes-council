/**
 * Council desktop plugin — seat columns + steer input.
 *
 * Install:
 *   mkdir -p "$HERMES_HOME/desktop-plugins/council"
 *   ln -sfn /path/to/hermes-council/desktop-plugins/council/plugin.js \
 *     "$HERMES_HOME/desktop-plugins/council/plugin.js"
 * Then ⌘K → "Reload desktop plugins" (and open Council from the sidebar).
 *
 * Backend: Python plugin `council` must be in plugins.enabled so
 * dashboard/plugin_api.py mounts at /api/plugins/council/.
 *
 * Plain ESM — jsx() only; no JSX syntax; only @hermes/plugin-sdk + react.
 */

import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  GlyphSpinner,
  Input,
  PALETTE_AREA,
  ROUTES_AREA,
  ScrollArea,
  SIDEBAR_NAV_AREA,
  STATUSBAR_AREAS,
  Separator,
  Textarea,
  Tip,
  cn,
  haptic,
  host,
  icons,
  profileColor,
  queryClient,
  useMutation,
  useQuery,
  useValue
} from '@hermes/plugin-sdk'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { jsx, jsxs, Fragment } from 'react/jsx-runtime'

const ID = 'council'
const QK = ['plugin', ID]

function useRest(ctx) {
  return useCallback(
    (path, opts) => ctx.rest(path, opts),
    [ctx]
  )
}

/** Native folder picker when running inside Hermes Desktop; null if cancelled/unavailable. */
async function pickDirectory(defaultPath) {
  try {
    const desktop =
      typeof window !== 'undefined' ? window.hermesDesktop : undefined
    if (!desktop || typeof desktop.selectPaths !== 'function') {
      return null
    }
    const paths = await desktop.selectPaths({
      directories: true,
      multiple: false,
      defaultPath: defaultPath || undefined
    })
    if (Array.isArray(paths) && paths[0]) {
      return String(paths[0])
    }
  } catch (err) {
    try {
      host.notifyError?.(err, 'Could not open folder picker')
    } catch (_) {
      /* ignore */
    }
  }
  return null
}

function statusTone(status) {
  if (!status) return 'text-(--ui-text-quaternary)'
  if (status === 'awaiting_user' || status === 'awaiting_round') return 'text-(--ui-accent)'
  if (status === 'concluded') return 'text-(--ui-text-tertiary)'
  if (status === 'stopped') return 'text-red-400'
  return 'text-(--ui-text-secondary)'
}

function SeatColumn({ seat, index, modelOptions, locked, saving, onModelChange }) {
  const color = profileColor(seat.name || String(index))
  const latest = seat.latest
  const empty = !latest || !(latest.content || '').trim()
  const errored = latest && latest.ok === false
  const history = seat.history || []
  const [settingsOpen, setSettingsOpen] = useState(false)
  const model = seat.model || ''
  const options = useMemo(() => {
    const list = Array.isArray(modelOptions) ? [...modelOptions] : []
    if (model && !list.includes(model)) list.unshift(model)
    return list
  }, [modelOptions, model])
  const disabled = Boolean(locked || saving)

  return jsxs('section', {
    className: cn(
      'flex min-w-[220px] max-w-[420px] flex-1 flex-col overflow-hidden rounded-md border',
      'border-(--ui-stroke-secondary)'
    ),
    style: { borderTopColor: color, borderTopWidth: 2 },
    children: [
      jsxs('header', {
        className: 'flex items-start gap-2 border-b border-(--ui-stroke-secondary) px-3 py-2',
        children: [
          jsx('div', {
            className: 'mt-1 h-2 w-2 shrink-0 rounded-full',
            style: { background: color }
          }),
          jsxs('div', {
            className: 'min-w-0 flex-1',
            children: [
              jsxs('div', {
                className: 'flex items-center gap-1.5',
                children: [
                  jsx('div', {
                    className: 'truncate text-sm font-medium',
                    children: seat.title || seat.name
                  }),
                  seat.chair
                    ? jsx(Badge, { variant: 'secondary', children: 'chair' })
                    : null,
                  errored
                    ? jsx(Badge, { variant: 'secondary', children: 'error' })
                    : null
                ]
              }),
              seat.voice
                ? jsx('div', {
                    className: 'truncate text-[0.6875rem] text-(--ui-text-quaternary)',
                    children: seat.voice
                  })
                : null,
              jsx('div', {
                className: 'truncate text-[0.625rem] text-(--ui-text-quaternary) font-mono',
                title: model || 'host default model',
                children: model || 'model: host default'
              })
            ]
          }),
          jsx(Tip, {
            label: disabled
              ? 'Model locked while this council is working'
              : 'Seat model settings',
            children: jsx(Button, {
              size: 'sm',
              variant: 'ghost',
              type: 'button',
              disabled: disabled && !settingsOpen,
              className: 'h-7 w-7 shrink-0 p-0',
              onClick: () => {
                if (disabled) return
                setSettingsOpen(v => !v)
              },
              children: icons.Settings
                ? jsx(icons.Settings, { className: 'h-3.5 w-3.5' })
                : '⚙'
            })
          })
        ]
      }),
      settingsOpen
        ? jsxs('div', {
            className:
              'flex flex-col gap-1.5 border-b border-(--ui-stroke-secondary) bg-(--ui-bg-secondary,transparent) px-3 py-2',
            children: [
              jsx('div', {
                className: 'text-[0.6875rem] uppercase tracking-wide text-(--ui-text-quaternary)',
                children: 'Model'
              }),
              jsxs('select', {
                className:
                  'h-8 w-full rounded border border-(--ui-stroke-secondary) bg-transparent px-2 text-xs font-mono',
                value: model,
                disabled,
                onChange: e => {
                  const next = e.target.value
                  if (typeof onModelChange === 'function') {
                    onModelChange(seat.name, next)
                  }
                },
                children: [
                  jsx('option', { value: '', children: 'Host default' }, '__default'),
                  ...options.map(m =>
                    jsx('option', { value: m, children: m }, m)
                  )
                ]
              }),
              disabled
                ? jsx('div', {
                    className: 'text-[0.625rem] text-(--ui-text-quaternary)',
                    children: 'Disabled while a round / work turn is running.'
                  })
                : jsx('div', {
                    className: 'text-[0.625rem] text-(--ui-text-quaternary)',
                    children: 'Saved to .council/seats/' + (seat.name || 'seat') + '.md'
                  })
            ]
          })
        : null,
      jsx(ScrollArea, {
        className: 'min-h-0 flex-1',
        children: jsxs('div', {
          className: 'flex flex-col gap-3 p-3 text-sm',
          children: [
            empty
              ? jsx('div', {
                  className: 'text-(--ui-text-quaternary) text-xs italic',
                  children: errored
                    ? latest.error || 'Seat returned empty / error'
                    : 'No contribution yet — run a round.'
                })
              : jsx('div', {
                  className: cn(
                    'whitespace-pre-wrap break-words leading-relaxed',
                    errored && 'text-red-300'
                  ),
                  children: latest.content
                }),
            history.length > 1
              ? jsxs(Fragment, {
                  children: [
                    jsx(Separator, {}),
                    jsx('div', {
                      className:
                        'text-[0.6875rem] uppercase tracking-wide text-(--ui-text-quaternary)',
                      children: 'Earlier turns'
                    }),
                    ...history
                      .slice(0, -1)
                      .reverse()
                      .slice(0, 4)
                      .map(h =>
                        jsxs(
                          'div',
                          {
                            className: 'rounded border border-(--ui-stroke-secondary) p-2',
                            children: [
                              jsx('div', {
                                className:
                                  'mb-1 text-[0.6875rem] text-(--ui-text-quaternary)',
                                children: `Turn ${h.turn}${h.stamp ? ' · ' + h.stamp : ''}`
                              }),
                              jsx('div', {
                                className:
                                  'line-clamp-6 whitespace-pre-wrap text-xs text-(--ui-text-secondary)',
                                children: h.content || ''
                              })
                            ]
                          },
                          String(h.turn)
                        )
                      )
                  ]
                })
              : null,
            latest && latest.via
              ? jsx('div', {
                  className: 'text-[0.625rem] text-(--ui-text-quaternary)',
                  children: latest.via
                })
              : null
          ]
        })
      })
    ]
  })
}

function CouncilPage({ ctx }) {
  const rest = useRest(ctx)
  const cwd = useValue(host.state.cwd)
  const [root, setRoot] = useState(() => cwd || '')
  const [sessionId, setSessionId] = useState('')
  const [steer, setSteer] = useState('')
  const [taskDraft, setTaskDraft] = useState('')
  const [newMode, setNewMode] = useState('meeting')
  const [template, setTemplate] = useState('software-team')

  useEffect(() => {
    if (cwd && !root) setRoot(cwd)
  }, [cwd, root])

  const qKey = [...QK, 'snapshot', root || '', sessionId || '']

  const snapshotQuery = useQuery({
    queryKey: qKey,
    queryFn: async () => {
      const qs = new URLSearchParams()
      if (root) qs.set('root', root)
      if (sessionId) qs.set('session_id', sessionId)
      return rest(`/snapshot?${qs.toString()}`)
    },
    refetchInterval: 4000,
    retry: 1
  })

  const templatesQuery = useQuery({
    queryKey: [...QK, 'templates'],
    queryFn: () => rest('/templates'),
    staleTime: 60_000
  })

  const snap = snapshotQuery.data
  const seats = (snap && snap.seats) || []
  const modelOptions = (snap && snap.models) || []
  const session = snap && snap.session
  const activeId = (snap && snap.session_id) || sessionId || ''
  const busy = !!(snap && snap.busy)
  const [modelSaving, setModelSaving] = useState('')

  useEffect(() => {
    if (snap && snap.session_id && snap.session_id !== sessionId) {
      // Keep local selection in sync when auto-picking latest session
      if (!sessionId) setSessionId(snap.session_id)
    }
  }, [snap, sessionId])

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: QK })
  }, [])

  const setSeatModel = useCallback(
    async (seatName, model) => {
      if (!seatName) return
      setModelSaving(seatName)
      try {
        const data = await rest('/seat/model', {
          method: 'POST',
          body: { root: root || null, seat: seatName, model: model || '' },
          timeoutMs: 20_000
        })
        haptic('tap')
        host.notify({
          kind: data && data.ok === false ? 'warning' : 'success',
          message:
            (data && data.message) ||
            `Model for ${seatName}: ${model || 'host default'}`
        })
        invalidate()
      } catch (err) {
        host.notifyError(err, `Could not set model for ${seatName}`)
      } finally {
        setModelSaving('')
      }
    },
    [rest, root, invalidate]
  )

  const conveneMut = useMutation({
    mutationFn: () =>
      rest('/convene', {
        method: 'POST',
        body: { root, template, force: false },
        timeoutMs: 30_000
      }),
    onSuccess: data => {
      haptic('tap')
      host.notify({
        kind: data && data.ok ? 'success' : 'warning',
        message: (data && data.message) || 'Convene finished'
      })
      invalidate()
    },
    onError: err => host.notifyError(err, 'Convene failed')
  })

  const startMut = useMutation({
    mutationFn: () =>
      rest(`/${newMode}/start`, {
        method: 'POST',
        body: { root, task: taskDraft.trim() },
        timeoutMs: 30_000
      }),
    onSuccess: data => {
      haptic('tap')
      if (data && data.ok === false) {
        host.notify({ kind: 'warning', message: data.message || `Could not start ${newMode}` })
        return
      }
      if (data && data.session_id) {
        setSessionId(data.session_id)
        setTaskDraft('')
      }
      host.notify({ kind: 'success', message: (data && data.message) || `${newMode} started` })
      invalidate()
    },
    onError: err => host.notifyError(err, `Start ${newMode} failed`)
  })

  const roundMut = useMutation({
    mutationFn: () =>
      rest('/meeting/round', {
        method: 'POST',
        body: {
          root,
          session_id: activeId,
          user_steer: steer
        },
        timeoutMs: 600_000
      }),
    onSuccess: data => {
      haptic('tap')
      setSteer('')
      if (data && data.snapshot) {
        queryClient.setQueryData(qKey, data.snapshot)
      }
      const failed = (data && data.failed_seats) || []
      host.notify({
        kind: failed.length ? 'warning' : 'success',
        message:
          (data && data.message) ||
          (failed.length ? `Round done with failures: ${failed.join(', ')}` : 'Round complete')
      })
      invalidate()
    },
    onError: err => host.notifyError(err, 'Round failed')
  })

  const concludeMut = useMutation({
    mutationFn: () =>
      rest(session && session.mode === 'work' ? '/work/conclude' : '/meeting/conclude', {
        method: 'POST',
        body: { root, session_id: activeId },
        timeoutMs: 300_000
      }),
    onSuccess: data => {
      haptic('tap')
      host.notify({
        kind: 'success',
        message: (data && data.message) || 'Meeting concluded'
      })
      invalidate()
    },
    onError: err => host.notifyError(err, 'Conclude failed')
  })

  const cancelMut = useMutation({
    mutationFn: () =>
      rest('/session/cancel', {
        method: 'POST',
        body: { root, session_id: activeId },
        timeoutMs: 30_000
      }),
    onSuccess: data => {
      haptic('tap')
      host.notify({ kind: 'success', message: (data && data.message) || 'Session cancelled' })
      invalidate()
    },
    onError: err => host.notifyError(err, 'Cancel failed')
  })

  const workTickMut = useMutation({
    mutationFn: () =>
      rest('/work/tick', {
        method: 'POST',
        body: { root, session_id: activeId },
        timeoutMs: 600_000
      }),
    onSuccess: data => {
      haptic('tap')
      if (data && data.snapshot) queryClient.setQueryData(qKey, data.snapshot)
      host.notify({
        kind: data && data.ok === false ? 'warning' : 'success',
        message: (data && data.message) || 'Work turn complete'
      })
      invalidate()
    },
    onError: err => host.notifyError(err, 'Work turn failed')
  })

  const acting =
    conveneMut.isPending ||
    startMut.isPending ||
    roundMut.isPending ||
    concludeMut.isPending ||
    cancelMut.isPending ||
    workTickMut.isPending

  const recent = (snap && snap.recent_sessions) || []
  const templates = (templatesQuery.data && templatesQuery.data.templates) || []

  const headerStatus = session
    ? `${session.mode || '—'} · ${session.status || '—'}`
    : snap && snap.ok === false
      ? snap.error || 'not ready'
      : 'no session'
  const sessionFinished =
    !session || session.status === 'concluded' || session.status === 'stopped'

  const body = (() => {
    if (snapshotQuery.isLoading && !snap) {
      return jsxs('div', {
        className: 'flex h-full items-center justify-center gap-2 text-(--ui-text-tertiary)',
        children: [jsx(GlyphSpinner, {}), ' Loading council…']
      })
    }
    if (snapshotQuery.isError && !snap) {
      return jsx(ErrorState, {
        title: 'Council API unavailable',
        description:
          'Is the council Python plugin enabled (plugins.enabled) and the gateway restarted so dashboard/plugin_api.py is mounted?',
        action: jsx(Button, {
          size: 'sm',
          onClick: () => snapshotQuery.refetch(),
          children: 'Retry'
        })
      })
    }
    if (snap && snap.ok === false && snap.error === 'not_convened') {
      return jsx(EmptyState, {
        icon: icons.Users,
        title: 'No council in this project',
        description: `Convene a template under ${root || 'the project root'} to stamp .council/ seats.`,
        action: jsxs('div', {
          className: 'flex flex-wrap items-center gap-2',
          children: [
            jsx('select', {
              className:
                'h-8 rounded border border-(--ui-stroke-secondary) bg-transparent px-2 text-sm',
              value: template,
              onChange: e => setTemplate(e.target.value),
              children: (templates.length
                ? templates.map(t =>
                    jsx('option', {
                      value: t.name || t.id || t,
                      children: t.name || t.id || String(t)
                    }, t.name || t.id || String(t))
                  )
                : ['software-team', 'solo-founder', 'c-suite'].map(n =>
                    jsx('option', { value: n, children: n }, n)
                  ))
            }),
            jsx(Button, {
              size: 'sm',
              disabled: acting || !root,
              onClick: () => conveneMut.mutate(),
              children: conveneMut.isPending ? 'Convening…' : 'Convene'
            })
          ]
        })
      })
    }

    return jsxs('div', {
      className: 'flex min-h-0 flex-1 flex-col gap-3',
      children: [
        // Seat columns
        seats.length
          ? jsx('div', {
              className: 'flex min-h-0 flex-1 gap-2 overflow-x-auto pb-1',
              children: seats.map((seat, i) =>
                jsx(
                  SeatColumn,
                  {
                    seat,
                    index: i,
                    modelOptions,
                    locked: busy || acting,
                    saving: modelSaving === seat.name,
                    onModelChange: setSeatModel
                  },
                  seat.name || String(i)
                )
              )
            })
          : jsx(EmptyState, {
              title: 'No seats',
              description: 'Council roster is empty.'
            }),

        // Steers strip
        snap && snap.steers && snap.steers.length
          ? jsxs('div', {
              className: 'shrink-0 rounded-md border border-(--ui-stroke-secondary) p-2',
              children: [
                jsx('div', {
                  className: 'mb-1 text-[0.6875rem] uppercase tracking-wide text-(--ui-text-quaternary)',
                  children: 'Recent steers'
                }),
                jsx('div', {
                  className: 'flex max-h-24 flex-col gap-1 overflow-y-auto',
                  children: snap.steers
                    .slice()
                    .reverse()
                    .map(s =>
                      jsx('div', {
                        key: String(s.turn),
                        className: 'truncate text-xs text-(--ui-text-secondary)',
                        children: `T${s.turn}: ${(s.content || '').replace(/\s+/g, ' ').slice(0, 160)}`
                      })
                    )
                })
              ]
            })
          : null,

        // Composer: steer + actions
        jsxs('div', {
          className:
            'shrink-0 rounded-md border border-(--ui-stroke-secondary) p-3 flex flex-col gap-2',
          children: [
            sessionFinished
              ? jsxs('div', {
                  className: 'flex flex-col gap-2 sm:flex-row sm:items-end',
                  children: [
                    jsxs('div', {
                      className: 'shrink-0',
                      children: [
                        jsx('div', {
                          className: 'mb-1 text-[0.6875rem] text-(--ui-text-quaternary)',
                          children: 'Session type'
                        }),
                        jsxs('select', {
                          className:
                            'h-8 rounded border border-(--ui-stroke-secondary) bg-transparent px-2 text-sm',
                          value: newMode,
                          onChange: e => setNewMode(e.target.value),
                          children: [
                            jsx('option', { value: 'meeting', children: 'Meeting' }),
                            jsx('option', { value: 'work', children: 'Work session' })
                          ]
                        })
                      ]
                    }),
                    jsxs('div', {
                      className: 'min-w-0 flex-1',
                      children: [
                        jsx('div', {
                          className: 'mb-1 text-[0.6875rem] text-(--ui-text-quaternary)',
                          children: `New ${newMode} task`
                        }),
                        jsx(Input, {
                          value: taskDraft,
                          placeholder: 'What should the council deliberate?',
                          onChange: e => setTaskDraft(e.target.value),
                          onKeyDown: e => {
                            if (e.key === 'Enter' && taskDraft.trim() && !acting) {
                              startMut.mutate()
                            }
                          }
                        })
                      ]
                    }),
                    jsx(Button, {
                      disabled: acting || !taskDraft.trim() || !root,
                      onClick: () => startMut.mutate(),
                      children: startMut.isPending
                        ? 'Starting…'
                        : newMode === 'work'
                          ? 'Start work session'
                          : 'Start meeting'
                    })
                  ]
                })
              : jsxs(Fragment, {
                  children: [
                    session.mode === 'meeting'
                      ? jsxs(Fragment, {
                          children: [
                            jsx('div', {
                              className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                              children: 'Your steer / feedback (injected before the next round)'
                            }),
                            jsx(Textarea, {
                              value: steer,
                              rows: 3,
                              placeholder:
                                'Optional guidance for the seats… (leave empty to just run another round)',
                              onChange: e => setSteer(e.target.value),
                              disabled: acting || roundMut.isPending
                            })
                          ]
                        })
                      : jsx('div', {
                          className: 'text-xs text-(--ui-text-secondary)',
                          children:
                            'Advance one routed work turn at a time. Conclude synthesizes and commits the worktree; cancel leaves it untouched.'
                        }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2',
                      children: [
                        session.mode === 'meeting'
                          ? jsx(Button, {
                              disabled: acting || !activeId,
                              onClick: () => roundMut.mutate(),
                              children: roundMut.isPending
                                ? jsxs('span', {
                                    className: 'inline-flex items-center gap-2',
                                    children: [jsx(GlyphSpinner, {}), ' Running round…']
                                  })
                                : steer.trim()
                                  ? 'Steer + round'
                                  : 'Run round'
                            })
                          : jsx(Button, {
                              disabled: acting || !activeId,
                              onClick: () => workTickMut.mutate(),
                              children: workTickMut.isPending ? 'Running work turn…' : 'Run work turn'
                            }),
                        jsx(Button, {
                          variant: 'ghost',
                          disabled: acting || !activeId,
                          onClick: () => {
                            if (
                              typeof window !== 'undefined' &&
                              window.confirm &&
                              !window.confirm(
                                'Cancel this session without synthesis or a record? Worktree changes will be left untouched.'
                              )
                            ) {
                              return
                            }
                            cancelMut.mutate()
                          },
                          children: cancelMut.isPending ? 'Cancelling…' : 'Cancel'
                        }),
                        jsx(Button, {
                          variant: 'secondary',
                          disabled: acting || !activeId,
                          onClick: () => {
                            if (
                              typeof window !== 'undefined' &&
                              window.confirm &&
                              !window.confirm(
                                session.mode === 'work'
                                  ? 'Conclude this work session, synthesize, and commit its worktree?'
                                  : 'Conclude this meeting and write the record?'
                              )
                            ) {
                              return
                            }
                            concludeMut.mutate()
                          },
                          children: concludeMut.isPending
                            ? 'Concluding…'
                            : session.mode === 'work'
                              ? 'Conclude work'
                              : 'Conclude meeting'
                        }),
                        session && session.task
                          ? jsx('span', {
                              className: 'text-xs text-(--ui-text-tertiary) truncate max-w-[40%]',
                              children: session.task
                            })
                          : null
                      ]
                    })
                  ]
                })
          ]
        })
      ]
    })
  })()

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col gap-3 p-3',
    'data-slot': 'council-page',
    children: [
      // Top bar
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 shrink-0',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 flex-1 items-center gap-2',
            children: [
              jsx(icons.Users, {
                className: 'h-4 w-4 shrink-0 text-(--ui-text-tertiary)'
              }),
              jsx('div', {
                className: 'text-sm font-medium shrink-0',
                children: 'Council'
              }),
              snap && snap.council
                ? jsx(Badge, { variant: 'secondary', children: snap.council })
                : null,
              jsx('span', {
                className: cn('text-xs', statusTone(session && session.status)),
                children: headerStatus
              }),
              busy || acting
                ? jsx(GlyphSpinner, { className: 'h-3.5 w-3.5' })
                : null
            ]
          }),
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              jsx(Tip, {
                label: 'Project root containing .council/',
                children: jsxs('div', {
                  className: 'flex items-center gap-1',
                  children: [
                    jsx(Input, {
                      className: 'h-8 w-[min(320px,36vw)] text-xs font-mono',
                      value: root,
                      placeholder: 'Project root',
                      onChange: e => setRoot(e.target.value)
                    }),
                    jsx(Button, {
                      size: 'sm',
                      variant: 'secondary',
                      type: 'button',
                      title: 'Browse for project folder',
                      onClick: () => {
                        void (async () => {
                          const dir = await pickDirectory(root || cwd || undefined)
                          if (dir) {
                            setRoot(dir)
                            haptic('tap')
                            host.notify?.({
                              kind: 'info',
                              message: `Council project root: ${dir}`
                            })
                          } else if (
                            typeof window !== 'undefined' &&
                            !(window.hermesDesktop && window.hermesDesktop.selectPaths)
                          ) {
                            host.notify?.({
                              kind: 'warning',
                              message:
                                'Folder picker needs Hermes Desktop. Type an absolute path, or use the active workspace cwd.'
                            })
                          }
                        })()
                      },
                      children: jsxs('span', {
                        className: 'inline-flex items-center gap-1',
                        children: [
                          icons.FolderOpen
                            ? jsx(icons.FolderOpen, { className: 'h-3.5 w-3.5' })
                            : null,
                          'Browse'
                        ]
                      })
                    })
                  ]
                })
              }),
              jsx('select', {
                className:
                  'h-8 max-w-[220px] rounded border border-(--ui-stroke-secondary) bg-transparent px-2 text-xs',
                value: activeId,
                onChange: e => setSessionId(e.target.value),
                children: [
                  jsx('option', { value: '', children: 'Latest session' }, ''),
                  ...recent.map(s =>
                    jsx(
                      'option',
                      {
                        value: s.id,
                        children: `${(s.id || '').slice(0, 18)}… · ${s.status || ''} · ${(s.task || '').slice(0, 28)}`
                      },
                      s.id
                    )
                  )
                ]
              }),
              jsx(Button, {
                size: 'sm',
                variant: 'ghost',
                disabled: snapshotQuery.isFetching,
                onClick: () => snapshotQuery.refetch(),
                children: 'Refresh'
              })
            ]
          })
        ]
      }),

      session && session.task
        ? jsx('div', {
            className: 'shrink-0 text-xs text-(--ui-text-secondary)',
            children: jsxs(Fragment, {
              children: [
                jsx('span', {
                  className: 'text-(--ui-text-quaternary)',
                  children: 'Task · '
                }),
                session.task
              ]
            })
          })
        : null,

      body
    ]
  })
}

function CouncilEditorPage({ ctx }) {
  const rest = useRest(ctx)
  const cwd = useValue(host.state.cwd)
  const root = cwd || ''
  const [draft, setDraft] = useState(null)
  const [selectedName, setSelectedName] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saveError, setSaveError] = useState('')
  const qKey = [...QK, 'editor', root]
  const editorQuery = useQuery({
    queryKey: qKey,
    enabled: Boolean(root),
    queryFn: () => rest(`/editor?root=${encodeURIComponent(root)}`),
    staleTime: 5_000
  })

  useEffect(() => {
    if (!editorQuery.data || dirty) return
    const next = {
      ...editorQuery.data,
      models: [...(editorQuery.data.models || [])],
      seats: (editorQuery.data.seats || []).map(seat => ({ ...seat }))
    }
    setDraft(next)
    setSelectedName(current =>
      next.seats.some(seat => seat.name === current)
        ? current
        : next.seats[0]
          ? next.seats[0].name
          : ''
    )
  }, [editorQuery.data, dirty])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const guard = event => {
      if (!dirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [dirty])

  const saveMut = useMutation({
    mutationFn: () =>
      rest('/editor/save', {
        method: 'POST',
        body: {
          root,
          seats: draft ? draft.seats : [],
          models: draft ? draft.models : []
        },
        timeoutMs: 30_000
      }),
    onSuccess: data => {
      haptic('tap')
      setSaveError('')
      setDirty(false)
      setDraft({
        ...data,
        models: [...(data.models || [])],
        seats: (data.seats || []).map(seat => ({ ...seat }))
      })
      queryClient.setQueryData(qKey, data)
      host.notify({ kind: 'success', message: data.message || 'Council saved' })
    },
    onError: error => {
      setSaveError(error && error.message ? error.message : String(error))
      host.notifyError(error, 'Council save failed')
    }
  })

  const selected =
    draft && draft.seats
      ? draft.seats.find(seat => seat.name === selectedName) || null
      : null

  const updateSelected = patch => {
    if (!draft || !selected) return
    setDraft({
      ...draft,
      seats: draft.seats.map(seat =>
        seat.name === selected.name ? { ...seat, ...patch } : seat
      )
    })
    setDirty(true)
    setSaveError('')
  }

  const moveSelected = delta => {
    if (!draft || !selected) return
    const index = draft.seats.findIndex(seat => seat.name === selected.name)
    const target = index + delta
    if (index < 0 || target < 0 || target >= draft.seats.length) return
    const seats = [...draft.seats]
    const [moved] = seats.splice(index, 1)
    seats.splice(target, 0, moved)
    setDraft({ ...draft, seats })
    setDirty(true)
    setSaveError('')
  }

  const leaveEditor = () => {
    if (
      dirty &&
      typeof window !== 'undefined' &&
      window.confirm &&
      !window.confirm('Discard unsaved council changes?')
    ) {
      return
    }
    host.navigate('/council')
  }

  let body
  if (!root) {
    body = jsx(EmptyState, {
      title: 'Open a project first',
      description: 'The Council Editor saves the .council directory in the current project.'
    })
  } else if (editorQuery.isLoading && !draft) {
    body = jsxs('div', {
      className: 'flex flex-1 items-center justify-center gap-2 text-sm text-(--ui-text-tertiary)',
      children: [jsx(GlyphSpinner, {}), ' Loading council editor…']
    })
  } else if (editorQuery.isError && !draft) {
    body = jsx(ErrorState, {
      title: 'Council editor unavailable',
      description: String(editorQuery.error || 'Convene a council first.'),
      action: jsx(Button, { onClick: () => editorQuery.refetch(), children: 'Retry' })
    })
  } else if (!draft || !draft.seats || draft.seats.length === 0) {
    body = jsx(EmptyState, {
      title: 'No editable seats',
      description: 'Convene a council first, then return to edit it.'
    })
  } else {
    const modelOptions = [...(draft.models || [])]
    if (selected && selected.model && !modelOptions.includes(selected.model)) {
      modelOptions.push(selected.model)
    }
    body = jsxs('div', {
      className: 'flex min-h-0 flex-1 flex-col gap-3 p-3 md:flex-row',
      children: [
        jsxs('section', {
          className:
            'flex w-full shrink-0 flex-col rounded-md border border-(--ui-stroke-secondary) md:w-72',
          children: [
            jsxs('div', {
              className: 'flex items-center justify-between border-b border-(--ui-stroke-secondary) p-3',
              children: [
                jsxs('div', {
                  children: [
                    jsx('div', { className: 'text-sm font-semibold', children: 'Speaking order' }),
                    jsx('div', {
                      className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                      children: 'Pinned when a session starts.'
                    })
                  ]
                }),
                jsxs('div', {
                  className: 'flex gap-1',
                  children: [
                    jsx(Button, {
                      variant: 'ghost',
                      size: 'sm',
                      disabled: !selected || draft.seats[0].name === selected.name,
                      onClick: () => moveSelected(-1),
                      title: 'Move seat up',
                      children: '↑'
                    }),
                    jsx(Button, {
                      variant: 'ghost',
                      size: 'sm',
                      disabled:
                        !selected || draft.seats[draft.seats.length - 1].name === selected.name,
                      onClick: () => moveSelected(1),
                      title: 'Move seat down',
                      children: '↓'
                    })
                  ]
                })
              ]
            }),
            jsx(ScrollArea, {
              className: 'min-h-0 flex-1',
              children: jsx('div', {
                className: 'flex flex-col gap-1 p-2',
                children: draft.seats.map((seat, index) =>
                  jsxs('button', {
                    type: 'button',
                    className: cn(
                      'rounded-md border px-3 py-2 text-left transition-colors',
                      seat.name === selectedName
                        ? 'border-(--ui-accent) bg-(--ui-bg-secondary)'
                        : 'border-transparent hover:bg-(--ui-bg-secondary)'
                    ),
                    onClick: () => setSelectedName(seat.name),
                    children: [
                      jsx('div', {
                        className: 'truncate text-sm font-medium',
                        children: `${index + 1}. ${seat.title}`
                      }),
                      jsx('div', {
                        className: 'truncate text-[0.6875rem] text-(--ui-text-quaternary)',
                        children: seat.name
                      })
                    ]
                  }, seat.name)
                )
              })
            })
          ]
        }),
        selected
          ? jsxs('section', {
              className:
                'flex min-h-0 min-w-0 flex-1 flex-col gap-3 rounded-md border border-(--ui-stroke-secondary) p-3',
              children: [
                jsxs('div', {
                  className: 'flex flex-wrap items-center justify-between gap-2',
                  children: [
                    jsxs('div', {
                      children: [
                        jsx('div', { className: 'text-base font-semibold', children: selected.title }),
                        jsx('div', {
                          className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                          children: `${selected.name} · ${selected.voice || 'neutral voice'}`
                        })
                      ]
                    }),
                    selected.content_hash
                      ? jsx('span', {
                          className: 'font-mono text-[0.625rem] text-(--ui-text-quaternary)',
                          title: selected.content_hash,
                          children: `sha256:${selected.content_hash.slice(0, 12)}`
                        })
                      : null
                  ]
                }),
                jsxs('div', {
                  className: 'grid gap-2 lg:grid-cols-2',
                  children: [
                    jsxs('label', {
                      className: 'flex flex-col gap-1',
                      children: [
                        jsx('span', {
                          className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                          children: 'Configured model'
                        }),
                        jsx('select', {
                          className:
                            'h-8 rounded border border-(--ui-stroke-secondary) bg-transparent px-2 text-sm',
                          value: selected.model || '',
                          onChange: event => updateSelected({ model: event.target.value }),
                          children: [
                            jsx('option', { value: '', children: 'Host default' }),
                            ...modelOptions.map(model =>
                              jsx('option', {
                                value: model,
                                children:
                                  draft.models && draft.models.includes(model)
                                    ? model
                                    : `${model} (unlisted)`
                              }, model)
                            )
                          ]
                        })
                      ]
                    }),
                    jsxs('label', {
                      className: 'flex flex-col gap-1',
                      children: [
                        jsx('span', {
                          className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                          children: 'Custom or unlisted model'
                        }),
                        jsx(Input, {
                          value: selected.model || '',
                          maxLength: 128,
                          placeholder: 'letters, digits, dot, underscore, colon, hyphen',
                          onChange: event => updateSelected({ model: event.target.value })
                        })
                      ]
                    })
                  ]
                }),
                jsxs('label', {
                  className: 'flex min-h-0 flex-1 flex-col gap-1',
                  children: [
                    jsx('span', {
                      className: 'text-[0.6875rem] text-(--ui-text-quaternary)',
                      children: 'Persona (Markdown)'
                    }),
                    jsx(Textarea, {
                      className: 'min-h-80 flex-1 font-mono text-xs',
                      value: selected.persona || '',
                      placeholder: 'Describe this seat’s responsibilities, priorities, and review style…',
                      onChange: event => updateSelected({ persona: event.target.value })
                    })
                  ]
                }),
                saveError
                  ? jsx('div', {
                      className: 'rounded border border-red-500/40 bg-red-500/10 p-2 text-xs text-red-400',
                      role: 'alert',
                      children: `Save failed: ${saveError}. Your edits are still unsaved.`
                    })
                  : null,
                draft.warnings && draft.warnings.length
                  ? jsx('div', {
                      className: 'text-[0.6875rem] text-amber-400',
                      children: draft.warnings.join(' ')
                    })
                  : null
              ]
            })
          : null
      ]
    })
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col bg-(--ui-bg-primary) p-3',
    children: [
      jsxs('header', {
        className: 'mb-3 flex shrink-0 items-center gap-2',
        children: [
          jsx(Button, { variant: 'ghost', size: 'sm', onClick: leaveEditor, children: '← Council' }),
          jsxs('div', {
            className: 'min-w-0 flex-1',
            children: [
              jsx('div', { className: 'text-sm font-semibold', children: 'Council Editor' }),
              jsx('div', {
                className: 'truncate text-[0.6875rem] text-(--ui-text-quaternary)',
                title: root,
                children: root || 'No project root'
              })
            ]
          }),
          dirty ? jsx(Badge, { variant: 'secondary', children: 'Unsaved changes' }) : null,
          jsx(Button, {
            disabled: !dirty || saveMut.isPending || !draft,
            onClick: () => saveMut.mutate(),
            children: saveMut.isPending ? 'Saving…' : 'Save council'
          })
        ]
      }),
      body
    ]
  })
}

function CouncilChip({ ctx }) {
  const rest = useRest(ctx)
  const cwd = useValue(host.state.cwd)
  const q = useQuery({
    queryKey: [...QK, 'chip', cwd || ''],
    queryFn: async () => {
      const qs = new URLSearchParams()
      if (cwd) qs.set('root', cwd)
      return rest(`/snapshot?${qs.toString()}`)
    },
    refetchInterval: 12_000,
    retry: 0
  })
  const snap = q.data
  const n = (snap && snap.seats && snap.seats.length) || 0
  const st = snap && snap.session && snap.session.status
  const label = st ? `council:${st}` : n ? `council:${n}` : 'council'

  return jsx(Tip, {
    label: 'Open Council seat board',
    children: jsx('button', {
      type: 'button',
      className: cn(
        'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] transition-colors',
        'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      ),
      onClick: () => {
        haptic('tap')
        host.navigate('/council')
      },
      children: label
    })
  })
}

export default {
  id: ID,
  name: 'Council',
  defaultEnabled: true,
  register(ctx) {
    // Live invalidate when gateway events fire (best-effort)
    try {
      ctx.socket('/events', () => {
        queryClient.invalidateQueries({ queryKey: QK })
      })
    } catch (_) {
      /* socket optional */
    }

    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: '/council' },
        render: () => jsx(CouncilPage, { ctx })
      },
      {
        id: 'editor-page',
        area: ROUTES_AREA,
        data: { path: '/council/editor' },
        render: () => jsx(CouncilEditorPage, { ctx })
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: '/council', label: 'Council', codicon: 'organization' }
      },
      {
        id: 'editor-nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: '/council/editor', label: 'Council Editor', codicon: 'edit' }
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: 'council.open',
          label: 'Open Council',
          keywords: ['council', 'seats', 'meeting', 'steer'],
          run: () => host.navigate('/council')
        }
      },
      {
        id: 'open-editor',
        area: PALETTE_AREA,
        data: {
          id: 'council.editor.open',
          label: 'Open Council Editor',
          keywords: ['council', 'seats', 'persona', 'model', 'order'],
          run: () => host.navigate('/council/editor')
        }
      },
      {
        id: 'chip',
        area: STATUSBAR_AREAS.right,
        order: 125,
        render: () => jsx(CouncilChip, { ctx })
      }
    ])
  }
}
