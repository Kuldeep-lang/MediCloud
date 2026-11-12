import { api } from './client'

const get = (url, params) => api.get(url, { params }).then((r) => r.data)
const post = (url, body) => api.post(url, body ?? {}).then((r) => r.data)
const patch = (url, body) => api.patch(url, body).then((r) => r.data)
const put = (url, body) => api.put(url, body).then((r) => r.data)
const del = (url) => api.delete(url).then((r) => r.data)

/** Drop empty filter values so they are not sent as ?status= */
export const clean = (params = {}) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null && v !== false))

export const authApi = {
  login: (email, password) => post('/auth/login', { email, password }),
  me: () => get('/auth/me'),
}

export const systemApi = {
  info: () => get('/system/info'),
  status: () => get('/system/status'),
}

export const dashboardApi = {
  summary: () => get('/dashboard/summary'),
  admissionsTrend: (days) => get('/dashboard/admissions-trend', { days }),
  appointmentStats: (days) => get('/dashboard/appointment-stats', { days }),
  departmentDistribution: (days) => get('/dashboard/department-distribution', { days }),
  revenue: (months) => get('/dashboard/revenue', { months }),
}

export const departmentsApi = {
  list: () => get('/departments'),
}

export const patientsApi = {
  list: (params) => get('/patients', clean(params)),
  get: (id) => get(`/patients/${id}`),
  create: (body) => post('/patients', body),
  update: (id, body) => patch(`/patients/${id}`, body),
  history: (id) => get(`/patients/${id}/history`),
}

export const doctorsApi = {
  list: (params) => get('/doctors', clean(params)),
  get: (id) => get(`/doctors/${id}`),
  create: (body) => post('/doctors', body),
  update: (id, body) => patch(`/doctors/${id}`, body),
  deactivate: (id) => del(`/doctors/${id}`),
  setSchedules: (id, blocks) => put(`/doctors/${id}/schedules`, blocks),
  availability: (id, date) => get(`/doctors/${id}/availability`, { date }),
  appointments: (id, params) => get(`/doctors/${id}/appointments`, clean(params)),
}

export const appointmentsApi = {
  list: (params) => get('/appointments', clean(params)),
  create: (body) => post('/appointments', body),
  update: (id, body) => patch(`/appointments/${id}`, body),
  cancel: (id, reason) => post(`/appointments/${id}/cancel`, { reason }),
  setStatus: (id, body) => patch(`/appointments/${id}/status`, body),
}

export const bedsApi = {
  wards: () => get('/wards'),
  createWard: (body) => post('/wards', body),
  occupancy: () => get('/beds/occupancy'),
  list: (params) => get('/beds', clean(params)),
  create: (body) => post('/beds', body),
  setStatus: (id, status) => patch(`/beds/${id}`, { status }),
}

export const admissionsApi = {
  list: (params) => get('/admissions', clean(params)),
  admit: (body) => post('/admissions', body),
  discharge: (id, summary) => post(`/admissions/${id}/discharge`, { discharge_summary: summary }),
}

export const medicinesApi = {
  list: (params) => get('/medicines', clean(params)),
  create: (body) => post('/medicines', body),
  update: (id, body) => patch(`/medicines/${id}`, body),
  deactivate: (id) => del(`/medicines/${id}`),
  adjustStock: (id, body) => post(`/medicines/${id}/stock`, body),
  movements: (id, params) => get(`/medicines/${id}/movements`, clean(params)),
  alerts: () => get('/medicines/alerts'),
  usage: (days) => get('/medicines/usage', { days }),
  categories: () => get('/medicines/categories'),
}

export const prescriptionsApi = {
  list: (params) => get('/prescriptions', clean(params)),
  create: (body) => post('/prescriptions', body),
  dispense: (id) => post(`/prescriptions/${id}/dispense`),
  cancel: (id) => post(`/prescriptions/${id}/cancel`),
}

export const billingApi = {
  invoices: (params) => get('/invoices', clean(params)),
  invoice: (id) => get(`/invoices/${id}`),
  billable: (patientId) => get('/invoices/billable', { patient_id: patientId }),
  create: (body) => post('/invoices', body),
  cancel: (id) => post(`/invoices/${id}/cancel`),
  pay: (id, body) => post(`/invoices/${id}/payments`, body),
  payments: (params) => get('/payments', clean(params)),
}
