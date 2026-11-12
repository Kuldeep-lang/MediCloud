import { Activity, Boxes, CheckCircle2, Clock, Database, ExternalLink, Server, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { errorMessage } from '../api/client'
import { systemApi } from '../api/endpoints'
import { ChartCard } from '../components/charts/ChartCard'
import { axisProps, gridProps, legendProps, SERIES, tooltipProps } from '../components/charts/chartTheme'
import { Badge, PageHeader } from '../components/ui/primitives'
import { StatCard } from '../components/ui/StatCard'
import { formatDuration, formatNumber } from '../utils/format'

const POLL_MS = 5000
const MAX_SAMPLES = 30

const LINKS = [
  { label: 'Grafana dashboards', href: 'http://localhost:3000', note: 'docker compose --profile monitoring, or kubectl port-forward svc/grafana 3000' },
  { label: 'Prometheus', href: 'http://localhost:9090', note: 'Targets, alert rules and raw PromQL' },
  { label: 'API documentation', href: '/api/docs', note: 'Interactive OpenAPI (Swagger UI)' },
]

export default function MonitoringPage() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [samples, setSamples] = useState([])
  const [pods, setPods] = useState({})
  const [live, setLive] = useState(true)

  useEffect(() => {
    if (!live) return undefined
    let cancelled = false
    const poll = async () => {
      const started = performance.now()
      try {
        const data = await systemApi.status()
        if (cancelled) return
        const rtt = Math.round(performance.now() - started)
        const time = new Date().toLocaleTimeString('en-GB', { hour12: false })
        setStatus(data)
        setError(null)
        setSamples((all) => [...all.slice(-(MAX_SAMPLES - 1)), { time, api: rtt, db: data.database.latency_ms ?? 0 }])
        setPods((all) => ({ ...all, [data.hostname]: { count: (all[data.hostname]?.count ?? 0) + 1, last: time } }))
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      }
    }
    poll()
    const timer = setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [live])

  const dbUp = status?.database.status === 'up'
  const podList = Object.entries(pods).sort((a, b) => b[1].count - a[1].count)

  return (
    <>
      <PageHeader
        title="System monitoring"
        description="Live status of the API pod that answers each request. Refreshes every 5 seconds."
        actions={
          <button type="button" className={live ? 'btn-secondary' : 'btn-primary'} onClick={() => setLive((v) => !v)} aria-pressed={live}>
            <Activity className="size-4" aria-hidden="true" /> {live ? 'Pause live updates' : 'Resume live updates'}
          </button>
        }
      />

      {error && (
        <div role="alert" className="mb-4 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <XCircle className="size-4" aria-hidden="true" /> API unreachable: {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="API status" value={error ? 'Down' : status ? 'Healthy' : '…'} hint={status ? `${status.environment} · v${status.version} (${status.commit})` : undefined} icon={error ? XCircle : CheckCircle2} accent={error ? 'critical' : 'good'} />
        <StatCard label="Database" value={status ? (dbUp ? 'Connected' : 'Unavailable') : '…'} hint={status && dbUp ? `${status.database.latency_ms} ms · PostgreSQL ${status.database.server_version}` : undefined} icon={Database} accent={status && !dbUp ? 'critical' : 'good'} />
        <StatCard label="Uptime (this pod)" value={status ? formatDuration(status.uptime_seconds) : '…'} hint={status ? `Python ${status.python_version}` : undefined} icon={Clock} accent="navy" />
        <StatCard label="Requests (this pod)" value={status ? formatNumber(status.requests.total) : '…'} hint={status ? `${status.requests.errors_5xx} server errors (5xx)` : undefined} icon={Server} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ChartCard title="Response time" subtitle={`Browser round-trip and database ping, last ${MAX_SAMPLES} samples`}
            table={{ columns: [{ key: 'time', header: 'Time' }, { key: 'api', header: 'API round-trip (ms)' }, { key: 'db', header: 'DB ping (ms)' }], rows: samples }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={samples} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="time" minTickGap={32} {...axisProps} />
                <YAxis width={52} tickFormatter={(v) => `${v}ms`} {...axisProps} />
                <Tooltip {...tooltipProps} formatter={(v, name) => [`${v} ms`, name]} />
                <Legend {...legendProps} />
                <Line type="linear" dataKey="api" name="API round-trip" stroke={SERIES[0]} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="linear" dataKey="db" name="DB ping" stroke={SERIES[1]} strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        <section className="card p-5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Boxes className="size-4 text-brand-600" aria-hidden="true" /> Backend replicas seen
          </h2>
          <p className="mt-1 mb-4 text-xs text-slate-500">
            Each poll may be answered by a different pod behind the Kubernetes Service - this is load balancing in action. Locally there is one process.
          </p>
          {podList.length === 0 ? (
            <p className="text-sm text-slate-500">Waiting for the first response…</p>
          ) : (
            <ul className="space-y-2">
              {podList.map(([host, info]) => (
                <li key={host} className="flex items-center justify-between gap-2 rounded-lg border border-slate-100 px-3 py-2">
                  <span className="truncate font-mono text-xs text-slate-700">{host}</span>
                  <span className="flex items-center gap-2 text-xs text-slate-500">
                    {status?.hostname === host && <Badge tone="good">serving</Badge>}
                    {info.count}×
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="card mt-4 p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">Observability tools</h2>
        <div className="grid gap-3 md:grid-cols-3">
          {LINKS.map((link) => (
            <a key={link.label} href={link.href} target="_blank" rel="noreferrer" className="rounded-xl border border-slate-200 p-4 transition-colors hover:border-brand-300 hover:bg-brand-50/50">
              <p className="flex items-center gap-1.5 text-sm font-medium text-slate-900">{link.label} <ExternalLink className="size-3.5 text-slate-400" aria-hidden="true" /></p>
              <p className="mt-1 text-xs text-slate-500">{link.note}</p>
            </a>
          ))}
        </div>
      </section>
    </>
  )
}
