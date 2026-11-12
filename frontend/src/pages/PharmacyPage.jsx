import { AlertTriangle, CalendarX, History, PackagePlus, Pill, Plus, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { errorMessage } from '../api/client'
import { doctorsApi, medicinesApi, prescriptionsApi } from '../api/endpoints'
import { ChartCard } from '../components/charts/ChartCard'
import { axisProps, gridProps, SERIES, tooltipProps } from '../components/charts/chartTheme'
import { PatientPicker } from '../components/PatientPicker'
import { DataTable, Pagination } from '../components/ui/DataTable'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { ConfirmDialog, Modal } from '../components/ui/Modal'
import { Badge, Field, PageHeader, Tabs } from '../components/ui/primitives'
import { StatCard } from '../components/ui/StatCard'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { useDebounce } from '../hooks/useDebounce'
import { formatCurrency, formatDate, formatDateTime, formatDay, titleCase } from '../utils/format'

const PAGE_SIZE = 15

function ExpiryCell({ medicine }) {
  if (medicine.is_expired) return <Badge tone="critical">Expired {formatDate(medicine.expiry_date)}</Badge>
  if (medicine.days_to_expiry <= 30) return <Badge tone="warning">{medicine.days_to_expiry} days left</Badge>
  return <span className="text-slate-600">{formatDate(medicine.expiry_date)}</span>
}

const EMPTY_MED = { code: '', name: '', generic_name: '', category: '', manufacturer: '', dosage_form: 'tablet', strength: '', unit_price: '', stock_quantity: '0', reorder_level: '10', batch_number: '', expiry_date: '' }

function MedicineFormModal({ medicine, onClose, onSaved }) {
  const toast = useToast()
  const [values, setValues] = useState(medicine ? Object.fromEntries(Object.keys(EMPTY_MED).map((k) => [k, medicine[k] ?? ''])) : EMPTY_MED)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setValues((v) => ({ ...v, [key]: e.target.value }))
  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const payload = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v === '' ? null : v]))
    try {
      if (medicine) {
        delete payload.code
        delete payload.stock_quantity
        await medicinesApi.update(medicine.id, payload)
      } else {
        await medicinesApi.create(payload)
      }
      toast.success(medicine ? 'Medicine updated' : `${values.name} added to inventory`)
      onSaved()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  const input = (key, props = {}) => (id) => <input id={id} className="input" value={values[key]} onChange={set(key)} {...props} />
  return (
    <Modal open onClose={onClose} size="lg" title={medicine ? `Edit ${medicine.name}` : 'Add medicine'}
      footer={<><button type="button" className="btn-secondary" onClick={onClose}>Cancel</button><button type="submit" form="medicine-form" className="btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button></>}>
      <form id="medicine-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-3">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-3">{error}</p>}
        <Field label="Code" required>{input('code', { required: true, disabled: Boolean(medicine) })}</Field>
        <Field label="Name" required className="sm:col-span-2">{input('name', { required: true })}</Field>
        <Field label="Generic name">{input('generic_name')}</Field>
        <Field label="Category">{input('category')}</Field>
        <Field label="Manufacturer">{input('manufacturer')}</Field>
        <Field label="Form">{input('dosage_form')}</Field>
        <Field label="Strength">{input('strength', { placeholder: '500 mg' })}</Field>
        <Field label="Unit price" required>{input('unit_price', { type: 'number', min: 0, step: '0.01', required: true })}</Field>
        {!medicine && <Field label="Opening stock">{input('stock_quantity', { type: 'number', min: 0 })}</Field>}
        <Field label="Reorder level">{input('reorder_level', { type: 'number', min: 0 })}</Field>
        <Field label="Batch number">{input('batch_number')}</Field>
        <Field label="Expiry date" required>{input('expiry_date', { type: 'date', required: true })}</Field>
      </form>
    </Modal>
  )
}

function StockModal({ medicine, onClose, onSaved }) {
  const toast = useToast()
  const [reason, setReason] = useState('restock')
  const [direction, setDirection] = useState('add')
  const [quantity, setQuantity] = useState('')
  const [reference, setReference] = useState('')
  const [error, setError] = useState(null)
  const signed = () => {
    const q = Math.abs(Number(quantity))
    if (reason === 'restock') return q
    if (reason === 'expired') return -q
    return direction === 'add' ? q : -q
  }
  const submit = async () => {
    try {
      const updated = await medicinesApi.adjustStock(medicine.id, { change_quantity: signed(), reason, reference: reference || null })
      toast.success(`${medicine.name}: stock is now ${updated.stock_quantity}`)
      onSaved()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }
  return (
    <Modal open onClose={onClose} size="sm" title="Adjust stock" description={`${medicine.name} · ${medicine.stock_quantity} in stock`}
      footer={<><button type="button" className="btn-secondary" onClick={onClose}>Cancel</button><button type="button" className="btn-primary" onClick={submit} disabled={!Number(quantity)}>Save</button></>}>
      <div className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <Field label="Type">
          {(id) => (
            <select id={id} className="input" value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="restock">Restock (add)</option>
              <option value="adjustment">Stock-take adjustment</option>
              <option value="expired">Expired write-off (remove)</option>
            </select>
          )}
        </Field>
        {reason === 'adjustment' && (
          <Field label="Direction">
            {(id) => (
              <select id={id} className="input" value={direction} onChange={(e) => setDirection(e.target.value)}>
                <option value="add">Increase</option>
                <option value="remove">Decrease</option>
              </select>
            )}
          </Field>
        )}
        <Field label="Quantity" required>{(id) => <input id={id} type="number" min="1" className="input" value={quantity} onChange={(e) => setQuantity(e.target.value)} />}</Field>
        <Field label="Reference">{(id) => <input id={id} className="input" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="e.g. PO-2026-118" maxLength={60} />}</Field>
      </div>
    </Modal>
  )
}

function MovementsModal({ medicine, onClose }) {
  const movements = useApi(() => medicinesApi.movements(medicine.id, { page_size: 50 }), [medicine.id])
  return (
    <Modal open onClose={onClose} size="lg" title="Stock history" description={medicine.name}>
      <AsyncContent state={movements}>
        {(data) => (
          <DataTable dense rows={data.items} empty={<EmptyState title="No stock movements" />}
            columns={[
              { key: 'created_at', header: 'When', render: (m) => formatDateTime(m.created_at), className: 'whitespace-nowrap' },
              { key: 'reason', header: 'Type', render: (m) => titleCase(m.reason) },
              { key: 'change_quantity', header: 'Change', align: 'right', render: (m) => <span className={m.change_quantity > 0 ? 'text-emerald-700' : 'text-slate-700'}>{m.change_quantity > 0 ? '+' : ''}{m.change_quantity}</span> },
              { key: 'balance_after', header: 'Balance', align: 'right' },
              { key: 'reference', header: 'Reference', render: (m) => m.reference ?? '—' },
            ]} />
        )}
      </AsyncContent>
    </Modal>
  )
}

function InventoryTab({ canManage, lowOnly, setLowOnly }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState(null)
  const term = useDebounce(search.trim(), 300)
  const categories = useApi(() => medicinesApi.categories(), [])
  const medicines = useApi(() => medicinesApi.list({ search: term, category, low_stock: lowOnly, page, page_size: PAGE_SIZE }), [term, category, lowOnly, page])

  const columns = [
    { key: 'name', header: 'Medicine', render: (m) => <div><p className="font-medium text-slate-900">{m.name}</p><p className="text-xs text-slate-500"><span className="font-mono">{m.code}</span> · {m.generic_name ?? '—'}</p></div> },
    { key: 'category', header: 'Category', render: (m) => m.category ?? '—' },
    { key: 'stock_quantity', header: 'Stock', align: 'right', render: (m) => <span className="inline-flex items-center gap-2">{m.is_low_stock && <Badge tone="warning">Low</Badge>}{m.stock_quantity}</span> },
    { key: 'reorder_level', header: 'Reorder at', align: 'right' },
    { key: 'unit_price', header: 'Unit price', align: 'right', render: (m) => formatCurrency(m.unit_price) },
    { key: 'expiry', header: 'Expiry', render: (m) => <ExpiryCell medicine={m} /> },
    ...(canManage ? [{ key: 'actions', header: <span className="sr-only">Actions</span>, align: 'right', render: (m) => (
      <div className="flex justify-end gap-1">
        <button type="button" className="btn-secondary btn-sm" onClick={() => setModal({ type: 'stock', medicine: m })}><PackagePlus className="size-3.5" aria-hidden="true" /> Stock</button>
        <button type="button" className="btn-ghost btn-sm" onClick={() => setModal({ type: 'edit', medicine: m })}>Edit</button>
        <button type="button" className="btn-ghost btn-sm" onClick={() => setModal({ type: 'history', medicine: m })} aria-label={`Stock history for ${m.name}`}><History className="size-3.5" /></button>
        <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => setModal({ type: 'remove', medicine: m })} aria-label={`Remove ${m.name}`}><Trash2 className="size-3.5" /></button>
      </div>
    ) }] : []),
  ]

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 lg:flex-row lg:items-center">
        <label className="relative flex-1">
          <span className="sr-only">Search medicines</span>
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
          <input className="input pl-9" placeholder="Search by name, generic name or code…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        </label>
        <select className="input lg:w-48" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1) }} aria-label="Filter by category">
          <option value="">All categories</option>
          {(categories.data ?? []).map((c) => <option key={c}>{c}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" className="accent-brand-600" checked={lowOnly} onChange={(e) => { setLowOnly(e.target.checked); setPage(1) }} /> Low stock only
        </label>
        {canManage && <button type="button" className="btn-primary" onClick={() => setModal({ type: 'add' })}><Plus className="size-4" aria-hidden="true" /> Add medicine</button>}
      </div>
      <AsyncContent state={medicines}>
        {(data) => (
          <>
            <DataTable columns={columns} rows={data.items} empty={<EmptyState icon={Pill} title="No medicines found" />} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
          </>
        )}
      </AsyncContent>
      {modal?.type === 'add' && <MedicineFormModal onClose={() => setModal(null)} onSaved={medicines.reload} />}
      {modal?.type === 'edit' && <MedicineFormModal medicine={modal.medicine} onClose={() => setModal(null)} onSaved={medicines.reload} />}
      {modal?.type === 'stock' && <StockModal medicine={modal.medicine} onClose={() => setModal(null)} onSaved={medicines.reload} />}
      {modal?.type === 'history' && <MovementsModal medicine={modal.medicine} onClose={() => setModal(null)} />}
      <ConfirmDialog open={modal?.type === 'remove'} title="Remove medicine?" confirmLabel="Remove"
        message={modal?.medicine ? `${modal.medicine.name} will be hidden from the formulary. Its stock history is kept.` : ''}
        onClose={() => setModal(null)}
        onConfirm={async () => {
          try { await medicinesApi.deactivate(modal.medicine.id); toast.success('Medicine removed'); medicines.reload(); setModal(null) } catch (err) { toast.error(errorMessage(err)) }
        }} />
    </div>
  )
}

