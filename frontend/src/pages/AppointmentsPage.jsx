import { CalendarClock, CalendarPlus, Search } from 'lucide-react'
import { useState } from 'react'

import { errorMessage } from '../api/client'
import { appointmentsApi, departmentsApi, doctorsApi } from '../api/endpoints'
import { PatientPicker } from '../components/PatientPicker'
import { SlotPicker } from '../components/SlotPicker'
import { DataTable, Pagination } from '../components/ui/DataTable'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { ConfirmDialog, Modal } from '../components/ui/Modal'
import { Badge, Field, PageHeader } from '../components/ui/primitives'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useApi } from '../hooks/useApi'
import { useDebounce } from '../hooks/useDebounce'
import { formatDate, formatTime, localDateOf, titleCase, todayLocal } from '../utils/format'

const STATUSES = ['scheduled', 'confirmed', 'completed', 'cancelled', 'no_show']
const PAGE_SIZE = 20

function DoctorSelect({ value, onChange, departmentId, id }) {
  const doctors = useApi(() => doctorsApi.list({ department_id: departmentId, page_size: 100 }), [departmentId])
  return (
    <select id={id} className="input" value={value ?? ''} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">Select a doctor…</option>
      {(doctors.data?.items ?? []).map((d) => (
        <option key={d.id} value={d.id}>
          {d.full_name} — {d.specialization}
        </option>
      ))}
    </select>
  )
}

