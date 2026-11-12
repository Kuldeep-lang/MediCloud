import { Search, UserPlus, Users } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { patientsApi } from '../api/endpoints'
import { PatientFormModal } from '../components/PatientFormModal'
import { DataTable, Pagination } from '../components/ui/DataTable'
import { AsyncContent, EmptyState } from '../components/ui/feedback'
import { PageHeader } from '../components/ui/primitives'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import { useDebounce } from '../hooks/useDebounce'
import { BLOOD_GROUPS, GENDERS } from '../utils/constants'
import { formatDate, titleCase } from '../utils/format'

const PAGE_SIZE = 15

export default function PatientsPage() {
  const { hasRole } = useAuth()
  const navigate = useNavigate()
  const canRegister = hasRole('admin', 'receptionist')
  const [search, setSearch] = useState('')
  const [gender, setGender] = useState('')
  const [bloodGroup, setBloodGroup] = useState('')
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const term = useDebounce(search.trim(), 300)

  const patients = useApi(
    () => patientsApi.list({ search: term, gender, blood_group: bloodGroup, page, page_size: PAGE_SIZE }),
    [term, gender, bloodGroup, page],
  )
  const resetPage = (setter) => (event) => {
    setter(event.target.value)
    setPage(1)
  }

  const columns = [
    { key: 'patient_code', header: 'Patient ID', render: (p) => <span className="font-mono text-xs text-brand-700">{p.patient_code}</span> },
    {
      key: 'name',
      header: 'Name',
      render: (p) => (
        <div>
          <p className="font-medium text-slate-900">{p.full_name}</p>
          <p className="text-xs text-slate-500">{p.email ?? 'No email'}</p>
        </div>
      ),
    },
    { key: 'age', header: 'Age / Gender', render: (p) => `${p.age} · ${titleCase(p.gender)}` },
    { key: 'phone', header: 'Phone', className: 'whitespace-nowrap' },
    { key: 'blood_group', header: 'Blood', render: (p) => p.blood_group ?? '—' },
    { key: 'created_at', header: 'Registered', render: (p) => formatDate(p.created_at), className: 'whitespace-nowrap' },
  ]

  return (
    <>
      <PageHeader
        title="Patients"
        description="Search, register and manage patient records."
        actions={
          canRegister && (
            <button type="button" className="btn-primary" onClick={() => setFormOpen(true)}>
              <UserPlus className="size-4" aria-hidden="true" /> Register patient
            </button>
          )
        }
      />

      <div className="card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
          <label className="relative flex-1">
            <span className="sr-only">Search patients</span>
            <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Search by name, Patient ID, phone or email…"
              value={search}
              onChange={resetPage(setSearch)}
            />
          </label>
          <select className="input sm:w-40" value={gender} onChange={resetPage(setGender)} aria-label="Filter by gender">
            <option value="">All genders</option>
            {GENDERS.map((g) => (
              <option key={g} value={g}>
                {titleCase(g)}
              </option>
            ))}
          </select>
          <select className="input sm:w-40" value={bloodGroup} onChange={resetPage(setBloodGroup)} aria-label="Filter by blood group">
            <option value="">All blood groups</option>
            {BLOOD_GROUPS.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </div>
        <AsyncContent state={patients}>
          {(data) => (
            <>
              <DataTable
                columns={columns}
                rows={data.items}
                onRowClick={(p) => navigate(`/patients/${p.id}`)}
                empty={
                  <EmptyState
                    icon={Users}
                    title={term ? 'No patients match your search' : 'No patients registered yet'}
                    description={term ? 'Try a different name, Patient ID or phone number.' : undefined}
                  />
                }
              />
              <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
            </>
          )}
        </AsyncContent>
      </div>

      {formOpen && (
        <PatientFormModal
          open
          onClose={() => setFormOpen(false)}
          onSaved={(p) => navigate(`/patients/${p.id}`)}
        />
      )}
    </>
  )
}