const EMPTY_ITEM = { medicine_id: '', dosage: '', frequency: '1-0-1', duration_days: '5', quantity: '10', instructions: '' }

function PrescriptionModal({ onClose, onSaved }) {
  const { hasRole } = useAuth()
  const toast = useToast()
  const isAdmin = hasRole('admin')
  const [patient, setPatient] = useState(null)
  const [doctorId, setDoctorId] = useState('')
  const [items, setItems] = useState([EMPTY_ITEM])
  const [notes, setNotes] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const medicines = useApi(() => medicinesApi.list({ page_size: 100 }), [])
  const doctors = useApi(() => doctorsApi.list({ page_size: 100 }), [], { enabled: isAdmin })
  const update = (i, key, value) => setItems((all) => all.map((it, idx) => (idx === i ? { ...it, [key]: value } : it)))
  const valid = patient && items.every((i) => i.medicine_id && i.dosage && i.frequency && Number(i.quantity) > 0) && (!isAdmin || doctorId)

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await prescriptionsApi.create({
        patient_id: patient.id,
        doctor_id: isAdmin ? Number(doctorId) : null,
        notes: notes || null,
        items: items.map((i) => ({ ...i, medicine_id: Number(i.medicine_id), quantity: Number(i.quantity), duration_days: i.duration_days ? Number(i.duration_days) : null, instructions: i.instructions || null })),
      })
      toast.success(`Prescription created for ${patient.full_name}`)
      onSaved()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} size="xl" title="Write prescription"
      footer={<><button type="button" className="btn-secondary" onClick={onClose}>Cancel</button><button type="button" className="btn-primary" onClick={submit} disabled={!valid || busy}>{busy ? 'Saving…' : 'Create prescription'}</button></>}>
      <div className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Patient" required>{(id) => <PatientPicker id={id} value={patient} onChange={setPatient} />}</Field>
          {isAdmin && (
            <Field label="Prescribing doctor" required>
              {(id) => <select id={id} className="input" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}><option value="">Select…</option>{(doctors.data?.items ?? []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</select>}
            </Field>
          )}
        </div>
        <div>
          <p className="label">Medicines</p>
          <div className="space-y-2">
            {items.map((item, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 rounded-xl border border-slate-100 p-2 md:grid-cols-[2fr_1fr_1fr_0.7fr_0.7fr_auto]">
                <select className="input col-span-2 md:col-span-1" value={item.medicine_id} onChange={(e) => update(i, 'medicine_id', e.target.value)} aria-label="Medicine">
                  <option value="">Select medicine…</option>
                  {(medicines.data?.items ?? []).map((m) => <option key={m.id} value={m.id} disabled={m.is_expired}>{m.name} ({m.stock_quantity} in stock)</option>)}
                </select>
                <input className="input" placeholder="Dosage" value={item.dosage} onChange={(e) => update(i, 'dosage', e.target.value)} aria-label="Dosage" />
                <input className="input" placeholder="Frequency" value={item.frequency} onChange={(e) => update(i, 'frequency', e.target.value)} aria-label="Frequency" />
                <input className="input" type="number" min="1" placeholder="Days" value={item.duration_days} onChange={(e) => update(i, 'duration_days', e.target.value)} aria-label="Duration in days" />
                <input className="input" type="number" min="1" placeholder="Qty" value={item.quantity} onChange={(e) => update(i, 'quantity', e.target.value)} aria-label="Quantity" />
                <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => setItems((all) => all.filter((_, idx) => idx !== i))} disabled={items.length === 1} aria-label="Remove medicine"><Trash2 className="size-4" /></button>
              </div>
            ))}
          </div>
          <button type="button" className="btn-secondary btn-sm mt-2" onClick={() => setItems((all) => [...all, EMPTY_ITEM])}><Plus className="size-3.5" aria-hidden="true" /> Add medicine</button>
        </div>
        <Field label="Notes">{(id) => <textarea id={id} className="input min-h-16" value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      </div>
    </Modal>
  )
}

