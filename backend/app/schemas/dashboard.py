from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money


class BedStats(BaseModel):
    total: int
    available: int
    occupied: int
    maintenance: int


class DashboardSummary(BaseModel):
    total_patients: int
    total_doctors: int
    appointments_today: int
    my_appointments_today: int | None = None  # doctors only
    beds: BedStats
    icu: BedStats
    active_admissions: int
    pending_prescriptions: int
    low_stock_medicines: int
    unpaid_invoices: int | None = None  # admin / receptionist
    monthly_revenue: Money | None = None  # admin only


class AdmissionTrendPoint(BaseModel):
    date: date
    admissions: int
    discharges: int


class AppointmentDailyPoint(BaseModel):
    date: date
    total: int
    completed: int
    cancelled: int


class StatusCount(BaseModel):
    status: str
    count: int


class AppointmentStats(BaseModel):
    by_status: list[StatusCount]
    daily: list[AppointmentDailyPoint]


class DepartmentCount(BaseModel):
    department: str
    patients: int


class RevenuePoint(BaseModel):
    month: str  # YYYY-MM
    revenue: Money
