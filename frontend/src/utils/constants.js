export const ROLES = {
  ADMIN: 'admin',
  DOCTOR: 'doctor',
  RECEPTIONIST: 'receptionist',
  PHARMACIST: 'pharmacist',
}
export const ALL_ROLES = Object.values(ROLES)

export const ROLE_LABELS = {
  admin: 'Administrator',
  doctor: 'Doctor',
  receptionist: 'Receptionist',
  pharmacist: 'Pharmacist',
}

export const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
export const GENDERS = ['male', 'female', 'other']
export const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
export const PAYMENT_METHODS = ['upi', 'cash', 'card', 'insurance', 'bank_transfer']

/**
 * Status tones. Every badge renders a text label next to its colour dot,
 * so meaning never depends on colour alone.
 */
export const STATUS_TONE = {
  // appointments
  scheduled: 'info',
  confirmed: 'brand',
  completed: 'good',
  cancelled: 'neutral',
  no_show: 'warning',
  // beds
  available: 'good',
  occupied: 'brand',
  maintenance: 'warning',
  // admissions
  admitted: 'brand',
  discharged: 'neutral',
  // prescriptions
  pending: 'warning',
  dispensed: 'good',
  // invoices / payments
  unpaid: 'critical',
  partially_paid: 'warning',
  paid: 'good',
  success: 'good',
  failed: 'critical',
  refunded: 'neutral',
}

export const DEMO_ACCOUNTS = [
  { email: 'admin@medicloud.demo', role: 'Administrator' },
  { email: 'doctor@medicloud.demo', role: 'Doctor' },
  { email: 'reception@medicloud.demo', role: 'Receptionist' },
  { email: 'pharmacy@medicloud.demo', role: 'Pharmacist' },
]
