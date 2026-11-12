"""Database integration: migrations, constraints and the demo-data seed."""

from alembic import command
from sqlalchemy import func, inspect, select, text

from app.db.prestart import alembic_config
from app.db.seed import seed_demo_data
from app.db.session import engine
from app.models import Admission, Bed, Medicine, StockMovement, User
from app.models.enums import AdmissionStatus, BedStatus
from tests.conftest import rebuild_schema

EXPECTED_TABLES = {
    "users",
    "departments",
    "doctors",
    "doctor_schedules",
    "patients",
    "appointments",
    "wards",
    "beds",
    "admissions",
    "medicines",
    "stock_movements",
    "prescriptions",
    "prescription_items",
    "invoices",
    "invoice_items",
    "payments",
}


def tables() -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_migrations_create_full_schema():
    assert tables() == EXPECTED_TABLES
    with engine.connect() as conn:
        partial_indexes = set(
            conn.scalars(text("SELECT indexname FROM pg_indexes WHERE indexdef LIKE '%WHERE%'"))
        )
        trigram = set(
            conn.scalars(
                text("SELECT indexname FROM pg_indexes WHERE indexdef LIKE '%gin_trgm_ops%'")
            )
        )
    assert {
        "uq_appointments_doctor_active_slot",
        "uq_admissions_active_bed",
        "uq_admissions_active_patient",
    } <= partial_indexes
    assert {"ix_patients_first_name_trgm", "ix_medicines_name_trgm"} <= trigram


def test_foreign_keys_are_indexed():
    """PostgreSQL does not index FKs automatically - every FK should lead an index."""
    inspector = inspect(engine)
    missing = []
    for table in EXPECTED_TABLES:
        leading = {idx["column_names"][0] for idx in inspector.get_indexes(table)}
        leading |= {uq["column_names"][0] for uq in inspector.get_unique_constraints(table)}
        for fk in inspector.get_foreign_keys(table):
            column = fk["constrained_columns"][0]
            if column not in leading and column not in (
                "created_by",
                "performed_by",
                "received_by",
                "dispensed_by",
            ):
                missing.append(f"{table}.{column}")
    assert missing == []


def test_downgrade_and_upgrade_round_trip():
    command.downgrade(alembic_config(), "base")
    assert tables() == set()
    command.upgrade(alembic_config(), "head")
    assert tables() == EXPECTED_TABLES


def test_seed_is_consistent_and_idempotent(db):
    try:
        assert seed_demo_data(db, "Demo@12345") is True
        db.commit()
        assert db.scalar(select(func.count(User.id))) == 4

        # Every medicine's ledger ends at its current stock level.
        for medicine in db.scalars(select(Medicine)):
            last = db.scalar(
                select(StockMovement.balance_after)
                .where(StockMovement.medicine_id == medicine.id)
                .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
                .limit(1)
            )
            assert last == medicine.stock_quantity, medicine.code

        # Bed status agrees with active admissions.
        occupied = db.scalar(select(func.count(Bed.id)).where(Bed.status == BedStatus.OCCUPIED))
        active = db.scalar(
            select(func.count(Admission.id)).where(Admission.status == AdmissionStatus.ADMITTED)
        )
        assert occupied == active > 0

        assert seed_demo_data(db, "Demo@12345") is False  # second run is a no-op
    finally:
        db.rollback()
        rebuild_schema()  # seeded data advanced sequences; start the next test clean


def test_unreachable_database_fails_fast():
    """A dead or partitioned DB must error within seconds, not hang on TCP retransmits."""
    import time

    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.pool import NullPool

    from app.db.session import DB_CONNECT_ARGS

    # 192.0.2.1 is TEST-NET-1 (RFC 5737): never routed, so packets go unanswered.
    unreachable = create_engine(
        "postgresql+psycopg://nobody:nothing@192.0.2.1:5432/none",
        connect_args=DB_CONNECT_ARGS,
        poolclass=NullPool,
    )
    started = time.perf_counter()
    with pytest.raises(OperationalError), unreachable.connect():
        pass
    assert time.perf_counter() - started < 8
