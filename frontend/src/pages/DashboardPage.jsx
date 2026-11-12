import {
  BedDouble,
  BedSingle,
  CalendarClock,
  IndianRupee,
  Pill,
  Receipt,
  Stethoscope,
  Users,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { appointmentsApi, bedsApi, dashboardApi } from '../api/endpoints'
import { ChartCard } from '../components/charts/ChartCard'
import {
  axisProps,
  barGap,
  gridProps,
  legendProps,
  SERIES,
  tooltipProps,
} from '../components/charts/chartTheme'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { Badge, PageHeader } from '../components/ui/primitives'
import { StatCard } from '../components/ui/StatCard'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import {
  formatCurrency,
  formatDay,
  formatMonth,
  formatNumber,
  formatTime,
  titleCase,
  todayLocal,
} from '../utils/format'

const RANGES = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
]

function KpiRow({ summary, role }) {
  const beds = summary.beds
  const occupancy = beds.total ? Math.round((beds.occupied / beds.total) * 100) : 0
  const last = {
    admin: {
      label: 'Revenue this month',
      value: formatCurrency(summary.monthly_revenue),
      hint: 'Successful payments, month to date',
      icon: IndianRupee,
      accent: 'good',
    },
    receptionist: {
      label: 'Unpaid invoices',
      value: formatNumber(summary.unpaid_invoices),
      hint: 'Unpaid or partially paid',
      icon: Receipt,
      accent: 'warning',
    },
    pharmacist: {
      label: 'Low-stock medicines',
      value: formatNumber(summary.low_stock_medicines),
      hint: `${summary.pending_prescriptions} prescriptions pending`,
      icon: Pill,
      accent: 'warning',
    },
    doctor: {
      label: 'Pending prescriptions',
      value: formatNumber(summary.pending_prescriptions),
      hint: 'Awaiting dispensing',
      icon: Pill,
      accent: 'navy',
    },
  }[role]
  const cards = [
    { label: 'Total patients', value: formatNumber(summary.total_patients), icon: Users },
    { label: 'Active doctors', value: formatNumber(summary.total_doctors), icon: Stethoscope, accent: 'navy' },
    {
      label: "Today's appointments",
      value: formatNumber(summary.appointments_today),
      hint:
        summary.my_appointments_today != null
          ? `${summary.my_appointments_today} with you`
          : 'Excluding cancellations',
      icon: CalendarClock,
    },
    {
      label: 'Available beds',
      value: `${formatNumber(beds.available)} / ${formatNumber(beds.total)}`,
      hint: `ICU: ${summary.icu.available} of ${summary.icu.total} free`,
      icon: BedSingle,
      accent: 'good',
    },
    {
      label: 'Occupied beds',
      value: formatNumber(beds.occupied),
      hint: `${occupancy}% occupancy · ${beds.maintenance} in maintenance`,
      icon: BedDouble,
      accent: 'navy',
    },
    last,
  ]
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map((card) => (
        <StatCard key={card.label} {...card} />
      ))}
    </div>
  )
}

