"""Enumerations shared by models, schemas and services."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    PHARMACIST = "pharmacist"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class BloodGroup(StrEnum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


ACTIVE_APPOINTMENT_STATUSES = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)


class WardType(StrEnum):
    GENERAL = "general"
    ICU = "icu"
    PRIVATE = "private"
    EMERGENCY = "emergency"


class BedStatus(StrEnum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class AdmissionStatus(StrEnum):
    ADMITTED = "admitted"
    DISCHARGED = "discharged"


class StockReason(StrEnum):
    RESTOCK = "restock"
    DISPENSE = "dispense"
    ADJUSTMENT = "adjustment"
    EXPIRED = "expired"


class PrescriptionStatus(StrEnum):
    PENDING = "pending"
    DISPENSED = "dispensed"
    CANCELLED = "cancelled"


class InvoiceStatus(StrEnum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class InvoiceItemType(StrEnum):
    CONSULTATION = "consultation"
    MEDICINE = "medicine"
    ROOM = "room"
    DIAGNOSTIC = "diagnostic"
    OTHER = "other"


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    INSURANCE = "insurance"
    BANK_TRANSFER = "bank_transfer"


class PaymentStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