function BookAppointmentModal({ onClose, onBooked }) {
  const toast = useToast()
  const departments = useApi(() => departmentsApi.list(), [])
  const [patient, setPatient] = useState(null)
  const [departmentId, setDepartmentId] = useState('')
  const [doctorId, setDoctorId] = useState(null)
  const [date, setDate] = useState(todayLocal(1))
  const [slot, setSlot] = useState(null)
  const [duration, setDuration] = useState(20)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await appointmentsApi.create({
        patient_id: patient.id,
        doctor_id: doctorId,
        scheduled_at: slot,
        duration_minutes: duration,
        reason: reason || null,
      })
      toast.success(`Appointment booked for ${patient.full_name}`)
      onBooked()
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
      title="Book appointment"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn-primary" onClick={submit} disabled={busy || !patient || !doctorId || !slot}>
            {busy ? 'Booking…' : 'Book appointment'}
          </button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-2">{error}</p>}
        <Field label="Patient" required className="sm:col-span-2">
          {(id) => <PatientPicker id={id} value={patient} onChange={setPatient} />}
        </Field>
        <Field label="Department">
          {(id) => (
            <select id={id} className="input" value={departmentId} onChange={(e) => { setDepartmentId(e.target.value); setDoctorId(null); setSlot(null) }}>
              <option value="">All departments</option>
              {(departments.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
        </Field>
        <Field label="Doctor" required>
          {(id) => <DoctorSelect id={id} departmentId={departmentId} value={doctorId} onChange={(v) => { setDoctorId(v); setSlot(null) }} />}
        </Field>
        <Field label="Date" required>
          {(id) => <input id={id} type="date" className="input" min={todayLocal()} value={date} onChange={(e) => { setDate(e.target.value); setSlot(null) }} />}
        </Field>
        <Field label="Duration">
          {(id) => (
            <select id={id} className="input" value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
              {[15, 20, 30, 45, 60].map((m) => <option key={m} value={m}>{m} minutes</option>)}
            </select>
          )}
        </Field>
        <div className="sm:col-span-2">
          <p className="label">Time slot *</p>
          <SlotPicker doctorId={doctorId} date={date} value={slot} onChange={setSlot} />
        </div>
        <Field label="Reason for visit" className="sm:col-span-2">
          {(id) => <input id={id} className="input" maxLength={255} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Follow-up consultation" />}
        </Field>
      </div>
    </Modal>
  )
}

function RescheduleModal({ appointment, onClose, onSaved }) {
  const toast = useToast()
  const [doctorId, setDoctorId] = useState(appointment.doctor_id)
  const [date, setDate] = useState(todayLocal(1))
  const [slot, setSlot] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await appointmentsApi.update(appointment.id, { doctor_id: doctorId, scheduled_at: slot })
      toast.success('Appointment rescheduled')
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
      title="Reschedule appointment"
      description={`${appointment.patient_name} · currently ${formatDate(appointment.scheduled_at)} ${formatTime(appointment.scheduled_at)}`}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>Back</button>
          <button type="button" className="btn-primary" onClick={submit} disabled={busy || !slot}>{busy ? 'Saving…' : 'Reschedule'}</button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <Field label="Doctor">{(id) => <DoctorSelect id={id} value={doctorId} onChange={(v) => { setDoctorId(v); setSlot(null) }} />}</Field>
        <Field label="New date">{(id) => <input id={id} type="date" className="input" min={todayLocal()} value={date} onChange={(e) => { setDate(e.target.value); setSlot(null) }} />}</Field>
        <SlotPicker doctorId={doctorId} date={date} value={slot} onChange={setSlot} />
      </div>
    </Modal>
  )
}

function CompleteModal({ appointment, onClose, onSaved }) {
  const toast = useToast()
  const [diagnosis, setDiagnosis] = useState(appointment.diagnosis ?? '')
  const [notes, setNotes] = useState(appointment.notes ?? '')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try {
      await appointmentsApi.setStatus(appointment.id, { status: 'completed', diagnosis: diagnosis || null, notes: notes || null })
      toast.success('Visit marked completed')
      onSaved()
      onClose()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      open
      onClose={onClose}
      title="Complete visit"
      description={appointment.patient_name}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>Back</button>
          <button type="button" className="btn-primary" onClick={submit} disabled={busy}>{busy ? 'Saving…' : 'Mark completed'}</button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Diagnosis">{(id) => <input id={id} className="input" value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} />}</Field>
        <Field label="Clinical notes">{(id) => <textarea id={id} className="input min-h-24" value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      </div>
    </Modal>
  )
}

export default function AppointmentsPage() {
  const { hasRole } = useAuth()
  const toast = useToast()
  const isDesk = hasRole('admin', 'receptionist')
  const isClinician = hasRole('admin', 'doctor')
  const [date, setDate] = useState(todayLocal())
  const [status, setStatus] = useState('')
  const [doctorId, setDoctorId] = useState(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState(null) // { type, appointment }
  const term = useDebounce(search.trim(), 300)

  const appointments = useApi(
    () => appointmentsApi.list({ date, status, doctor_id: doctorId, search: term, page, page_size: PAGE_SIZE }),
    [date, status, doctorId, term, page],
  )
  const close = () => setModal(null)
  const today = todayLocal()

  const quickStatus = async (appointment, next) => {
    try {
      await appointmentsApi.setStatus(appointment.id, { status: next })
      toast.success(`Marked ${titleCase(next).toLowerCase()}`)
      appointments.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  const actions = (a) => {
    const active = a.status === 'scheduled' || a.status === 'confirmed'
    if (!active) return null
    const isPastOrToday = localDateOf(a.scheduled_at) <= today
    return (
      <div className="flex flex-wrap justify-end gap-1">
        {isDesk && a.status === 'scheduled' && (
          <button type="button" className="btn-secondary btn-sm" onClick={() => quickStatus(a, 'confirmed')}>Confirm</button>
        )}
        {isClinician && isPastOrToday && (
          <button type="button" className="btn-primary btn-sm" onClick={() => setModal({ type: 'complete', appointment: a })}>Complete</button>
        )}
        {isDesk && isPastOrToday && (
          <button type="button" className="btn-ghost btn-sm" onClick={() => quickStatus(a, 'no_show')}>No-show</button>
        )}
        {isDesk && (
          <>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setModal({ type: 'reschedule', appointment: a })}>Reschedule</button>
            <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => setModal({ type: 'cancel', appointment: a })}>Cancel</button>
          </>
        )}
      </div>
    )
  }

  const columns = [
    {
      key: 'time',
      header: 'Time',
      className: 'whitespace-nowrap',
      render: (a) => (
        <div>
          <p className="tabular font-medium text-slate-900">{formatTime(a.scheduled_at)}</p>
          <p className="text-xs text-slate-500">{a.duration_minutes} min</p>
        </div>
      ),
    },
    {
      key: 'patient',
      header: 'Patient',
      render: (a) => (
        <div>
          <p className="font-medium text-slate-900">{a.patient_name}</p>
          <p className="font-mono text-xs text-slate-500">{a.patient_code}</p>
        </div>
      ),
    },
    {
      key: 'doctor',
      header: 'Doctor',
      render: (a) => (
        <div>
          <p className="text-slate-800">{a.doctor_name}</p>
          <p className="text-xs text-slate-500">{a.department_name}</p>
        </div>
      ),
    },
    { key: 'reason', header: 'Reason', render: (a) => <span className="text-slate-600">{a.reason ?? '—'}</span> },
    { key: 'status', header: 'Status', render: (a) => <Badge status={a.status} /> },
    { key: 'actions', header: <span className="sr-only">Actions</span>, align: 'right', render: actions },
  ]

  return (
    <>
      <PageHeader
        title="Appointments"
        description="Book, reschedule and track appointments."
        actions={
          isDesk && (
            <button type="button" className="btn-primary" onClick={() => setModal({ type: 'book' })}>
              <CalendarPlus className="size-4" aria-hidden="true" /> Book appointment
            </button>
          )
        }
      />
      <div className="card overflow-hidden">
        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <input type="date" className="input" value={date} onChange={(e) => { setDate(e.target.value); setPage(1) }} aria-label="Date" />
          <select className="input" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} aria-label="Filter by status">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </select>
          {!hasRole('doctor') && (
            <DoctorSelect value={doctorId} onChange={(v) => { setDoctorId(v); setPage(1) }} />
          )}
          <label className="relative">
            <span className="sr-only">Search patient</span>
            <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
            <input className="input pl-9" placeholder="Patient name or ID…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
          </label>
        </div>
        <AsyncContent state={appointments}>
          {(data) => (
            <>
              <DataTable
                columns={columns}
                rows={data.items}
                empty={<EmptyState icon={CalendarClock} title="No appointments for this day" description="Pick another date or clear the filters." />}
              />
              <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
            </>
          )}
        </AsyncContent>
      </div>

      {modal?.type === 'book' && <BookAppointmentModal onClose={close} onBooked={appointments.reload} />}
      {modal?.type === 'reschedule' && <RescheduleModal appointment={modal.appointment} onClose={close} onSaved={appointments.reload} />}
      {modal?.type === 'complete' && <CompleteModal appointment={modal.appointment} onClose={close} onSaved={appointments.reload} />}
      <ConfirmDialog
        open={modal?.type === 'cancel'}
        title="Cancel appointment?"
        message={modal?.appointment ? `Cancel ${modal.appointment.patient_name}'s appointment with ${modal.appointment.doctor_name}? The slot becomes free again.` : ''}
        confirmLabel="Cancel appointment"
        inputLabel="Reason (optional)"
        onClose={close}
        onConfirm={async (reason) => {
          try {
            await appointmentsApi.cancel(modal.appointment.id, reason)
            toast.success('Appointment cancelled')
            appointments.reload()
            close()
          } catch (err) {
            toast.error(errorMessage(err))
          }
        }}
      />
    </>
  )
}