function PrescriptionsTab() {
  const { hasRole } = useAuth()
  const toast = useToast()
  const [status, setStatus] = useState('pending')
  const [page, setPage] = useState(1)
  const [writing, setWriting] = useState(false)
  const [confirm, setConfirm] = useState(null)
  const prescriptions = useApi(() => prescriptionsApi.list({ status, page, page_size: PAGE_SIZE }), [status, page])
  const canDispense = hasRole('admin', 'pharmacist')
  const canPrescribe = hasRole('admin', 'doctor')

  const act = async () => {
    const { type, rx } = confirm
    try {
      if (type === 'dispense') await prescriptionsApi.dispense(rx.id)
      else await prescriptionsApi.cancel(rx.id)
      toast.success(type === 'dispense' ? `Dispensed for ${rx.patient_name} - stock updated` : 'Prescription cancelled')
      prescriptions.reload()
      setConfirm(null)
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
        <select className="input sm:w-48" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} aria-label="Filter prescriptions">
          <option value="pending">Pending</option>
          <option value="dispensed">Dispensed</option>
          <option value="cancelled">Cancelled</option>
          <option value="">All</option>
        </select>
        {canPrescribe && <button type="button" className="btn-primary" onClick={() => setWriting(true)}><Plus className="size-4" aria-hidden="true" /> Write prescription</button>}
      </div>
      <AsyncContent state={prescriptions}>
        {(data) => (
          <>
            <DataTable rows={data.items} empty={<EmptyState icon={Pill} title="No prescriptions" />}
              columns={[
                { key: 'created_at', header: 'Date', render: (p) => formatDateTime(p.created_at), className: 'whitespace-nowrap' },
                { key: 'patient', header: 'Patient', render: (p) => <div><p className="font-medium text-slate-900">{p.patient_name}</p><p className="font-mono text-xs text-slate-500">{p.patient_code}</p></div> },
                { key: 'doctor_name', header: 'Doctor' },
                { key: 'items', header: 'Medicines', render: (p) => <ul className="text-xs text-slate-600">{p.items.map((i) => <li key={i.id}>{i.medicine_name} · {i.frequency} · ×{i.quantity}</li>)}</ul> },
                { key: 'status', header: 'Status', render: (p) => <Badge status={p.status} /> },
                { key: 'actions', header: <span className="sr-only">Actions</span>, align: 'right', render: (p) => p.status === 'pending' && (
                  <div className="flex justify-end gap-1">
                    {canDispense && <button type="button" className="btn-primary btn-sm" onClick={() => setConfirm({ type: 'dispense', rx: p })}>Dispense</button>}
                    {canPrescribe && <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => setConfirm({ type: 'cancel', rx: p })}>Cancel</button>}
                  </div>
                ) },
              ]} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
          </>
        )}
      </AsyncContent>
      {writing && <PrescriptionModal onClose={() => setWriting(false)} onSaved={prescriptions.reload} />}
      <ConfirmDialog open={Boolean(confirm)} tone={confirm?.type === 'dispense' ? 'primary' : 'danger'}
        title={confirm?.type === 'dispense' ? 'Dispense prescription?' : 'Cancel prescription?'}
        message={confirm?.type === 'dispense' ? `Stock for every medicine will be reduced in one transaction - all items or none.` : 'This prescription will be cancelled.'}
        confirmLabel={confirm?.type === 'dispense' ? 'Dispense' : 'Cancel prescription'}
        onConfirm={act} onClose={() => setConfirm(null)} />
    </div>
  )
}

