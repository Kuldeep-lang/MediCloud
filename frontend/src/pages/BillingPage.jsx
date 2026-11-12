import { CreditCard, FilePlus2, Plus, Receipt, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { errorMessage } from '../api/client'
import { billingApi } from '../api/endpoints'
import { PatientPicker } from '../components/PatientPicker'
import { DataTable, Pagination } from '../components/ui/DataTable'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { ConfirmDialog, Modal } from '../components/ui/Modal'
import { Badge, DetailItem, Field, PageHeader, Spinner, Tabs } from '../components/ui/primitives'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { useDebounce } from '../hooks/useDebounce'
import { PAYMENT_METHODS } from '../utils/constants'
import { formatCurrency, formatDate, formatDateTime, titleCase } from '../utils/format'

const PAGE_SIZE = 15
const round2 = (n) => Math.round(n * 100) / 100

function NewInvoiceModal({ onClose, onCreated }) {
  const toast = useToast()
  const [patient, setPatient] = useState(null)
  const [excluded, setExcluded] = useState(() => new Set())
  const [extras, setExtras] = useState([])
  const [discount, setDiscount] = useState('0')
  const [taxPercent, setTaxPercent] = useState('0')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const billable = useApi(() => billingApi.billable(patient.id), [patient?.id], { enabled: Boolean(patient) })

  const selected = (billable.data?.items ?? []).filter((_, i) => !excluded.has(i))
  const extraLines = extras.filter((e) => e.description.trim().length >= 2 && Number(e.unit_price) >= 0 && Number(e.quantity) >= 1)
  const subtotal = round2(
    selected.reduce((s, i) => s + i.line_total, 0) + extraLines.reduce((s, e) => s + Number(e.unit_price) * Number(e.quantity), 0),
  )
  const disc = Number(discount) || 0
  const tax = round2(((subtotal - disc) * (Number(taxPercent) || 0)) / 100)
  const total = round2(subtotal - disc + tax)

  const toggle = (i) =>
    setExcluded((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const items = [
        ...selected.map(({ line_total: _ignored, ...item }) =>
          Object.fromEntries(Object.entries(item).filter(([, v]) => v != null)),
        ),
        ...extraLines.map((e) => ({ ...e, quantity: Number(e.quantity) })),
      ]
      const invoice = await billingApi.create({ patient_id: patient.id, items, discount: disc.toFixed(2), tax_percent: taxPercent || '0' })
      toast.success(`Invoice ${invoice.invoice_number} created`)
      onCreated(invoice)
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} size="xl" title="New invoice" description="Unbilled consultations, dispensed medicines and room stays are added automatically."
      footer={<><button type="button" className="btn-secondary" onClick={onClose}>Cancel</button><button type="button" className="btn-primary" onClick={submit} disabled={busy || !patient || (!selected.length && !extraLines.length) || disc > subtotal}>{busy ? 'Creating…' : `Create invoice · ${formatCurrency(total)}`}</button></>}>
      <div className="space-y-5">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <Field label="Patient" required>{(id) => <PatientPicker id={id} value={patient} onChange={(p) => { setPatient(p); setExcluded(new Set()) }} />}</Field>

        {patient && (
          <div>
            <p className="label">Billable items</p>
            {billable.loading ? (
              <p className="flex items-center gap-2 text-sm text-slate-500"><Spinner className="size-4" /> Finding unbilled items…</p>
            ) : billable.data?.items.length ? (
              <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
                {billable.data.items.map((item, i) => (
                  <li key={i}>
                    <label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-slate-50">
                      <input type="checkbox" className="accent-brand-600" checked={!excluded.has(i)} onChange={() => toggle(i)} />
                      <Badge tone="neutral">{titleCase(item.item_type)}</Badge>
                      <span className="flex-1 text-slate-700">{item.description}</span>
                      <span className="tabular text-slate-900">{formatCurrency(item.line_total)}</span>
                    </label>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="rounded-xl border border-dashed border-slate-200 px-3 py-4 text-center text-sm text-slate-500">Nothing unbilled for this patient. Add a manual line below.</p>
            )}
          </div>
        )}

        {patient && (
          <div>
            <p className="label">Additional charges (diagnostics, procedures…)</p>
            <div className="space-y-2">
              {extras.map((e, i) => (
                <div key={i} className="grid grid-cols-[0.9fr_2fr_0.6fr_1fr_auto] gap-2">
                  <select className="input" value={e.item_type} onChange={(ev) => setExtras((all) => all.map((x, j) => (j === i ? { ...x, item_type: ev.target.value } : x)))} aria-label="Charge type">
                    <option value="diagnostic">Diagnostic</option>
                    <option value="other">Other</option>
                  </select>
                  <input className="input" placeholder="Description" value={e.description} onChange={(ev) => setExtras((all) => all.map((x, j) => (j === i ? { ...x, description: ev.target.value } : x)))} aria-label="Description" />
                  <input className="input" type="number" min="1" value={e.quantity} onChange={(ev) => setExtras((all) => all.map((x, j) => (j === i ? { ...x, quantity: ev.target.value } : x)))} aria-label="Quantity" />
                  <input className="input" type="number" min="0" step="0.01" placeholder="Price" value={e.unit_price} onChange={(ev) => setExtras((all) => all.map((x, j) => (j === i ? { ...x, unit_price: ev.target.value } : x)))} aria-label="Unit price" />
                  <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => setExtras((all) => all.filter((_, j) => j !== i))} aria-label="Remove charge"><Trash2 className="size-4" /></button>
                </div>
              ))}
            </div>
            <button type="button" className="btn-secondary btn-sm mt-2" onClick={() => setExtras((all) => [...all, { item_type: 'diagnostic', description: '', quantity: '1', unit_price: '' }])}>
              <Plus className="size-3.5" aria-hidden="true" /> Add charge
            </button>
          </div>
        )}

        {patient && (
          <div className="grid gap-4 rounded-xl bg-slate-50 p-4 sm:grid-cols-2">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Discount" error={disc > subtotal ? 'Exceeds subtotal' : undefined}>{(id) => <input id={id} type="number" min="0" step="0.01" className="input" value={discount} onChange={(e) => setDiscount(e.target.value)} />}</Field>
              <Field label="Tax %">{(id) => <input id={id} type="number" min="0" max="100" step="0.5" className="input" value={taxPercent} onChange={(e) => setTaxPercent(e.target.value)} />}</Field>
            </div>
            <dl className="tabular space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Subtotal</dt><dd>{formatCurrency(subtotal)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Discount</dt><dd>−{formatCurrency(disc)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Tax</dt><dd>{formatCurrency(tax)}</dd></div>
              <div className="flex justify-between border-t border-slate-200 pt-1 font-semibold text-slate-900"><dt>Total</dt><dd>{formatCurrency(total)}</dd></div>
            </dl>
          </div>
        )}
      </div>
    </Modal>
  )
}

function InvoiceModal({ invoiceId, onClose, onChanged }) {
  const toast = useToast()
  const invoice = useApi(() => billingApi.invoice(invoiceId), [invoiceId])
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('upi')
  const [simulateFailure, setSimulateFailure] = useState(false)
  const [busy, setBusy] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)

  const pay = async (inv) => {
    setBusy(true)
    try {
      const payment = await billingApi.pay(inv.id, { amount: amount || inv.balance_due, method, simulate_failure: simulateFailure })
      if (payment.status === 'success') toast.success(`Payment ${payment.transaction_ref} recorded (simulated)`)
      else toast.error(`Payment declined (simulated) - ${payment.transaction_ref}`)
      setAmount('')
      invoice.reload()
      onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} size="xl" title={invoice.data ? `Invoice ${invoice.data.invoice_number}` : 'Invoice'}
      description={invoice.data ? `${invoice.data.patient_name} · ${invoice.data.patient_code}` : undefined}>
      <AsyncContent state={invoice}>
        {(inv) => (
          <div className="space-y-6">
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <DetailItem label="Issued">{formatDateTime(inv.issued_at)}</DetailItem>
              <DetailItem label="Due">{formatDate(inv.due_date)}</DetailItem>
              <DetailItem label="Status"><Badge status={inv.status} /></DetailItem>
              <DetailItem label="Balance due"><span className="font-semibold">{formatCurrency(inv.balance_due)}</span></DetailItem>
            </dl>
            <div className="overflow-hidden rounded-xl border border-slate-200">
              <DataTable dense rows={inv.items} columns={[
                { key: 'item_type', header: 'Type', render: (i) => titleCase(i.item_type) },
                { key: 'description', header: 'Description' },
                { key: 'quantity', header: 'Qty', align: 'right' },
                { key: 'unit_price', header: 'Unit price', align: 'right', render: (i) => formatCurrency(i.unit_price) },
                { key: 'line_total', header: 'Amount', align: 'right', render: (i) => formatCurrency(i.line_total) },
              ]} />
              <dl className="tabular space-y-1 border-t border-slate-200 bg-slate-50 px-4 py-3 text-sm">
                <div className="flex justify-between"><dt className="text-slate-500">Subtotal</dt><dd>{formatCurrency(inv.subtotal)}</dd></div>
                {inv.discount > 0 && <div className="flex justify-between"><dt className="text-slate-500">Discount</dt><dd>−{formatCurrency(inv.discount)}</dd></div>}
                {inv.tax > 0 && <div className="flex justify-between"><dt className="text-slate-500">Tax</dt><dd>{formatCurrency(inv.tax)}</dd></div>}
                <div className="flex justify-between font-semibold text-slate-900"><dt>Total</dt><dd>{formatCurrency(inv.total)}</dd></div>
                <div className="flex justify-between text-emerald-700"><dt>Paid</dt><dd>{formatCurrency(inv.amount_paid)}</dd></div>
              </dl>
            </div>

            {inv.payments.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">Payments</h3>
                <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 text-sm">
                  {inv.payments.map((p) => (
                    <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                      <span className="font-mono text-xs text-slate-500">{p.transaction_ref}</span>
                      <span className="text-slate-600">{titleCase(p.method)} · {formatDateTime(p.paid_at)}</span>
                      <span className="tabular font-medium">{formatCurrency(p.amount)}</span>
                      <Badge status={p.status} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {inv.balance_due > 0 && inv.status !== 'cancelled' && (
              <div className="rounded-xl border border-brand-100 bg-brand-50/50 p-4">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900"><CreditCard className="size-4 text-brand-600" aria-hidden="true" /> Record payment <span className="font-normal text-slate-500">(simulated - no real gateway)</span></h3>
                <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
                  <input type="number" min="0.01" step="0.01" max={inv.balance_due} className="input" placeholder={`Amount (max ${inv.balance_due})`} value={amount} onChange={(e) => setAmount(e.target.value)} aria-label="Payment amount" />
                  <select className="input" value={method} onChange={(e) => setMethod(e.target.value)} aria-label="Payment method">
                    {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{titleCase(m)}</option>)}
                  </select>
                  <button type="button" className="btn-primary" onClick={() => pay(inv)} disabled={busy}>{busy ? 'Processing…' : `Pay ${formatCurrency(amount || inv.balance_due)}`}</button>
                </div>
                <label className="mt-2 flex items-center gap-2 text-xs text-slate-600">
                  <input type="checkbox" className="accent-brand-600" checked={simulateFailure} onChange={(e) => setSimulateFailure(e.target.checked)} />
                  Simulate a declined payment
                </label>
              </div>
            )}

            {inv.status !== 'cancelled' && inv.amount_paid === 0 && (
              <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => setConfirmCancel(true)}>Cancel invoice</button>
            )}
            <ConfirmDialog open={confirmCancel} title="Cancel invoice?" confirmLabel="Cancel invoice"
              message="Its items become billable again on a new invoice."
              onClose={() => setConfirmCancel(false)}
              onConfirm={async () => {
                try { await billingApi.cancel(inv.id); toast.success('Invoice cancelled'); setConfirmCancel(false); invoice.reload(); onChanged() } catch (err) { toast.error(errorMessage(err)) }
              }} />
          </div>
        )}
      </AsyncContent>
    </Modal>
  )
}

function PaymentsTab() {
  const [page, setPage] = useState(1)
  const payments = useApi(() => billingApi.payments({ page, page_size: PAGE_SIZE }), [page])
  return (
    <div className="card overflow-hidden">
      <AsyncContent state={payments}>
        {(data) => (
          <>
            <DataTable rows={data.items} empty={<EmptyState icon={CreditCard} title="No payments yet" />} columns={[
              { key: 'paid_at', header: 'When', render: (p) => formatDateTime(p.paid_at), className: 'whitespace-nowrap' },
              { key: 'transaction_ref', header: 'Reference', render: (p) => <span className="font-mono text-xs">{p.transaction_ref}</span> },
              { key: 'invoice_number', header: 'Invoice', render: (p) => <span className="font-mono text-xs text-brand-700">{p.invoice_number}</span> },
              { key: 'patient_name', header: 'Patient' },
              { key: 'method', header: 'Method', render: (p) => titleCase(p.method) },
              { key: 'amount', header: 'Amount', align: 'right', render: (p) => formatCurrency(p.amount) },
              { key: 'status', header: 'Status', render: (p) => <Badge status={p.status} /> },
            ]} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
          </>
        )}
      </AsyncContent>
    </div>
  )
}

export default function BillingPage() {
  const [tab, setTab] = useState('invoices')
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [openInvoiceId, setOpenInvoiceId] = useState(null)
  const term = useDebounce(search.trim(), 300)
  const invoices = useApi(() => billingApi.invoices({ search: term, status, page, page_size: PAGE_SIZE }), [term, status, page])

  return (
    <>
      <PageHeader title="Billing" description="Invoices for consultations, medicines, rooms and diagnostics. Payments are simulated."
        actions={<button type="button" className="btn-primary" onClick={() => setCreating(true)}><FilePlus2 className="size-4" aria-hidden="true" /> New invoice</button>} />
      <div className="mb-4"><Tabs value={tab} onChange={setTab} tabs={[{ value: 'invoices', label: 'Invoices' }, { value: 'payments', label: 'Payments' }]} /></div>
      {tab === 'invoices' ? (
        <div className="card overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
            <label className="relative flex-1">
              <span className="sr-only">Search invoices</span>
              <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
              <input className="input pl-9" placeholder="Invoice number, patient name or Patient ID…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
            </label>
            <select className="input sm:w-48" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} aria-label="Filter by status">
              <option value="">All statuses</option>
              {['unpaid', 'partially_paid', 'paid', 'cancelled'].map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
            </select>
          </div>
          <AsyncContent state={invoices}>
            {(data) => (
              <>
                <DataTable rows={data.items} onRowClick={(inv) => setOpenInvoiceId(inv.id)} empty={<EmptyState icon={Receipt} title="No invoices found" />} columns={[
                  { key: 'invoice_number', header: 'Invoice', render: (i) => <span className="font-mono text-xs text-brand-700">{i.invoice_number}</span> },
                  { key: 'patient', header: 'Patient', render: (i) => <div><p className="font-medium text-slate-900">{i.patient_name}</p><p className="font-mono text-xs text-slate-500">{i.patient_code}</p></div> },
                  { key: 'issued_at', header: 'Issued', render: (i) => formatDate(i.issued_at), className: 'whitespace-nowrap' },
                  { key: 'total', header: 'Total', align: 'right', render: (i) => formatCurrency(i.total) },
                  { key: 'amount_paid', header: 'Paid', align: 'right', render: (i) => formatCurrency(i.amount_paid) },
                  { key: 'balance_due', header: 'Balance', align: 'right', render: (i) => <span className={i.balance_due > 0 ? 'font-medium text-slate-900' : 'text-slate-400'}>{formatCurrency(i.balance_due)}</span> },
                  { key: 'status', header: 'Status', render: (i) => <Badge status={i.status} /> },
                ]} />
                <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
              </>
            )}
          </AsyncContent>
        </div>
      ) : (
        <PaymentsTab />
      )}
      {creating && <NewInvoiceModal onClose={() => setCreating(false)} onCreated={(inv) => { invoices.reload(); setOpenInvoiceId(inv.id) }} />}
      {openInvoiceId && <InvoiceModal invoiceId={openInvoiceId} onClose={() => setOpenInvoiceId(null)} onChanged={invoices.reload} />}
    </>
  )
}
