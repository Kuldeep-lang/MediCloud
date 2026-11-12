import { Clock, Plus, Search, Stethoscope, UserMinus } from 'lucide-react'
import { useState } from 'react'

import { errorMessage } from '../api/client'
import { departmentsApi, doctorsApi } from '../api/endpoints'
import { ScheduleEditor, ScheduleSummary } from '../components/ScheduleEditor'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { ConfirmDialog, Modal } from '../components/ui/Modal'
import { Avatar, Badge, DetailItem, Field, PageHeader } from '../components/ui/primitives'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { useDebounce } from '../hooks/useDebounce'
import { formatCurrency, formatTime, todayLocal } from '../utils/format'
import { toApiBlocks, WEEKDAY_PRESET } from '../utils/schedule'

const EMPTY_DOCTOR = {
  first_name: '',
  last_name: '',
  specialization: '',
  department_id: '',
  license_number: '',
  email: '',
  phone: '',
  consultation_fee: '800',
  years_experience: '5',
}

function DoctorFormModal({ departments, onClose, onSaved }) {
  const toast = useToast()
  const [values, setValues] = useState({ ...EMPTY_DOCTOR, department_id: departments[0]?.id ?? '' })
  const [blocks, setBlocks] = useState(WEEKDAY_PRESET)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setValues((v) => ({ ...v, [key]: e.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const doctor = await doctorsApi.create({
        ...values,
        department_id: Number(values.department_id),
        years_experience: Number(values.years_experience),
        schedules: toApiBlocks(blocks),
      })
      toast.success(`${doctor.full_name} added`)
      onSaved()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Add doctor"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" form="doctor-form" className="btn-primary" disabled={busy}>
            {busy ? 'Saving…' : 'Add doctor'}
          </button>
        </>
      }
    >
      <form id="doctor-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-2">{error}</p>}
        <Field label="First name" required>{(id) => <input id={id} className="input" required value={values.first_name} onChange={set('first_name')} />}</Field>
        <Field label="Last name" required>{(id) => <input id={id} className="input" required value={values.last_name} onChange={set('last_name')} />}</Field>
        <Field label="Department" required>
          {(id) => (
            <select id={id} className="input" value={values.department_id} onChange={set('department_id')}>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
        </Field>
        <Field label="Specialization" required>{(id) => <input id={id} className="input" required value={values.specialization} onChange={set('specialization')} />}</Field>
        <Field label="Licence number" required hint="e.g. NMC-2018-10452">{(id) => <input id={id} className="input" required value={values.license_number} onChange={set('license_number')} />}</Field>
        <Field label="Email" required>{(id) => <input id={id} type="email" className="input" required value={values.email} onChange={set('email')} />}</Field>
        <Field label="Phone" required>{(id) => <input id={id} className="input" required value={values.phone} onChange={set('phone')} />}</Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Fee">{(id) => <input id={id} type="number" min="0" step="50" className="input" value={values.consultation_fee} onChange={set('consultation_fee')} />}</Field>
          <Field label="Experience (yrs)">{(id) => <input id={id} type="number" min="0" max="70" className="input" value={values.years_experience} onChange={set('years_experience')} />}</Field>
        </div>
        <div className="sm:col-span-2">
          <p className="label">Availability schedule</p>
          <ScheduleEditor blocks={blocks} onChange={setBlocks} />
        </div>
      </form>
    </Modal>
  )
}

function DoctorDetailModal({ doctor, onClose, onChanged }) {
  const { user, hasRole } = useAuth()
  const toast = useToast()
  const canEditSchedule = hasRole('admin') || user.doctor_id === doctor.id
  const canSeeAppointments = hasRole('admin', 'receptionist') || user.doctor_id === doctor.id
  const [editing, setEditing] = useState(false)
  const [blocks, setBlocks] = useState(doctor.schedules ?? [])
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const today = useApi(() => doctorsApi.appointments(doctor.id, { date: todayLocal(), page_size: 50 }), [doctor.id], {
    enabled: canSeeAppointments,
  })

  const saveSchedule = async () => {
    setBusy(true)
    try {
      await doctorsApi.setSchedules(doctor.id, toApiBlocks(blocks))
      toast.success('Schedule updated')
      setEditing(false)
      onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const deactivate = async () => {
    try {
      await doctorsApi.deactivate(doctor.id)
      toast.success(`${doctor.full_name} removed from active staff`)
      onChanged()
      onClose()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <Modal open onClose={onClose} size="lg" title={doctor.full_name} description={`${doctor.specialization} · ${doctor.department_name}`}>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <DetailItem label="Licence">{doctor.license_number}</DetailItem>
        <DetailItem label="Fee">{formatCurrency(doctor.consultation_fee)}</DetailItem>
        <DetailItem label="Experience">{`${doctor.years_experience} years`}</DetailItem>
        <DetailItem label="Status"><Badge tone={doctor.is_active ? 'good' : 'neutral'}>{doctor.is_active ? 'Active' : 'Inactive'}</Badge></DetailItem>
        <DetailItem label="Email">{doctor.email}</DetailItem>
        <DetailItem label="Phone">{doctor.phone}</DetailItem>
      </dl>

      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Weekly schedule</h3>
          {canEditSchedule && !editing && (
            <button type="button" className="btn-secondary btn-sm" onClick={() => setEditing(true)}>
              <Clock className="size-3.5" aria-hidden="true" /> Edit schedule
            </button>
          )}
        </div>
        {editing ? (
          <>
            <ScheduleEditor blocks={blocks} onChange={setBlocks} />
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" className="btn-secondary btn-sm" onClick={() => { setBlocks(doctor.schedules); setEditing(false) }}>Cancel</button>
              <button type="button" className="btn-primary btn-sm" onClick={saveSchedule} disabled={busy}>{busy ? 'Saving…' : 'Save schedule'}</button>
            </div>
          </>
        ) : (
          <ScheduleSummary schedules={doctor.schedules} />
        )}
      </div>

      {canSeeAppointments && (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Today&apos;s appointments</h3>
          <AsyncContent state={today} isEmpty={(d) => !d.items.length} empty={<p className="text-sm text-slate-500">No appointments today.</p>}>
            {(data) => (
              <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100">
                {data.items.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <span className="tabular font-medium">{formatTime(a.scheduled_at)}</span>
                    <span className="flex-1 truncate">{a.patient_name}</span>
                    <Badge status={a.status} />
                  </li>
                ))}
              </ul>
            )}
          </AsyncContent>
        </div>
      )}

      {hasRole('admin') && doctor.is_active && (
        <div className="mt-6 border-t border-slate-100 pt-4">
          <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => setConfirmOpen(true)}>
            <UserMinus className="size-4" aria-hidden="true" /> Remove doctor
          </button>
        </div>
      )}
      <ConfirmDialog
        open={confirmOpen}
        title="Remove doctor?"
        message={`${doctor.full_name} will no longer be bookable. Their appointment and prescription history is kept.`}
        confirmLabel="Remove"
        onConfirm={deactivate}
        onClose={() => setConfirmOpen(false)}
      />
    </Modal>
  )
}

export default function DoctorsPage() {
  const { hasRole, user } = useAuth()
  const [search, setSearch] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [adding, setAdding] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const term = useDebounce(search.trim(), 300)

  const departments = useApi(() => departmentsApi.list(), [])
  const doctors = useApi(
    () => doctorsApi.list({ search: term, department_id: departmentId, include_inactive: includeInactive, page_size: 100 }),
    [term, departmentId, includeInactive],
  )
  const selected = useApi(() => doctorsApi.get(selectedId), [selectedId], { enabled: Boolean(selectedId) })

  return (
    <>
      <PageHeader
        title="Doctors"
        description="Profiles, departments and weekly availability."
        actions={
          hasRole('admin') && (
            <button type="button" className="btn-primary" onClick={() => setAdding(true)} disabled={!departments.data}>
              <Plus className="size-4" aria-hidden="true" /> Add doctor
            </button>
          )
        }
      />
      <div className="card mb-4 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <label className="relative flex-1">
          <span className="sr-only">Search doctors</span>
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
          <input className="input pl-9" placeholder="Search by name, specialization or licence…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <select className="input sm:w-56" value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} aria-label="Filter by department">
          <option value="">All departments</option>
          {(departments.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        {hasRole('admin') && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={includeInactive} onChange={(e) => setIncludeInactive(e.target.checked)} className="accent-brand-600" />
            Show inactive
          </label>
        )}
      </div>

      <AsyncContent
        state={doctors}
        isEmpty={(d) => !d.items.length}
        empty={<div className="card"><EmptyState icon={Stethoscope} title="No doctors found" /></div>}
      >
        {(data) => (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((doctor) => (
              <button
                key={doctor.id}
                type="button"
                onClick={() => setSelectedId(doctor.id)}
                className={`card p-5 text-left transition-shadow hover:shadow-lg ${user.doctor_id === doctor.id ? 'ring-2 ring-brand-300' : ''} ${doctor.is_active ? '' : 'opacity-60'}`}
              >
                <div className="flex items-start gap-3">
                  <Avatar name={doctor.full_name} size="size-11" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-slate-900">{doctor.full_name}</p>
                    <p className="truncate text-sm text-slate-500">{doctor.specialization}</p>
                  </div>
                  {!doctor.is_active && <Badge tone="neutral">Inactive</Badge>}
                </div>
                <div className="mt-4 flex items-center justify-between text-xs">
                  <Badge tone="brand">{doctor.department_name}</Badge>
                  <span className="text-slate-500">{doctor.years_experience} yrs · {formatCurrency(doctor.consultation_fee)}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </AsyncContent>

      {adding && departments.data && (
        <DoctorFormModal departments={departments.data} onClose={() => setAdding(false)} onSaved={doctors.reload} />
      )}
      {selectedId && selected.data && selected.data.id === selectedId && (
        <DoctorDetailModal
          key={selected.data.id}
          doctor={selected.data}
          onClose={() => setSelectedId(null)}
          onChanged={() => {
            doctors.reload()
            selected.reload()
          }}
        />
      )}
    </>
  )
}