function StatusBreakdown({ rows }) {
  const total = rows.reduce((sum, r) => sum + r.count, 0)
  const sorted = [...rows].sort((a, b) => b.count - a.count)
  return (
    <ul className="space-y-3">
      {sorted.map((row) => {
        const pct = total ? (row.count / total) * 100 : 0
        return (
          <li key={row.status}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-slate-700">{titleCase(row.status)}</span>
              <span className="tabular text-slate-500">
                {formatNumber(row.count)} · {pct.toFixed(0)}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full"
                style={{ width: `${pct}%`, backgroundColor: SERIES[0] }}
                aria-hidden="true"
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export default function DashboardPage() {
  const { user, hasRole } = useAuth()
  const [days, setDays] = useState(30)
  const isAdmin = hasRole('admin')
  const canSeeBeds = hasRole('admin', 'doctor', 'receptionist')

  const summary = useApi(() => dashboardApi.summary(), [])
  const trend = useApi(() => dashboardApi.admissionsTrend(days), [days])
  const stats = useApi(() => dashboardApi.appointmentStats(days), [days])
  const departments = useApi(() => dashboardApi.departmentDistribution(Math.max(days, 30)), [days])
  const revenue = useApi(() => dashboardApi.revenue(6), [], { enabled: isAdmin })
  const occupancy = useApi(() => bedsApi.occupancy(), [], { enabled: canSeeBeds })
  const today = useApi(() => appointmentsApi.list({ date: todayLocal(), page_size: 6 }), [], {
    enabled: canSeeBeds,
  })

  const daily = (stats.data?.daily ?? []).map((d) => ({
    date: d.date,
    completed: d.completed,
    cancelled: d.cancelled,
    other: d.total - d.completed - d.cancelled,
  }))
  const wardTypes = Object.entries(occupancy.data?.by_ward_type ?? {}).map(([type, b]) => ({
    type: type === 'icu' ? 'ICU' : titleCase(type),
    occupied: b.occupied,
    maintenance: b.maintenance,
    available: b.available,
  }))

  return (
    <>
      <PageHeader
        title={`Welcome, ${user.full_name.startsWith('Dr.') ? user.full_name : user.full_name.split(' ')[0]}`}
        description="Live hospital overview - every figure is computed from the database."
      />

      <AsyncContent state={summary}>{(data) => <KpiRow summary={data} role={user.role} />}</AsyncContent>

      {/* One filter row scopes every trend chart below it. */}
      <div className="mt-8 mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">Trends</h2>
        <div role="group" aria-label="Date range" className="flex gap-1 rounded-xl bg-slate-100 p-1">
          {RANGES.map((range) => (
            <button
              key={range.value}
              type="button"
              aria-pressed={days === range.value}
              onClick={() => setDays(range.value)}
              className={`rounded-lg px-3 py-1 text-xs font-medium ${
                days === range.value ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-600'
              }`}
            >
              Last {range.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Patient admissions"
          subtitle={`Admissions and discharges per day, last ${days} days`}
          state={trend}
          table={{
            columns: [
              { key: 'date', header: 'Date', format: (v) => formatDay(v) },
              { key: 'admissions', header: 'Admissions' },
              { key: 'discharges', header: 'Discharges' },
            ],
            rows: trend.data ?? [],
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" tickFormatter={(v) => formatDay(v)} minTickGap={24} {...axisProps} />
              <YAxis allowDecimals={false} width={36} {...axisProps} />
              <Tooltip {...tooltipProps} labelFormatter={(v) => formatDay(v, { dateStyle: 'medium' })} />
              <Legend {...legendProps} />
              <Line type="linear" dataKey="admissions" name="Admissions" stroke={SERIES[0]} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }} />
              <Line type="linear" dataKey="discharges" name="Discharges" stroke={SERIES[1]} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Appointments"
          subtitle={`Daily appointments by outcome, last ${days} days`}
          state={stats}
          table={{
            columns: [
              { key: 'date', header: 'Date', format: (v) => formatDay(v) },
              { key: 'completed', header: 'Completed' },
              { key: 'cancelled', header: 'Cancelled' },
              { key: 'other', header: 'Scheduled / no-show' },
            ],
            rows: daily,
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={daily} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" tickFormatter={(v) => formatDay(v)} minTickGap={24} {...axisProps} />
              <YAxis allowDecimals={false} width={36} {...axisProps} />
              <Tooltip {...tooltipProps} labelFormatter={(v) => formatDay(v, { dateStyle: 'medium' })} />
              <Legend {...legendProps} />
              <Bar dataKey="completed" name="Completed" stackId="a" fill={SERIES[0]} {...barGap} />
              <Bar dataKey="cancelled" name="Cancelled" stackId="a" fill={SERIES[1]} {...barGap} />
              <Bar dataKey="other" name="Scheduled / no-show" stackId="a" fill={SERIES[2]} radius={[4, 4, 0, 0]} {...barGap} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Patients by department"
          subtitle={`Distinct patients seen, last ${Math.max(days, 30)} days`}
          state={departments}
          height={280}
          table={{
            columns: [
              { key: 'department', header: 'Department' },
              { key: 'patients', header: 'Patients' },
            ],
            rows: departments.data ?? [],
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={departments.data ?? []} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid {...gridProps} horizontal={false} vertical />
              <XAxis type="number" allowDecimals={false} {...axisProps} />
              <YAxis type="category" dataKey="department" width={150} {...axisProps} />
              <Tooltip {...tooltipProps} />
              <Bar dataKey="patients" name="Patients" fill={SERIES[0]} radius={[0, 4, 4, 0]} barSize={14} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Appointment status" subtitle={`Share of appointments, last ${days} days`} state={stats} height={280}>
          {stats.data && <StatusBreakdown rows={stats.data.by_status} />}
        </ChartCard>

        {isAdmin && (
          <ChartCard
            title="Monthly revenue"
            subtitle="Successful (simulated) payments, last 6 months"
            state={revenue}
            table={{
              columns: [
                { key: 'month', header: 'Month', format: formatMonth },
                { key: 'revenue', header: 'Revenue', format: (v) => formatCurrency(v) },
              ],
              rows: revenue.data ?? [],
            }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={revenue.data ?? []} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="month" tickFormatter={formatMonth} {...axisProps} />
                <YAxis width={64} tickFormatter={(v) => formatCurrency(v, { compact: true })} {...axisProps} />
                <Tooltip {...tooltipProps} labelFormatter={formatMonth} formatter={(v) => [formatCurrency(v), 'Revenue']} />
                <Bar dataKey="revenue" name="Revenue" fill={SERIES[0]} radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {canSeeBeds && (
          <ChartCard
            title="Bed occupancy by ward type"
            subtitle="Current state of every bed"
            state={occupancy}
            table={{
              columns: [
                { key: 'type', header: 'Ward type' },
                { key: 'occupied', header: 'Occupied' },
                { key: 'maintenance', header: 'Maintenance' },
                { key: 'available', header: 'Available' },
              ],
              rows: wardTypes,
            }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={wardTypes} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid {...gridProps} horizontal={false} vertical />
                <XAxis type="number" allowDecimals={false} {...axisProps} />
                <YAxis type="category" dataKey="type" width={90} {...axisProps} />
                <Tooltip {...tooltipProps} />
                <Legend {...legendProps} />
                <Bar dataKey="occupied" name="Occupied" stackId="b" fill={SERIES[0]} barSize={18} {...barGap} />
                <Bar dataKey="maintenance" name="Maintenance" stackId="b" fill={SERIES[1]} barSize={18} {...barGap} />
                <Bar dataKey="available" name="Available" stackId="b" fill={SERIES[2]} barSize={18} radius={[0, 4, 4, 0]} {...barGap} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}
      </div>

      {canSeeBeds && (
        <section className="card mt-4 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">
              {hasRole('doctor') ? 'Your appointments today' : "Today's schedule"}
            </h2>
            <Link to="/appointments" className="text-xs font-medium text-brand-600 hover:underline">
              View all
            </Link>
          </div>
          <AsyncContent
            state={today}
            isEmpty={(d) => d.items.length === 0}
            empty={<EmptyState title="No appointments today" icon={CalendarClock} />}
          >
            {(data) => (
              <ul className="divide-y divide-slate-100">
                {data.items.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                    <span className="tabular w-12 font-medium text-slate-900">{formatTime(a.scheduled_at)}</span>
                    <span className="flex-1 truncate text-slate-700">
                      {a.patient_name}
                      <span className="ml-2 text-xs text-slate-400">{a.patient_code}</span>
                    </span>
                    <span className="hidden truncate text-slate-500 sm:block">{a.doctor_name}</span>
                    <Badge status={a.status} />
                  </li>
                ))}
              </ul>
            )}
          </AsyncContent>
        </section>
      )}
    </>
  )
}
