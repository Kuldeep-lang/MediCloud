import { BedDouble, BedSingle, Plus, User, Wrench } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { errorMessage } from '../api/client'
import { admissionsApi, bedsApi, doctorsApi } from '../api/endpoints'
import { PatientPicker } from '../components/PatientPicker'
import { DataTable, Pagination } from '../components/ui/DataTable'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { ConfirmDialog, Modal } from '../components/ui/Modal'
import { Badge, DetailItem, Field, PageHeader, Tabs } from '../components/ui/primitives'
import { StatCard } from '../components/ui/StatCard'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { formatCurrency, formatDateTime, titleCase } from '../utils/format'

const TILE = {
  available: { cls: 'border-emerald-200 bg-emerald-50/60 hover:border-emerald-400', icon: BedSingle, iconCls: 'text-emerald-600' },
  occupied: { cls: 'border-brand-200 bg-brand-50 hover:border-brand-400', icon: User, iconCls: 'text-brand-600' },
  maintenance: { cls: 'border-amber-200 bg-amber-50 hover:border-amber-400', icon: Wrench, iconCls: 'text-amber-600' },
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-slate-600" aria-label="Bed status legend">
      {Object.entries(TILE).map(([status, { icon: Icon, iconCls }]) => (
        <span key={status} className="flex items-center gap-1.5">
          <Icon className={`size-3.5 ${iconCls}`} aria-hidden="true" /> {titleCase(status)}
        </span>
      ))}
    </div>
  )
}

