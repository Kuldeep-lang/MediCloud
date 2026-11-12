import { ArrowLeft, EyeOff, Pencil, Phone } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { patientsApi } from '../api/endpoints'
import { PatientFormModal } from '../components/PatientFormModal'
import { DataTable } from '../components/ui/DataTable'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { Avatar, Badge, DetailItem, Tabs } from '../components/ui/primitives'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatDateTime, titleCase } from '../utils/format'

function Profile({ patient, canEdit, onEdit }) {
  return (
    <section className="card p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-4">
          <Avatar name={patient.full_name} size="size-14 text-base" />
          <div>
            <h1 className="text-xl font-semibold text-slate-900">{patient.full_name}</h1>
            <p className="font-mono text-sm text-brand-700">{patient.patient_code}</p>
          </div>
        </div>
        {canEdit && (
          <button type="button" className="btn-secondary" onClick={onEdit}>
            <Pencil className="size-4" aria-hidden="true" /> Edit details
          </button>
        )}
      </div>
      <dl className="mt-6 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        <DetailItem label="Age">{`${patient.age} years (${formatDate(patient.date_of_birth)})`}</DetailItem>
        <DetailItem label="Gender">{titleCase(patient.gender)}</DetailItem>
        <DetailItem label="Blood group">{patient.blood_group}</DetailItem>
        <DetailItem label="Allergies">{patient.allergies ?? 'None recorded'}</DetailItem>
        <DetailItem label="Phone">{patient.phone}</DetailItem>
        <DetailItem label="Email">{patient.email}</DetailItem>
        <DetailItem label="Address">{patient.address}</DetailItem>
        <DetailItem label="Emergency contact">
          {patient.emergency_contact_name && (
            <span className="flex items-center gap-1.5">
              {patient.emergency_contact_name}
              <Phone className="size-3 text-slate-400" aria-hidden="true" />
              {patient.emergency_contact_phone}
            </span>
          )}
        </DetailItem>
      </dl>
    </section>
  )
}

function History({ patientId }) {
  const [tab, setTab] = useState('appointments')
  const history = useApi(() => patientsApi.history(patientId), [patientId])
  return (
    <section className="card mt-4 overflow-hidden">
      <AsyncContent state={history}>
        {(data) => (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
              <Tabs
                value={tab}
                onChange={setTab}
                tabs={[
                  { value: 'appointments', label: 'Appointments', count: data.appointments.length },
                  ...(data.clinical_details_redacted
                    ? []
                    : [{ value: 'prescriptions', label: 'Prescriptions', count: data.prescriptions.length }]),
                  { value: 'admissions', label: 'Admissions', count: data.admissions.length },
                ]}
              />
              {data.clinical_details_redacted && (
                <p className="flex items-center gap-1.5 text-xs text-slate-500">
                  <EyeOff className="size-3.5" aria-hidden="true" /> Clinical notes hidden for your role
                </p>
              )}
            </div>
            {tab === 'appointments' && (
              <DataTable
                rows={data.appointments}
                empty={<EmptyState title="No appointments yet" />}
                columns={[
                  { key: 'when', header: 'Date', render: (a) => formatDateTime(a.scheduled_at), className: 'whitespace-nowrap' },
                  { key: 'doctor', header: 'Doctor', render: (a) => (
                    <div><p className="text-slate-800">{a.doctor_name}</p><p className="text-xs text-slate-500">{a.department_name}</p></div>
                  ) },
                  { key: 'reason', header: 'Reason', render: (a) => a.reason ?? '—' },
                  ...(data.clinical_details_redacted
                    ? []
                    : [{ key: 'diagnosis', header: 'Diagnosis / notes', render: (a) => (
                        <div className="max-w-xs"><p className="text-slate-800">{a.diagnosis ?? '—'}</p>{a.notes && <p className="text-xs text-slate-500">{a.notes}</p>}</div>
                      ) }]),
                  { key: 'status', header: 'Status', render: (a) => <Badge status={a.status} /> },
                ]}
              />
            )}
            {tab === 'prescriptions' && (
              <DataTable
                rows={data.prescriptions}
                empty={<EmptyState title="No prescriptions yet" />}
                columns={[
                  { key: 'created_at', header: 'Date', render: (p) => formatDate(p.created_at) },
                  { key: 'doctor_name', header: 'Prescribed by' },
                  { key: 'items', header: 'Medicines', render: (p) => (
                    <ul className="text-xs text-slate-600">{p.items.map((i) => <li key={i.id}>{i.medicine_name} · {i.dosage} · {i.frequency} · ×{i.quantity}</li>)}</ul>
                  ) },
                  { key: 'status', header: 'Status', render: (p) => <Badge status={p.status} /> },
                ]}
              />
            )}
            {tab === 'admissions' && (
              <DataTable
                rows={data.admissions}
                empty={<EmptyState title="No admissions recorded" />}
                columns={[
                  { key: 'admitted_at', header: 'Admitted', render: (a) => formatDateTime(a.admitted_at), className: 'whitespace-nowrap' },
                  { key: 'discharged_at', header: 'Discharged', render: (a) => formatDateTime(a.discharged_at), className: 'whitespace-nowrap' },
                  { key: 'bed', header: 'Ward / bed', render: (a) => `${a.ward_name} · ${a.bed_number}` },
                  { key: 'reason', header: 'Reason' },
                  { key: 'status', header: 'Status', render: (a) => <Badge status={a.status} /> },
                ]}
              />
            )}
          </>
        )}
      </AsyncContent>
    </section>
  )
}

export default function PatientDetailPage() {
  const { patientId } = useParams()
  const { hasRole } = useAuth()
  const [editing, setEditing] = useState(false)
  const patient = useApi(() => patientsApi.get(patientId), [patientId])

  return (
    <>
      <Link to="/patients" className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-brand-700">
        <ArrowLeft className="size-4" aria-hidden="true" /> All patients
      </Link>
      <AsyncContent state={patient}>
        {(data) => (
          <>
            <Profile patient={data} canEdit={hasRole('admin', 'receptionist')} onEdit={() => setEditing(true)} />
            {hasRole('admin', 'doctor', 'receptionist') && <History patientId={patientId} />}
            {editing && (
              <PatientFormModal open patient={data} onClose={() => setEditing(false)} onSaved={patient.reload} />
            )}
          </>
        )}
      </AsyncContent>
    </>
  )
}
