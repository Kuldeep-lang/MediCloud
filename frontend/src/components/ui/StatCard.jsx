/** KPI tile: the number is the chart. Proportional figures for the headline value. */
export function StatCard({ label, value, hint, icon: Icon, accent = 'brand' }) {
  const accents = {
    brand: 'bg-brand-50 text-brand-600',
    good: 'bg-emerald-50 text-emerald-600',
    warning: 'bg-amber-50 text-amber-600',
    critical: 'bg-red-50 text-red-600',
    navy: 'bg-navy-900/5 text-navy-700',
  }
  return (
    <div className="card flex items-start gap-4 p-5">
      {Icon && (
        <span className={`rounded-xl p-2.5 ${accents[accent]}`}>
          <Icon className="size-5" aria-hidden="true" />
        </span>
      )}
      <div className="min-w-0">
        <p className="text-sm text-slate-500">{label}</p>
        <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
        {hint && <p className="mt-1 truncate text-xs text-slate-500">{hint}</p>}
      </div>
    </div>
  )
}