function BedModal({ bed, onClose, onChanged }) {
  const { hasRole } = useAuth()
  const toast = useToast()
  const [patient, setPatient] = useState(null)
  const [doctorId, setDoctorId] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [confirmDischarge, setConfirmDischarge] = useState(false)
  const doctors = useApi(() => doctorsApi.list({ page_size: 100 }), [], { enabled: bed.status === 'available' })
  const canAdmit = hasRole('admin', 'receptionist')

  const run = async (action, message) => {
    setBusy(true)
    setError(null)
    try {
      await action()
      toast.success(message)
      onChanged()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const admit = () =>
    run(
      () => admissionsApi.admit({ patient_id: patient.id, bed_id: bed.id, admitting_doctor_id: doctorId ? Number(doctorId) : null, reason }),
      `${patient.full_name} admitted to ${bed.bed_number}`,
    )

  return (
    <Modal open onClose={onClose} title={`Bed ${bed.bed_number}`} description={`${bed.ward_name} · ${titleCase(bed.ward_type)}`}
      footer={
        bed.status === 'available' && canAdmit ? (
          <>
            <button type="button" className="btn-secondary" onClick={onClose}>Close</button>
            <button type="button" className="btn-primary" onClick={admit} disabled={busy || !patient || reason.trim().length < 3}>
              {busy ? 'Admitting…' : 'Admit patient'}
            </button>
          </>
        ) : null
      }
    >
      {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="mb-4"><Badge status={bed.status} /></div>

      {bed.status === 'available' && (
        canAdmit ? (
          <div className="space-y-4">
            <Field label="Patient" required>{(id) => <PatientPicker id={id} value={patient} onChange={setPatient} />}</Field>
            <Field label="Admitting doctor">
              {(id) => (
                <select id={id} className="input" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
                  <option value="">Not specified</option>
                  {(doctors.data?.items ?? []).map((d) => <option key={d.id} value={d.id}>{d.full_name} — {d.department_name}</option>)}
                </select>
              )}
            </Field>
            <Field label="Reason for admission" required>
              {(id) => <textarea id={id} className="input min-h-20" value={reason} onChange={(e) => setReason(e.target.value)} />}
            </Field>
            {hasRole('admin') && (
              <button type="button" className="btn-ghost btn-sm text-amber-700" disabled={busy}
                onClick={() => run(() => bedsApi.setStatus(bed.id, 'maintenance'), `${bed.bed_number} marked under maintenance`)}>
                <Wrench className="size-3.5" aria-hidden="true" /> Mark under maintenance
              </button>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-600">This bed is free.</p>
        )
      )}

      {bed.status === 'occupied' && (
        <>
          <dl className="grid grid-cols-2 gap-4">
            <DetailItem label="Patient">{bed.current_patient_name}</DetailItem>
            <DetailItem label="Patient ID">{bed.current_patient_code}</DetailItem>
            <DetailItem label="Admitted">{formatDateTime(bed.admitted_at)}</DetailItem>
          </dl>
          <div className="mt-6 flex gap-2">
            <button type="button" className="btn-primary" onClick={() => setConfirmDischarge(true)}>Discharge patient</button>
          </div>
          <ConfirmDialog
            open={confirmDischarge}
            tone="primary"
            title="Discharge patient?"
            message={`${bed.current_patient_name} will be discharged and ${bed.bed_number} becomes available.`}
            confirmLabel="Discharge"
            inputLabel="Discharge summary (optional)"
            onClose={() => setConfirmDischarge(false)}
            onConfirm={(summary) => run(() => admissionsApi.discharge(bed.current_admission_id, summary), `${bed.current_patient_name} discharged`)}
          />
        </>
      )}

      {bed.status === 'maintenance' && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">This bed is out of service.</p>
          {hasRole('admin') && (
            <button type="button" className="btn-primary" disabled={busy}
              onClick={() => run(() => bedsApi.setStatus(bed.id, 'available'), `${bed.bed_number} is available again`)}>
              Mark available
            </button>
          )}
        </div>
      )}
    </Modal>
  )
}

function AddBedModal({ wards, onClose, onSaved }) {
  const toast = useToast()
  const [wardId, setWardId] = useState(wards[0]?.id ?? '')
  const [bedNumber, setBedNumber] = useState('')
  const [error, setError] = useState(null)
  const submit = async () => {
    try {
      await bedsApi.create({ ward_id: Number(wardId), bed_number: bedNumber })
      toast.success(`Bed ${bedNumber.toUpperCase()} added`)
      onSaved()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    }
  }
  return (
    <Modal open onClose={onClose} size="sm" title="Add bed"
      footer={<><button type="button" className="btn-secondary" onClick={onClose}>Cancel</button><button type="button" className="btn-primary" onClick={submit} disabled={!bedNumber}>Add bed</button></>}>
      <div className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <Field label="Ward">{(id) => <select id={id} className="input" value={wardId} onChange={(e) => setWardId(e.target.value)}>{wards.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>}</Field>
        <Field label="Bed number" hint="Letters, digits and dashes, e.g. GA-31">{(id) => <input id={id} className="input" value={bedNumber} onChange={(e) => setBedNumber(e.target.value)} maxLength={10} />}</Field>
      </div>
    </Modal>
  )
}

function AdmissionsTab() {
  const [status, setStatus] = useState('admitted')
  const [page, setPage] = useState(1)
  const admissions = useApi(() => admissionsApi.list({ status, page, page_size: 15 }), [status, page])
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-slate-100 p-4">
        <select className="input sm:w-56" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} aria-label="Filter admissions">
          <option value="admitted">Currently admitted</option>
          <option value="discharged">Discharged</option>
          <option value="">All admissions</option>
        </select>
      </div>
      <AsyncContent state={admissions}>
        {(data) => (
          <>
            <DataTable
              rows={data.items}
              empty={<EmptyState icon={BedDouble} title="No admissions" />}
              columns={[
                { key: 'patient', header: 'Patient', render: (a) => <Link to={`/patients/${a.patient_id}`} className="font-medium text-slate-900 hover:text-brand-700">{a.patient_name}<span className="ml-2 font-mono text-xs text-slate-400">{a.patient_code}</span></Link> },
                { key: 'bed', header: 'Ward / bed', render: (a) => `${a.ward_name} · ${a.bed_number}` },
                { key: 'doctor_name', header: 'Doctor', render: (a) => a.doctor_name ?? '—' },
                { key: 'admitted_at', header: 'Admitted', render: (a) => formatDateTime(a.admitted_at), className: 'whitespace-nowrap' },
                { key: 'discharged_at', header: 'Discharged', render: (a) => formatDateTime(a.discharged_at), className: 'whitespace-nowrap' },
                { key: 'status', header: 'Status', render: (a) => <Badge status={a.status} /> },
              ]}
            />
            <Pagination page={page} pageSize={15} total={data.total} onChange={setPage} />
          </>
        )}
      </AsyncContent>
    </div>
  )
}

export default function BedsPage() {
  const { hasRole } = useAuth()
  const [tab, setTab] = useState('board')
  const [selectedBed, setSelectedBed] = useState(null)
  const [addingBed, setAddingBed] = useState(false)
  const occupancy = useApi(() => bedsApi.occupancy(), [])
  const beds = useApi(() => bedsApi.list(), [])
  const reload = () => {
    occupancy.reload()
    beds.reload()
  }

  const o = occupancy.data
  const icu = o?.by_ward_type.icu
  const general = o?.by_ward_type.general

  return (
    <>
      <PageHeader
        title="Beds & Wards"
        description="Real-time bed occupancy, allocation and discharge."
        actions={hasRole('admin') && o && (
          <button type="button" className="btn-secondary" onClick={() => setAddingBed(true)}>
            <Plus className="size-4" aria-hidden="true" /> Add bed
          </button>
        )}
      />
      {o && (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Overall occupancy" value={`${o.overall.occupancy_rate}%`} hint={`${o.overall.occupied} of ${o.overall.total} beds occupied`} icon={BedDouble} accent="navy" />
          <StatCard label="ICU beds available" value={icu ? `${icu.available} / ${icu.total}` : '—'} hint={icu ? `${icu.occupancy_rate}% occupied` : undefined} icon={BedSingle} accent={icu && icu.available <= 2 ? 'critical' : 'good'} />
          <StatCard label="General ward available" value={general ? `${general.available} / ${general.total}` : '—'} hint={general ? `${general.occupancy_rate}% occupied` : undefined} icon={BedSingle} accent="good" />
          <StatCard label="Under maintenance" value={o.overall.maintenance} hint="Out of service" icon={Wrench} accent="warning" />
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={tab} onChange={setTab} tabs={[{ value: 'board', label: 'Bed board' }, { value: 'admissions', label: 'Admissions' }]} />
        {tab === 'board' && <Legend />}
      </div>

      {tab === 'board' ? (
        <AsyncContent state={beds}>
          {(allBeds) => (
            <div className="space-y-4">
              {(o?.wards ?? []).map((ward) => {
                const wardBeds = allBeds.filter((b) => b.ward_id === ward.id)
                return (
                  <section key={ward.id} className="card p-5">
                    <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-slate-900">{ward.name}</h2>
                        <Badge tone={ward.ward_type === 'icu' ? 'critical' : 'brand'}>{ward.ward_type === 'icu' ? 'ICU' : titleCase(ward.ward_type)}</Badge>
                      </div>
                      <p className="text-xs text-slate-500">
                        Floor {ward.floor ?? '—'} · {formatCurrency(ward.daily_rate)}/day ·{' '}
                        <span className="font-medium text-slate-700">{ward.occupied_beds}/{ward.total_beds} occupied</span>
                      </p>
                    </header>
                    <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 md:grid-cols-6 xl:grid-cols-10">
                      {wardBeds.map((bed) => {
                        const tile = TILE[bed.status]
                        const Icon = tile.icon
                        return (
                          <button
                            key={bed.id}
                            type="button"
                            onClick={() => setSelectedBed(bed)}
                            className={`flex flex-col items-start rounded-xl border p-2 text-left transition-colors ${tile.cls}`}
                            aria-label={`Bed ${bed.bed_number}, ${bed.status}${bed.current_patient_name ? `, ${bed.current_patient_name}` : ''}`}
                          >
                            <span className="flex w-full items-center justify-between">
                              <span className="text-xs font-semibold text-slate-800">{bed.bed_number}</span>
                              <Icon className={`size-3.5 ${tile.iconCls}`} aria-hidden="true" />
                            </span>
                            <span className="mt-1 w-full truncate text-[11px] text-slate-500">
                              {bed.current_patient_name ?? titleCase(bed.status)}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </section>
                )
              })}
            </div>
          )}
        </AsyncContent>
      ) : (
        <AdmissionsTab />
      )}

      {selectedBed && <BedModal key={selectedBed.id} bed={selectedBed} onClose={() => setSelectedBed(null)} onChanged={reload} />}
      {addingBed && o && <AddBedModal wards={o.wards} onClose={() => setAddingBed(false)} onSaved={reload} />}
    </>
  )
}
