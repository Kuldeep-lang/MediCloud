"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""

from app.models.admission import Admission
from app.models.appointment import Appointment
from app.models.billing import Invoice, InvoiceItem, Payment
from app.models.department import Department
from app.models.doctor import Doctor, DoctorSchedule
from app.models.medicine import Medicine, StockMovement
from app.models.patient import Patient
from app.models.prescription import Prescription, PrescriptionItem
from app.models.user import User
from app.models.ward import Bed, Ward

__all__ = [
    "Admission",
    "Appointment",
    "Bed",
    "Department",
    "Doctor",
    "DoctorSchedule",
    "Invoice",
    "InvoiceItem",
    "Medicine",
    "Patient",
    "Payment",
    "Prescription",
    "PrescriptionItem",
    "StockMovement",
    "User",
    "Ward",
]