function UsageTab() {
  const usage = useApi(() => medicinesApi.usage(30), [])
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <ChartCard title="Units dispensed per day" subtitle="Last 30 days" state={usage}
          table={{ columns: [{ key: 'date', header: 'Date', format: (v) => formatDay(v) }, { key: 'quantity', header: 'Units' }], rows: usage.data?.daily ?? [] }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={usage.data?.daily ?? []} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" tickFormatter={(v) => formatDay(v)} minTickGap={24} {...axisProps} />
              <YAxis allowDecimals={false} width={40} {...axisProps} />
              <Tooltip {...tooltipProps} labelFormatter={(v) => formatDay(v, { dateStyle: 'medium' })} formatter={(v) => [v, 'Units dispensed']} />
              <Bar dataKey="quantity" fill={SERIES[0]} radius={[4, 4, 0, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-slate-900">Most dispensed</h2>
        <p className="mb-4 text-xs text-slate-500">Top medicines, last 30 days</p>
        <AsyncContent state={usage} isEmpty={(d) => !d.top_medicines.length} empty={<EmptyState title="Nothing dispensed yet" />}>
          {(data) => {
            const max = Math.max(...data.top_medicines.map((m) => m.quantity), 1)
            return (
              <ul className="space-y-3">
                {data.top_medicines.map((m) => (
                  <li key={m.medicine_id}>
                    <div className="mb-1 flex justify-between text-sm"><span className="text-slate-700">{m.name}</span><span className="tabular text-slate-500">{m.quantity}</span></div>
                    <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full" style={{ width: `${(m.quantity / max) * 100}%`, backgroundColor: SERIES[0] }} /></div>
                  </li>
                ))}
              </ul>
            )
          }}
        </AsyncContent>
      </section>
    </div>
  )
}

export default function PharmacyPage() {
  const { hasRole } = useAuth()
  const canManage = hasRole('admin', 'pharmacist')
  const [tab, setTab] = useState(canManage ? 'inventory' : 'prescriptions')
  const [lowOnly, setLowOnly] = useState(false)
  const alerts = useApi(() => medicinesApi.alerts(), [], { enabled: canManage })

  return (
    <>
      <PageHeader title="Pharmacy" description="Inventory, prescriptions, alerts and stock usage." />
      {canManage && alerts.data && (
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <button type="button" className="text-left" onClick={() => { setTab('inventory'); setLowOnly(true) }}>
            <StatCard label="Low stock" value={alerts.data.low_stock.length} hint={alerts.data.low_stock.slice(0, 3).map((m) => m.name).join(', ') || 'All stocked'} icon={AlertTriangle} accent="warning" />
          </button>
          <StatCard label="Expiring within 30 days" value={alerts.data.expiring_soon.length} hint={alerts.data.expiring_soon.slice(0, 3).map((m) => m.name).join(', ') || 'None'} icon={CalendarX} accent="warning" />
          <StatCard label="Expired with stock" value={alerts.data.expired.length} hint={alerts.data.expired.map((m) => m.name).join(', ') || 'None'} icon={CalendarX} accent="critical" />
        </div>
      )}
      <div className="mb-4">
        <Tabs value={tab} onChange={setTab} tabs={[
          { value: 'inventory', label: 'Inventory' },
          { value: 'prescriptions', label: 'Prescriptions' },
          ...(canManage ? [{ value: 'usage', label: 'Stock usage' }] : []),
        ]} />
      </div>
      {tab === 'inventory' && <InventoryTab canManage={canManage} lowOnly={lowOnly} setLowOnly={setLowOnly} />}
      {tab === 'prescriptions' && <PrescriptionsTab />}
      {tab === 'usage' && <UsageTab />}
    </>
  )
}
