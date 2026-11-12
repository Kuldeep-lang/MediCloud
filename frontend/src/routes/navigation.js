import {
  Activity,
  BedDouble,
  CalendarClock,
  LayoutDashboard,
  Pill,
  Receipt,
  Stethoscope,
  Users,
} from 'lucide-react'

import { ALL_ROLES } from '../utils/constants'

/**
 * Single source of truth for navigation AND route guards, so users never see a
 * link they cannot open. The backend enforces the same rules independently.
 */
export const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, roles: ALL_ROLES },
  { to: '/patients', label: 'Patients', icon: Users, roles: ALL_ROLES },
  { to: '/doctors', label: 'Doctors', icon: Stethoscope, roles: ['admin', 'doctor', 'receptionist'] },
  {
    to: '/appointments',
    label: 'Appointments',
    icon: CalendarClock,
    roles: ['admin', 'doctor', 'receptionist'],
  },
  { to: '/beds', label: 'Beds & Wards', icon: BedDouble, roles: ['admin', 'doctor', 'receptionist'] },
  { to: '/pharmacy', label: 'Pharmacy', icon: Pill, roles: ['admin', 'pharmacist', 'doctor'] },
  { to: '/billing', label: 'Billing', icon: Receipt, roles: ['admin', 'receptionist'] },
  { to: '/monitoring', label: 'System Monitoring', icon: Activity, roles: ['admin'] },
]

export const rolesFor = (path) => NAV_ITEMS.find((item) => item.to === path)?.roles ?? ALL_ROLES
