"""Test fixtures.

Tests run against a REAL PostgreSQL database (partial indexes, CHECK constraints,
row locks and timezone SQL are all PostgreSQL features worth testing for real).
The schema is built with the actual Alembic migrations, so migrations are tested
too. Every test starts with empty tables.

Set TEST_DATABASE_URL to point elsewhere (CI uses a service container).
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://medicloud:devpassword@127.0.0.1:5433/medicloud_test",
)
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz"
os.environ["APP_ENV"] = "test"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["HOSPITAL_TIMEZONE"] = "Asia/Kolkata"
os.environ["LOG_LEVEL"] = "WARNING"

from collections.abc import Iterator  # noqa: E402
from datetime import date, datetime, time, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402
from itertools import count  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pwdlib import PasswordHash  # noqa: E402
from pwdlib.hashers.argon2 import Argon2Hasher  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import security  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.core.timeutils import hospital_tz, local_today, now_utc  # noqa: E402
from app.db.prestart import alembic_config  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Appointment,
    Bed,
    Department,
    Doctor,
    DoctorSchedule,
    Medicine,
    Patient,
    User,
    Ward,
)
from app.models.enums import AppointmentStatus, Gender, Role, WardType  # noqa: E402

# Cheap Argon2 parameters for tests only - production uses the recommended ones.
security.password_hash = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=1024, parallelism=1),))

TABLES = (
    "payments, invoice_items, invoices, stock_movements, prescription_items, prescriptions, "
    "admissions, beds, wards, appointments, doctor_schedules, doctors, departments, "
    "medicines, patients, users"
)
DEFAULT_PASSWORD = "Password123!"


def rebuild_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    rebuild_schema()
    yield


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        conn.execute(text("ALTER SEQUENCE patient_code_seq RESTART"))
        conn.execute(text("ALTER SEQUENCE invoice_number_seq RESTART"))


@pytest.fixture
def db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def local_at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=hospital_tz())


def tomorrow_iso(hour: int, minute: int = 0) -> str:
    """Naive local datetime string - the API interprets it in hospital time."""
    day = local_today() + timedelta(days=1)
    return datetime.combine(day, time(hour, minute)).isoformat()


class Factory:
    """Creates committed rows directly through the ORM for test setup."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._seq = count(1)

    def _n(self) -> int:
        return next(self._seq)

    def save(self, obj):
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def user(
        self,
        role: Role,
        *,
        email: str | None = None,
        active: bool = True,
        password: str = DEFAULT_PASSWORD,
    ) -> User:
        n = self._n()
        return self.save(
            User(
                email=email or f"{role.value}{n}@test.medicloud.demo",
                full_name=f"Test {role.value.title()} {n}",
                role=role,
                hashed_password=security.hash_password(password),
                is_active=active,
            )
        )

    @staticmethod
    def headers(user: User) -> dict[str, str]:
        token, _ = create_access_token(user.id, user.role.value)
        return {"Authorization": f"Bearer {token}"}

    def department(self, *, active: bool = True) -> Department:
        n = self._n()
        return self.save(Department(name=f"Department {n}", code=f"DEP{n}", is_active=active))

    def doctor(
        self, *, department: Department | None = None, user: User | None = None, fee: str = "800.00"
    ) -> Doctor:
        """Doctor available every day 08:00-20:00 in 15-minute slots."""
        n = self._n()
        doctor = Doctor(
            department_id=(department or self.department()).id,
            user_id=user.id if user else None,
            first_name="Asha",
            last_name=f"Rao{n}",
            specialization="General Medicine",
            license_number=f"LIC-{n:05d}",
            email=f"doctor{n}@test.medicloud.demo",
            phone="+91 9876543210",
            consultation_fee=Decimal(fee),
            years_experience=10,
        )
        doctor.schedules = [
            DoctorSchedule(day_of_week=d, start_time=time(8), end_time=time(20), slot_minutes=15)
            for d in range(7)
        ]
        return self.save(doctor)

    def patient(self, **overrides) -> Patient:
        n = self._n()
        fields = {
            "first_name": "Ravi",
            "last_name": f"Kumar{n}",
            "date_of_birth": date(1990, 5, 17),
            "gender": Gender.MALE,
            "phone": "+91 9123456789",
            "email": f"patient{n}@example.com",
        } | overrides
        return self.save(Patient(**fields))

    def ward(
        self, *, ward_type: WardType = WardType.GENERAL, beds: int = 3, rate: str = "1500.00"
    ) -> Ward:
        n = self._n()
        ward = Ward(name=f"Ward {n}", ward_type=ward_type, floor=1, daily_rate=Decimal(rate))
        ward.beds = [Bed(bed_number=f"W{n}-{i:02d}") for i in range(1, beds + 1)]
        return self.save(ward)

    def medicine(
        self,
        *,
        stock: int = 100,
        reorder: int = 10,
        price: str = "10.00",
        expiry_days: int = 365,
        active: bool = True,
    ) -> Medicine:
        n = self._n()
        return self.save(
            Medicine(
                code=f"MED{n:04d}",
                name=f"Medicine {n}",
                category="Analgesic",
                dosage_form="tablet",
                strength="500 mg",
                unit_price=Decimal(price),
                stock_quantity=stock,
                reorder_level=reorder,
                expiry_date=local_today() + timedelta(days=expiry_days),
                is_active=active,
            )
        )

    def appointment(
        self,
        patient: Patient,
        doctor: Doctor,
        *,
        when: datetime | None = None,
        status: AppointmentStatus = AppointmentStatus.SCHEDULED,
    ) -> Appointment:
        """Insert directly (bypasses booking rules) - used for past appointments."""
        when = when or (now_utc() - timedelta(days=1))
        return self.save(
            Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                scheduled_at=when,
                duration_minutes=15,
                status=status,
            )
        )


@pytest.fixture
def factory(db: Session) -> Factory:
    return Factory(db)


@pytest.fixture
def admin_headers(factory: Factory) -> dict[str, str]:
    return factory.headers(factory.user(Role.ADMIN))


@pytest.fixture
def receptionist_headers(factory: Factory) -> dict[str, str]:
    return factory.headers(factory.user(Role.RECEPTIONIST))


@pytest.fixture
def pharmacist_headers(factory: Factory) -> dict[str, str]:
    return factory.headers(factory.user(Role.PHARMACIST))


@pytest.fixture
def doctor_ctx(factory: Factory) -> tuple[Doctor, dict[str, str]]:
    """A doctor profile linked to a doctor-role login."""
    user = factory.user(Role.DOCTOR)
    doctor = factory.doctor(user=user)
    return doctor, factory.headers(user)
