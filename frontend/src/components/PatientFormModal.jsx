import { useState } from 'react'

import { errorMessage } from '../api/client'
import { patientsApi } from '../api/endpoints'
import { useToast } from '../context/ToastContext'
import { BLOOD_GROUPS, GENDERS } from '../utils/constants'
import { titleCase, todayLocal } from '../utils/format'
import { Modal } from './ui/Modal'
import { Field } from './ui/primitives'

const EMPTY = {
  first_name: '',
  last_name: '',
  date_of_birth: '',
  gender: 'female',
  phone: '',
  email: '',
  address: '',
  blood_group: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  allergies: '',
}
const PHONE = /^\+?[0-9][0-9 ()-]{6,18}$/

function validate(values) {
  const errors = {}
  if (!values.first_name.trim()) errors.first_name = 'First name is required'
  if (!values.last_name.trim()) errors.last_name = 'Last name is required'
  if (!values.date_of_birth) errors.date_of_birth = 'Date of birth is required'
  else if (values.date_of_birth > todayLocal()) errors.date_of_birth = 'Cannot be in the future'
  if (!PHONE.test(values.phone.trim())) errors.phone = 'Enter a valid phone number'
  if (values.email && !/^\S+@\S+\.\S+$/.test(values.email)) errors.email = 'Enter a valid email'
  if (values.emergency_contact_phone && !PHONE.test(values.emergency_contact_phone.trim())) {
    errors.emergency_contact_phone = 'Enter a valid phone number'
  }
  return errors
}

/** Register a new patient or edit an existing one. */
export function PatientFormModal({ open, onClose, patient, onSaved }) {
  const toast = useToast()
  const [values, setValues] = useState(() => toForm(patient))
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [serverError, setServerError] = useState(null)

  const set = (key) => (event) => setValues((v) => ({ ...v, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    const found = validate(values)
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    setServerError(null)
    const payload = Object.fromEntries(
      Object.entries(values).map(([k, v]) => [k, typeof v === 'string' && v.trim() === '' ? null : v]),
    )
    try {
      const saved = patient
        ? await patientsApi.update(patient.id, payload)
        : await patientsApi.create(payload)
      toast.success(patient ? 'Patient details updated' : `Patient ${saved.patient_code} registered`)
      onSaved?.(saved)
      onClose()
    } catch (err) {
      setServerError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={patient ? `Edit ${patient.full_name}` : 'Register new patient'}
      description={patient ? patient.patient_code : 'A Patient ID is generated automatically.'}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="patient-form" className="btn-primary" disabled={busy}>
            {busy ? 'Saving…' : patient ? 'Save changes' : 'Register patient'}
          </button>
        </>
      }
    >
      <form id="patient-form" onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        {serverError && (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 sm:col-span-2">
            {serverError}
          </p>
        )}
        <Field label="First name" required error={errors.first_name}>
          {(id) => <input id={id} className="input" value={values.first_name} onChange={set('first_name')} maxLength={60} />}
        </Field>
        <Field label="Last name" required error={errors.last_name}>
          {(id) => <input id={id} className="input" value={values.last_name} onChange={set('last_name')} maxLength={60} />}
        </Field>
        <Field label="Date of birth" required error={errors.date_of_birth}>
          {(id) => (
            <input id={id} type="date" className="input" value={values.date_of_birth} max={todayLocal()} onChange={set('date_of_birth')} />
          )}
        </Field>
        <Field label="Gender" required>
          {(id) => (
            <select id={id} className="input" value={values.gender} onChange={set('gender')}>
              {GENDERS.map((g) => (
                <option key={g} value={g}>
                  {titleCase(g)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Phone" required error={errors.phone}>
          {(id) => <input id={id} className="input" value={values.phone} onChange={set('phone')} placeholder="+91 98765 43210" />}
        </Field>
        <Field label="Email" error={errors.email}>
          {(id) => <input id={id} type="email" className="input" value={values.email} onChange={set('email')} />}
        </Field>
        <Field label="Blood group">
          {(id) => (
            <select id={id} className="input" value={values.blood_group} onChange={set('blood_group')}>
              <option value="">Unknown</option>
              {BLOOD_GROUPS.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Allergies">
          {(id) => <input id={id} className="input" value={values.allergies} onChange={set('allergies')} placeholder="e.g. Penicillin" />}
        </Field>
        <Field label="Address" className="sm:col-span-2">
          {(id) => <textarea id={id} className="input min-h-16" value={values.address} onChange={set('address')} />}
        </Field>
        <Field label="Emergency contact name">
          {(id) => <input id={id} className="input" value={values.emergency_contact_name} onChange={set('emergency_contact_name')} />}
        </Field>
        <Field label="Emergency contact phone" error={errors.emergency_contact_phone}>
          {(id) => <input id={id} className="input" value={values.emergency_contact_phone} onChange={set('emergency_contact_phone')} />}
        </Field>
      </form>
    </Modal>
  )
}

function toForm(patient) {
  if (!patient) return EMPTY
  return Object.fromEntries(Object.keys(EMPTY).map((k) => [k, patient[k] ?? '']))
}
