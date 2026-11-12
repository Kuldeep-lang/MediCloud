"""Deterministic SYNTHETIC demo data. Contains no real patient information.

A fixed random seed makes every run produce the same people, schedules and
inventory. Dates are relative to "now", so charts always show recent activity.
The seed is idempotent: it does nothing if any user already exists.
"""

import logging
import random
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.timeutils import hospital_tz, local_today, now_utc
from app.models import (
    Admission,
    Appointment,
    Bed,
    Department,
    Doctor,
    DoctorSchedule,
    Invoice,
    InvoiceItem,
    Medicine,
    Patient,
    Payment,
    Prescription,
    PrescriptionItem,
    StockMovement,
    User,
    Ward,
)
from app.models.enums import (
    AdmissionStatus,
    AppointmentStatus,
    BedStatus,
    BloodGroup,
    Gender,
    InvoiceItemType,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    PrescriptionStatus,
    Role,
    StockReason,
    WardType,
)

logger = logging.getLogger(__name__)

SEED = 20261112
HISTORY_DAYS = 180
FUTURE_DAYS = 14

DEMO_USERS = [
    ("admin@medicloud.demo", "Priya Nair", Role.ADMIN),
    ("doctor@medicloud.demo", "Dr. Arjun Mehta", Role.DOCTOR),
    ("reception@medicloud.demo", "Kavya Iyer", Role.RECEPTIONIST),
    ("pharmacy@medicloud.demo", "Rohan Gupta", Role.PHARMACIST),
]

DEPARTMENTS = [
    (
        "Cardiology",
        "CARD",
        "Heart and vascular care",
        ["Interventional Cardiology", "Clinical Cardiology"],
        [
            "Essential hypertension",
            "Stable angina",
            "Atrial fibrillation - follow-up",
            "Hyperlipidaemia",
            "Palpitations, benign",
        ],
    ),
    (
        "Neurology",
        "NEUR",
        "Brain, spine and nervous system",
        ["Clinical Neurology", "Neurophysiology"],
        [
            "Migraine without aura",
            "Tension-type headache",
            "Peripheral neuropathy",
            "Epilepsy - medication review",
            "Vertigo",
        ],
    ),
    (
        "Orthopaedics",
        "ORTH",
        "Bones, joints and sports injuries",
        ["Joint Replacement", "Sports Medicine"],
        [
            "Knee osteoarthritis",
            "Lumbar strain",
            "Ankle sprain",
            "Frozen shoulder",
            "Fracture follow-up",
        ],
    ),
    (
        "Paediatrics",
        "PEDS",
        "Care for infants, children and adolescents",
        ["General Paediatrics", "Neonatology"],
        [
            "Acute viral fever",
            "Otitis media",
            "Routine immunisation",
            "Gastroenteritis",
            "Seasonal allergic rhinitis",
        ],
    ),
    (
        "General Medicine",
        "GMED",
        "Primary and internal medicine",
        ["Internal Medicine", "Family Medicine"],
        [
            "Type 2 diabetes - review",
            "Upper respiratory infection",
            "Vitamin D deficiency",
            "Iron-deficiency anaemia",
            "Acute gastritis",
        ],
    ),
    (
        "Dermatology",
        "DERM",
        "Skin, hair and nail conditions",
        ["Clinical Dermatology", "Cosmetic Dermatology"],
        [
            "Atopic dermatitis",
            "Acne vulgaris",
            "Fungal skin infection",
            "Psoriasis",
            "Contact dermatitis",
        ],
    ),
    (
        "ENT",
        "ENT",
        "Ear, nose and throat",
        ["Otolaryngology", "Head and Neck Surgery"],
        [
            "Chronic sinusitis",
            "Tonsillitis",
            "Impacted ear wax",
            "Allergic rhinitis",
            "Hearing assessment",
        ],
    ),
    (
        "Obstetrics & Gynaecology",
        "OBGY",
        "Women's health and maternity",
        ["Obstetrics", "Gynaecology"],
        [
            "Routine antenatal check",
            "Polycystic ovary syndrome",
            "Menstrual irregularity",
            "Postnatal review",
            "Urinary tract infection",
        ],
    ),
]

VISIT_REASONS = [
    "Follow-up consultation",
    "New symptoms",
    "Routine check-up",
    "Medication review",
    "Test results discussion",
    "Persistent pain",
    "Fever and fatigue",
    "Second opinion",
]

# code, name, generic, category, form, strength, unit price (INR), final stock, reorder level
MEDICINES = [
    (
        "PCM500",
        "Paracetamol 500",
        "Paracetamol",
        "Analgesic",
        "tablet",
        "500 mg",
        "2.00",
        1800,
        300,
    ),
    ("IBU400", "Ibuprofen 400", "Ibuprofen", "Analgesic", "tablet", "400 mg", "3.50", 950, 200),
    (
        "DCL50",
        "Diclofenac 50",
        "Diclofenac sodium",
        "Analgesic",
        "tablet",
        "50 mg",
        "2.80",
        60,
        150,
    ),
    ("TRM50", "Tramadol 50", "Tramadol", "Analgesic", "capsule", "50 mg", "6.00", 240, 80),
    (
        "AMX500",
        "Amoxicillin 500",
        "Amoxicillin",
        "Antibiotic",
        "capsule",
        "500 mg",
        "6.50",
        720,
        200,
    ),
    (
        "AZI500",
        "Azithromycin 500",
        "Azithromycin",
        "Antibiotic",
        "tablet",
        "500 mg",
        "22.00",
        85,
        100,
    ),
    (
        "CIP500",
        "Ciprofloxacin 500",
        "Ciprofloxacin",
        "Antibiotic",
        "tablet",
        "500 mg",
        "8.00",
        410,
        120,
    ),
    ("CEF200", "Cefixime 200", "Cefixime", "Antibiotic", "tablet", "200 mg", "11.00", 380, 120),
    (
        "DOX100",
        "Doxycycline 100",
        "Doxycycline",
        "Antibiotic",
        "capsule",
        "100 mg",
        "5.50",
        300,
        100,
    ),
    ("MET500", "Metformin 500", "Metformin", "Antidiabetic", "tablet", "500 mg", "1.80", 2200, 400),
    ("GLM2", "Glimepiride 2", "Glimepiride", "Antidiabetic", "tablet", "2 mg", "4.20", 640, 150),
    (
        "INS-R",
        "Insulin Regular",
        "Human insulin",
        "Antidiabetic",
        "injection",
        "100 IU/ml",
        "180.00",
        38,
        40,
    ),
    ("AML5", "Amlodipine 5", "Amlodipine", "Cardiovascular", "tablet", "5 mg", "2.40", 1500, 300),
    (
        "TEL40",
        "Telmisartan 40",
        "Telmisartan",
        "Cardiovascular",
        "tablet",
        "40 mg",
        "5.00",
        900,
        200,
    ),
    (
        "ATV20",
        "Atorvastatin 20",
        "Atorvastatin",
        "Cardiovascular",
        "tablet",
        "20 mg",
        "6.80",
        1100,
        250,
    ),
    (
        "ASP75",
        "Aspirin 75",
        "Acetylsalicylic acid",
        "Cardiovascular",
        "tablet",
        "75 mg",
        "1.20",
        1300,
        300,
    ),
    (
        "CLP75",
        "Clopidogrel 75",
        "Clopidogrel",
        "Cardiovascular",
        "tablet",
        "75 mg",
        "7.50",
        140,
        150,
    ),
    (
        "MTP50",
        "Metoprolol 50",
        "Metoprolol succinate",
        "Cardiovascular",
        "tablet",
        "50 mg",
        "4.60",
        700,
        150,
    ),
    ("FUR40", "Furosemide 40", "Furosemide", "Cardiovascular", "tablet", "40 mg", "1.50", 520, 120),
    (
        "PAN40",
        "Pantoprazole 40",
        "Pantoprazole",
        "Gastrointestinal",
        "tablet",
        "40 mg",
        "4.00",
        1250,
        250,
    ),
    (
        "OME20",
        "Omeprazole 20",
        "Omeprazole",
        "Gastrointestinal",
        "capsule",
        "20 mg",
        "3.20",
        860,
        200,
    ),
    ("OND4", "Ondansetron 4", "Ondansetron", "Gastrointestinal", "tablet", "4 mg", "5.50", 45, 80),
    (
        "ORS",
        "ORS Sachet",
        "Oral rehydration salts",
        "Gastrointestinal",
        "sachet",
        "21 g",
        "18.00",
        420,
        100,
    ),
    (
        "DOM10",
        "Domperidone 10",
        "Domperidone",
        "Gastrointestinal",
        "tablet",
        "10 mg",
        "2.60",
        500,
        120,
    ),
    ("CET10", "Cetirizine 10", "Cetirizine", "Antihistamine", "tablet", "10 mg", "1.60", 1400, 250),
    (
        "LEV5",
        "Levocetirizine 5",
        "Levocetirizine",
        "Antihistamine",
        "tablet",
        "5 mg",
        "2.20",
        780,
        200,
    ),
    ("MON10", "Montelukast 10", "Montelukast", "Respiratory", "tablet", "10 mg", "9.50", 460, 120),
    (
        "SAL-INH",
        "Salbutamol Inhaler",
        "Salbutamol",
        "Respiratory",
        "inhaler",
        "100 mcg",
        "145.00",
        64,
        40,
    ),
    (
        "BUD-INH",
        "Budesonide Inhaler",
        "Budesonide",
        "Respiratory",
        "inhaler",
        "200 mcg",
        "320.00",
        22,
        30,
    ),
    (
        "AMB-SYR",
        "Ambroxol Syrup",
        "Ambroxol",
        "Respiratory",
        "syrup",
        "30 mg/5 ml",
        "68.00",
        150,
        50,
    ),
    (
        "PRED10",
        "Prednisolone 10",
        "Prednisolone",
        "Corticosteroid",
        "tablet",
        "10 mg",
        "2.10",
        380,
        100,
    ),
    (
        "HYD-CRM",
        "Hydrocortisone Cream",
        "Hydrocortisone",
        "Dermatological",
        "cream",
        "1%",
        "55.00",
        90,
        40,
    ),
    (
        "CLT-CRM",
        "Clotrimazole Cream",
        "Clotrimazole",
        "Dermatological",
        "cream",
        "1%",
        "48.00",
        130,
        40,
    ),
    (
        "FLU150",
        "Fluconazole 150",
        "Fluconazole",
        "Antifungal",
        "tablet",
        "150 mg",
        "12.00",
        260,
        80,
    ),
    (
        "BPO-GEL",
        "Benzoyl Peroxide Gel",
        "Benzoyl peroxide",
        "Dermatological",
        "gel",
        "2.5%",
        "95.00",
        70,
        30,
    ),
    (
        "ISO10",
        "Isotretinoin 10",
        "Isotretinoin",
        "Dermatological",
        "capsule",
        "10 mg",
        "28.00",
        18,
        40,
    ),
    (
        "VTD60K",
        "Vitamin D3 60K",
        "Cholecalciferol",
        "Supplement",
        "capsule",
        "60000 IU",
        "32.00",
        610,
        150,
    ),
    (
        "FER100",
        "Ferrous Sulphate",
        "Ferrous sulphate",
        "Supplement",
        "tablet",
        "100 mg",
        "1.40",
        1600,
        300,
    ),
    ("FOL5", "Folic Acid 5", "Folic acid", "Supplement", "tablet", "5 mg", "0.90", 1800, 300),
    (
        "CAL500",
        "Calcium + D3",
        "Calcium carbonate",
        "Supplement",
        "tablet",
        "500 mg",
        "3.00",
        1200,
        250,
    ),
    (
        "B12-1500",
        "Methylcobalamin",
        "Methylcobalamin",
        "Supplement",
        "tablet",
        "1500 mcg",
        "6.00",
        540,
        150,
    ),
    (
        "GAB300",
        "Gabapentin 300",
        "Gabapentin",
        "Neurological",
        "capsule",
        "300 mg",
        "9.00",
        330,
        100,
    ),
    (
        "LEV500",
        "Levetiracetam 500",
        "Levetiracetam",
        "Neurological",
        "tablet",
        "500 mg",
        "14.00",
        280,
        100,
    ),
    ("SUM50", "Sumatriptan 50", "Sumatriptan", "Neurological", "tablet", "50 mg", "24.00", 75, 60),
    (
        "BET-SYR",
        "Betahistine 16",
        "Betahistine",
        "Neurological",
        "tablet",
        "16 mg",
        "7.00",
        210,
        60,
    ),
    (
        "ESC10",
        "Escitalopram 10",
        "Escitalopram",
        "Psychiatric",
        "tablet",
        "10 mg",
        "6.50",
        360,
        100,
    ),
    (
        "ALP025",
        "Alprazolam 0.25",
        "Alprazolam",
        "Psychiatric",
        "tablet",
        "0.25 mg",
        "2.50",
        120,
        60,
    ),
    (
        "OXY-NAS",
        "Oxymetazoline Spray",
        "Oxymetazoline",
        "ENT",
        "nasal spray",
        "0.05%",
        "85.00",
        95,
        30,
    ),
    (
        "CIP-EAR",
        "Ciprofloxacin Ear Drops",
        "Ciprofloxacin",
        "ENT",
        "drops",
        "0.3%",
        "62.00",
        70,
        30,
    ),
    (
        "PRG-200",
        "Progesterone 200",
        "Micronised progesterone",
        "Hormonal",
        "capsule",
        "200 mg",
        "38.00",
        110,
        50,
    ),
    (
        "LTX50",
        "Levothyroxine 50",
        "Levothyroxine",
        "Hormonal",
        "tablet",
        "50 mcg",
        "1.90",
        980,
        200,
    ),
    (
        "NS-500",
        "Normal Saline 500 ml",
        "Sodium chloride 0.9%",
        "IV Fluid",
        "infusion",
        "500 ml",
        "35.00",
        260,
        100,
    ),
    (
        "RL-500",
        "Ringer Lactate 500 ml",
        "Compound sodium lactate",
        "IV Fluid",
        "infusion",
        "500 ml",
        "42.00",
        190,
        80,
    ),
    (
        "CEFT1G",
        "Ceftriaxone 1 g",
        "Ceftriaxone",
        "Antibiotic",
        "injection",
        "1 g",
        "58.00",
        140,
        60,
    ),
    (
        "HEP5K",
        "Heparin 5000 IU",
        "Heparin sodium",
        "Anticoagulant",
        "injection",
        "5000 IU",
        "95.00",
        48,
        40,
    ),
    (
        "ENX40",
        "Enoxaparin 40",
        "Enoxaparin",
        "Anticoagulant",
        "injection",
        "40 mg",
        "310.00",
        26,
        30,
    ),
    (
        "MOR10",
        "Morphine 10",
        "Morphine sulphate",
        "Analgesic",
        "injection",
        "10 mg/ml",
        "45.00",
        30,
        20,
    ),
    (
        "DEX4",
        "Dexamethasone 4",
        "Dexamethasone",
        "Corticosteroid",
        "injection",
        "4 mg/ml",
        "12.00",
        160,
        60,
    ),
    (
        "ADR1",
        "Adrenaline 1 mg",
        "Epinephrine",
        "Emergency",
        "injection",
        "1 mg/ml",
        "28.00",
        55,
        30,
    ),
    (
        "ATR06",
        "Atropine 0.6",
        "Atropine sulphate",
        "Emergency",
        "injection",
        "0.6 mg/ml",
        "15.00",
        40,
        30,
    ),
]
# Medicines whose stock should be close to expiry / already expired, for alerts.
EXPIRING_SOON_CODES = {"AMB-SYR", "ORS", "OXY-NAS", "INS-R"}
EXPIRED_CODES = {"HYD-CRM", "ATR06"}

# name, type, floor, daily rate (INR), bed count, bed prefix, beds occupied now
WARDS = [
    ("General Ward A", WardType.GENERAL, 1, "1500.00", 30, "GA", 11),
    ("General Ward B", WardType.GENERAL, 2, "1500.00", 20, "GB", 7),
    ("Intensive Care Unit", WardType.ICU, 3, "8000.00", 12, "ICU", 8),
    ("Private Rooms", WardType.PRIVATE, 4, "4500.00", 10, "PR", 4),
    ("Emergency", WardType.EMERGENCY, 0, "3000.00", 8, "ER", 3),
]
ADMISSION_REASONS = [
    "Community-acquired pneumonia",
    "Uncontrolled blood sugar",
    "Post-operative care",
    "Chest pain - observation",
    "Acute gastroenteritis with dehydration",
    "Dengue fever",
    "Fracture - surgical fixation",
    "Severe asthma exacerbation",
    "Cellulitis - IV antibiotics",
    "Head injury - observation",
]
DIAGNOSTIC_TESTS = [
    ("Complete blood count", "450.00"),
    ("Lipid profile", "750.00"),
    ("Chest X-ray", "600.00"),
    ("ECG", "350.00"),
    ("HbA1c", "550.00"),
    ("Ultrasound abdomen", "1500.00"),
    ("CT scan - head", "4500.00"),
    ("Liver function test", "800.00"),
]
ALLERGIES = ["Penicillin", "Sulfa drugs", "Peanuts", "Latex", "Dust mites", "Shellfish"]
BLOOD_GROUP_WEIGHTS = {
    BloodGroup.O_POS: 37,
    BloodGroup.B_POS: 32,
    BloodGroup.A_POS: 22,
    BloodGroup.AB_POS: 6,
    BloodGroup.O_NEG: 1,
    BloodGroup.B_NEG: 1,
    BloodGroup.A_NEG: 0.6,
    BloodGroup.AB_NEG: 0.4,
}
PAYMENT_METHOD_WEIGHTS = {
    PaymentMethod.UPI: 45,
    PaymentMethod.CASH: 22,
    PaymentMethod.CARD: 20,
    PaymentMethod.INSURANCE: 10,
    PaymentMethod.BANK_TRANSFER: 3,
}


class _Seeder:
    def __init__(self, db: Session, password: str) -> None:
        self.db = db
        self.password = password
        self.rng = random.Random(SEED)
        self.fake = Faker("en_IN")
        self.fake.seed_instance(SEED)
        self.tz = hospital_tz()
        self.now = now_utc()
        self.today = local_today()
        self.txn_counter = 0
        self.invoice_counter = 0

    # ---------- helpers ----------
    def local_dt(self, day: date, at: time) -> datetime:
        return datetime.combine(day, at, tzinfo=self.tz).astimezone(self.now.tzinfo)

    def phone(self) -> str:
        return f"+91 {self.rng.choice('6789')}{self.rng.randint(100_000_000, 999_999_999)}"

    def txn_ref(self) -> str:
        self.txn_counter += 1
        return f"SIM-SEED{self.txn_counter:010d}"

    def next_invoice_number(self, issued: datetime) -> str:
        self.invoice_counter += 1
        return f"INV-{issued.astimezone(self.tz).year}-{self.invoice_counter:06d}"

    @staticmethod
    def slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    # ---------- reference data ----------
    def users(self) -> dict[Role, User]:
        users = {}
        for email, name, role in DEMO_USERS:
            user = User(
                email=email, full_name=name, role=role, hashed_password=hash_password(self.password)
            )
            self.db.add(user)
            users[role] = user
        self.db.flush()
        return users

    def departments_and_doctors(self, doctor_user: User) -> tuple[list[Doctor], dict]:
        doctors: list[Doctor] = []
        diagnoses: dict[int, list[str]] = {}
        for d_index, (name, code, desc, specs, dx) in enumerate(DEPARTMENTS):
            dept = Department(name=name, code=code, description=desc)
            self.db.add(dept)
            self.db.flush()
            for s_index, spec in enumerate(specs):
                if d_index == 0 and s_index == 0:
                    first, last, user_id = "Arjun", "Mehta", doctor_user.id
                else:
                    first, last, user_id = self.fake.first_name(), self.fake.last_name(), None
                number = len(doctors) + 1
                doctor = Doctor(
                    user_id=user_id,
                    department_id=dept.id,
                    first_name=first,
                    last_name=last,
                    specialization=spec,
                    license_number=f"NMC-{2000 + self.rng.randint(0, 22)}-{10000 + number * 37}",
                    email=f"{self.slug(first)}.{self.slug(last)}{number}@medicloud.demo",
                    phone=self.phone(),
                    consultation_fee=Decimal(self.rng.choice([500, 600, 700, 800, 1000, 1200])),
                    years_experience=self.rng.randint(4, 30),
                )
                # Mon-Fri mornings, alternate afternoons, some Saturdays.
                blocks = [(day, time(9, 0), time(13, 0)) for day in range(5)]
                if number % 2 == 0:
                    blocks += [(day, time(14, 0), time(17, 0)) for day in (0, 2, 4)]
                else:
                    blocks += [(day, time(14, 0), time(17, 0)) for day in (1, 3)]
                if number % 3 == 0:
                    blocks.append((5, time(9, 0), time(12, 0)))
                doctor.schedules = [
                    DoctorSchedule(day_of_week=d, start_time=s, end_time=e, slot_minutes=20)
                    for d, s, e in blocks
                ]
                self.db.add(doctor)
                doctors.append(doctor)
                diagnoses[number] = dx
        self.db.flush()
        return doctors, {doc.id: diagnoses[i + 1] for i, doc in enumerate(doctors)}

    def patients(self, count: int = 120) -> list[Patient]:
        patients = []
        groups, weights = zip(*BLOOD_GROUP_WEIGHTS.items(), strict=True)
        for _ in range(count):
            gender = self.rng.choices([Gender.MALE, Gender.FEMALE, Gender.OTHER], [49, 49, 2])[0]
            if gender == Gender.MALE:
                first = self.fake.first_name_male()
            elif gender == Gender.FEMALE:
                first = self.fake.first_name_female()
            else:
                first = self.fake.first_name()
            age_days = self.rng.randint(365, 88 * 365)
            registered = self.now - timedelta(
                days=self.rng.randint(0, 365), minutes=self.rng.randint(0, 600)
            )
            patients.append(
                Patient(
                    first_name=first,
                    last_name=self.fake.last_name(),
                    date_of_birth=self.today - timedelta(days=age_days),
                    gender=gender,
                    phone=self.phone(),
                    email=self.fake.safe_email() if self.rng.random() < 0.8 else None,
                    address=self.fake.address().replace("\n", ", "),
                    blood_group=self.rng.choices(groups, weights)[0],
                    emergency_contact_name=self.fake.name(),
                    emergency_contact_phone=self.phone(),
                    allergies=self.rng.choice(ALLERGIES) if self.rng.random() < 0.15 else None,
                    created_at=registered,
                )
            )
        # Insert in registration order so patient codes increase with registration date.
        patients.sort(key=lambda p: p.created_at)
        self.db.add_all(patients)
        self.db.flush()
        return patients

    def wards_and_beds(self) -> dict[str, tuple[Ward, list[Bed], int]]:
        result = {}
        for name, ward_type, floor, rate, count, prefix, occupied in WARDS:
            ward = Ward(name=name, ward_type=ward_type, floor=floor, daily_rate=Decimal(rate))
            ward.beds = [Bed(bed_number=f"{prefix}-{n:02d}") for n in range(1, count + 1)]
            self.db.add(ward)
            result[prefix] = (ward, ward.beds, occupied)
        # A couple of beds under maintenance make the occupancy chart more realistic.
        result["GA"][1][-1].status = BedStatus.MAINTENANCE
        result["GB"][1][-1].status = BedStatus.MAINTENANCE
        self.db.flush()
        return result

    def medicines(self) -> dict[str, Medicine]:
        medicines = {}
        for code, name, generic, cat, form, strength, price, stock, reorder in MEDICINES:
            if code in EXPIRED_CODES:
                expiry = self.today - timedelta(days=self.rng.randint(3, 25))
            elif code in EXPIRING_SOON_CODES:
                expiry = self.today + timedelta(days=self.rng.randint(5, 28))
            else:
                expiry = self.today + timedelta(days=self.rng.randint(120, 900))
            med = Medicine(
                code=code,
                name=name,
                generic_name=generic,
                category=cat,
                manufacturer=self.rng.choice(
                    [
                        "Sunrise Pharma",
                        "Medilife Labs",
                        "Healwell Ltd",
                        "Apex Generics",
                        "Vitacare Pharmaceuticals",
                    ]
                ),
                dosage_form=form,
                strength=strength,
                unit_price=Decimal(price),
                stock_quantity=stock,
                reorder_level=reorder,
                batch_number=f"B{self.rng.randint(10000, 99999)}",
                expiry_date=expiry,
            )
            self.db.add(med)
            medicines[code] = med
        self.db.flush()
        return medicines

    # ---------- activity ----------
    def appointments(
        self,
        doctors: list[Doctor],
        patients: list[Patient],
        diagnoses: dict[int, list[str]],
        receptionist: User,
    ) -> list[Appointment]:
        appointments: list[Appointment] = []
        # Some patients are frequent visitors: weight patients unevenly.
        patient_weights = [self.rng.choice([1, 1, 1, 2, 3, 5]) for _ in patients]
        patient_slots: dict[int, set[datetime]] = {}
        for offset in range(-HISTORY_DAYS, FUTURE_DAYS + 1):
            day = self.today + timedelta(days=offset)
            # Volume grows over time (a hospital gaining patients) - nicer trend charts.
            growth = 0.35 + 0.65 * (offset + HISTORY_DAYS) / (HISTORY_DAYS + FUTURE_DAYS)
            for doctor in doctors:
                blocks = [b for b in doctor.schedules if b.day_of_week == day.weekday()]
                if not blocks:
                    continue
                slots = []
                for block in blocks:
                    cursor = datetime.combine(day, block.start_time)
                    end = datetime.combine(day, block.end_time)
                    while cursor + timedelta(minutes=block.slot_minutes) <= end:
                        slots.append(cursor.time())
                        cursor += timedelta(minutes=block.slot_minutes)
                if offset == 0:
                    wanted = self.rng.randint(1, 3) + (3 if doctor.user_id else 0)
                elif offset > 0:
                    wanted = self.rng.choices([0, 1, 2], [45, 40, 15])[0]
                else:
                    wanted = self.rng.choices([0, 1, 2, 3], [42, 33, 18, 7])[0]
                    wanted = round(wanted * growth + self.rng.random() * 0.4)
                for slot in sorted(self.rng.sample(slots, min(wanted, len(slots)))):
                    start = self.local_dt(day, slot)
                    # Same rule the API enforces: a patient is never in two places at once.
                    patient = self.rng.choices(patients, patient_weights)[0]
                    while start in patient_slots.setdefault(patient.id, set()):
                        patient = self.rng.choices(patients, patient_weights)[0]
                    patient_slots[patient.id].add(start)
                    if start < self.now:
                        status = self.rng.choices(
                            [
                                AppointmentStatus.COMPLETED,
                                AppointmentStatus.CANCELLED,
                                AppointmentStatus.NO_SHOW,
                            ],
                            [80, 12, 8],
                        )[0]
                        if offset == 0:
                            status = AppointmentStatus.COMPLETED
                    else:
                        status = self.rng.choices(
                            [
                                AppointmentStatus.SCHEDULED,
                                AppointmentStatus.CONFIRMED,
                                AppointmentStatus.CANCELLED,
                            ],
                            [62, 33, 5],
                        )[0]
                    appt = Appointment(
                        patient_id=patient.id,
                        doctor_id=doctor.id,
                        scheduled_at=start,
                        duration_minutes=20,
                        status=status,
                        reason=self.rng.choice(VISIT_REASONS),
                        created_by=receptionist.id,
                        created_at=min(start, self.now) - timedelta(days=self.rng.randint(1, 10)),
                    )
                    if status == AppointmentStatus.COMPLETED:
                        appt.diagnosis = self.rng.choice(diagnoses[doctor.id])
                        appt.notes = self.rng.choice(
                            [
                                "Advised rest and hydration. Review in 2 weeks.",
                                "Vitals stable. Continue current medication.",
                                "Lifestyle modification discussed. Follow up after tests.",
                                "Symptoms improving. Taper medication as advised.",
                                "Referred for further investigations.",
                            ]
                        )
                    elif status == AppointmentStatus.CANCELLED:
                        appt.cancellation_reason = self.rng.choice(
                            ["Patient request", "Doctor unavailable", "Rescheduled by patient"]
                        )
                    appointments.append(appt)
        self.db.add_all(appointments)
        self.db.flush()
        return appointments

    def prescriptions(
        self, appointments: list[Appointment], medicines: dict[str, Medicine], pharmacist: User
    ) -> list[tuple[datetime, Medicine, int, int]]:
        """Create prescriptions; return dispense events (time, medicine, qty, rx_id)."""
        usable = [m for code, m in medicines.items() if code not in EXPIRED_CODES]
        events = []
        for appt in appointments:
            if appt.status != AppointmentStatus.COMPLETED or self.rng.random() > 0.55:
                continue
            chosen = self.rng.sample(usable, self.rng.randint(1, 3))
            age = self.now - appt.scheduled_at
            dispensed = age > timedelta(hours=6) and self.rng.random() < 0.93
            rx = Prescription(
                patient_id=appt.patient_id,
                doctor_id=appt.doctor_id,
                appointment_id=appt.id,
                status=PrescriptionStatus.DISPENSED if dispensed else PrescriptionStatus.PENDING,
                notes="Take after meals." if self.rng.random() < 0.4 else None,
                created_at=appt.scheduled_at + timedelta(minutes=15),
            )
            for med in chosen:
                per_unit = med.dosage_form in ("tablet", "capsule")
                qty = self.rng.choice([10, 14, 15, 20, 30]) if per_unit else self.rng.randint(1, 2)
                rx.items.append(
                    PrescriptionItem(
                        medicine_id=med.id,
                        dosage=med.strength or "1 unit",
                        frequency=self.rng.choice(["1-0-1", "1-1-1", "0-0-1", "1-0-0", "SOS"]),
                        duration_days=self.rng.choice([3, 5, 7, 10, 14, 30]),
                        quantity=qty,
                        instructions=self.rng.choice([None, "After food", "Before breakfast"]),
                    )
                )
            if dispensed:
                rx.dispensed_at = appt.scheduled_at + timedelta(hours=1)
                rx.dispensed_by = pharmacist.id
            self.db.add(rx)
            self.db.flush()
            if dispensed:
                for item in rx.items:
                    med = next(m for m in chosen if m.id == item.medicine_id)
                    events.append((rx.dispensed_at, med, item.quantity, rx.id))
        return events

    def stock_ledger(self, medicines: dict[str, Medicine], events, pharmacist: User) -> None:
        """Build a consistent ledger: restocks then dispenses, ending at the target stock."""
        start = self.now - timedelta(days=HISTORY_DAYS + 5)
        mid = self.now - timedelta(days=HISTORY_DAYS // 2)
        by_med: dict[int, list] = {}
        for when, med, qty, rx_id in events:
            by_med.setdefault(med.id, []).append((when, qty, rx_id))
        for med in medicines.values():
            dispenses = sorted(by_med.get(med.id, []))
            total = sum(q for _, q, _ in dispenses)
            before_mid = sum(q for w, q, _ in dispenses if w < mid)
            final = med.stock_quantity
            first = before_mid + self.rng.randint(20, 60)
            second = final + total - first
            if second <= 0:
                first, second = final + total, 0
            entries = [(start, first, StockReason.RESTOCK, "opening stock")]
            if second > 0:
                entries.append((mid, second, StockReason.RESTOCK, "purchase order"))
            entries += [
                (w, -q, StockReason.DISPENSE, f"prescription:{rx}") for w, q, rx in dispenses
            ]
            balance = 0
            for when, change, reason, ref in sorted(entries, key=lambda e: e[0]):
                balance += change
                self.db.add(
                    StockMovement(
                        medicine_id=med.id,
                        change_quantity=change,
                        balance_after=balance,
                        reason=reason,
                        reference=ref,
                        performed_by=pharmacist.id,
                        created_at=when,
                    )
                )
            assert balance == final, f"ledger mismatch for {med.code}"  # noqa: S101
        self.db.flush()

    def admissions(self, wards, patients: list[Patient], doctors: list[Doctor]) -> list[Admission]:
        admissions = []
        free_patients = list(patients)
        self.rng.shuffle(free_patients)
        # Historical (discharged) stays spread over the history window.
        all_beds = [
            b for _, beds, _ in wards.values() for b in beds if b.status != BedStatus.MAINTENANCE
        ]
        for _ in range(72):
            admitted = self.now - timedelta(
                days=self.rng.randint(4, HISTORY_DAYS - 5), hours=self.rng.randint(0, 23)
            )
            stay = timedelta(days=self.rng.randint(1, 8), hours=self.rng.randint(1, 20))
            discharged = min(admitted + stay, self.now - timedelta(hours=2))
            admissions.append(
                Admission(
                    patient_id=self.rng.choice(patients).id,
                    bed_id=self.rng.choice(all_beds).id,
                    admitting_doctor_id=self.rng.choice(doctors).id,
                    admitted_at=admitted,
                    discharged_at=discharged,
                    status=AdmissionStatus.DISCHARGED,
                    reason=self.rng.choice(ADMISSION_REASONS),
                    discharge_summary="Condition improved. Discharged with medication and advice.",
                )
            )
        # Current occupancy.
        for _, (_ward, beds, occupied) in wards.items():
            for bed in [b for b in beds if b.status == BedStatus.AVAILABLE][:occupied]:
                patient = free_patients.pop()
                admissions.append(
                    Admission(
                        patient_id=patient.id,
                        bed_id=bed.id,
                        admitting_doctor_id=self.rng.choice(doctors).id,
                        admitted_at=self.now
                        - timedelta(days=self.rng.randint(0, 9), hours=self.rng.randint(1, 20)),
                        status=AdmissionStatus.ADMITTED,
                        reason=self.rng.choice(ADMISSION_REASONS),
                    )
                )
                bed.status = BedStatus.OCCUPIED
        self.db.add_all(admissions)
        self.db.flush()
        return admissions

    def _pay(self, invoice: Invoice, issued: datetime, receptionist: User) -> None:
        roll = self.rng.random()
        if roll < 0.80:
            portion = invoice.total
        elif roll < 0.88:
            portion = (invoice.total * Decimal(self.rng.choice(["0.3", "0.5", "0.6"]))).quantize(
                Decimal("0.01")
            )
        else:
            invoice.status = InvoiceStatus.UNPAID
            return
        paid_at = min(issued + timedelta(hours=self.rng.randint(0, 48)), self.now)
        if self.rng.random() < 0.04:  # an occasional declined (simulated) attempt first
            invoice.payments.append(
                Payment(
                    amount=portion,
                    method=PaymentMethod.CARD,
                    status=PaymentStatus.FAILED,
                    transaction_ref=self.txn_ref(),
                    paid_at=paid_at - timedelta(minutes=5),
                    received_by=receptionist.id,
                )
            )
        methods, weights = zip(*PAYMENT_METHOD_WEIGHTS.items(), strict=True)
        invoice.payments.append(
            Payment(
                amount=portion,
                method=self.rng.choices(methods, weights)[0],
                status=PaymentStatus.SUCCESS,
                transaction_ref=self.txn_ref(),
                paid_at=paid_at,
                received_by=receptionist.id,
            )
        )
        invoice.status = (
            InvoiceStatus.PAID if portion >= invoice.total else InvoiceStatus.PARTIALLY_PAID
        )

    def _invoice(
        self,
        patient_id: int,
        issued: datetime,
        lines: list[dict],
        user: User,
        admission_id: int | None = None,
    ) -> Invoice:
        subtotal = sum((line["unit_price"] * line["quantity"] for line in lines), Decimal("0"))
        invoice = Invoice(
            invoice_number=self.next_invoice_number(issued),
            patient_id=patient_id,
            admission_id=admission_id,
            issued_at=issued,
            due_date=(issued + timedelta(days=15)).date(),
            subtotal=subtotal,
            discount=Decimal("0"),
            tax=Decimal("0"),
            total=subtotal,
            status=InvoiceStatus.UNPAID,
            created_by=user.id,
            created_at=issued,
            items=[InvoiceItem(**line) for line in lines],
        )
        self.db.add(invoice)
        return invoice

    def invoices(
        self, appointments: list[Appointment], admissions: list[Admission], receptionist: User
    ) -> None:
        doctors = {d.id: d for d in self.db.scalars(select(Doctor))}
        rx_by_appt: dict[int, list[PrescriptionItem]] = {}
        for rx in self.db.scalars(
            select(Prescription).where(Prescription.status == PrescriptionStatus.DISPENSED)
        ):
            rx_by_appt.setdefault(rx.appointment_id, []).extend(rx.items)
        cutoff = self.now - timedelta(hours=3)
        for appt in sorted(appointments, key=lambda a: a.scheduled_at):
            # Leave some recent visits unbilled so "generate invoice" has work to do.
            if appt.status != AppointmentStatus.COMPLETED or appt.scheduled_at > cutoff:
                continue
            if self.rng.random() < 0.12:
                continue
            doctor = doctors[appt.doctor_id]
            when = appt.scheduled_at.astimezone(self.tz).strftime("%d %b %Y")
            lines = [
                {
                    "item_type": InvoiceItemType.CONSULTATION,
                    "description": f"Consultation - {doctor.full_name} ({doctor.department.name}), "
                    f"{when}",
                    "quantity": 1,
                    "unit_price": doctor.consultation_fee,
                    "appointment_id": appt.id,
                }
            ]
            for item in rx_by_appt.get(appt.id, []):
                lines.append(
                    {
                        "item_type": InvoiceItemType.MEDICINE,
                        "description": f"{item.medicine.name} ({item.dosage}) x {item.quantity}",
                        "quantity": item.quantity,
                        "unit_price": item.medicine.unit_price,
                        "prescription_item_id": item.id,
                    }
                )
            if self.rng.random() < 0.18:
                test, price = self.rng.choice(DIAGNOSTIC_TESTS)
                lines.append(
                    {
                        "item_type": InvoiceItemType.DIAGNOSTIC,
                        "description": test,
                        "quantity": 1,
                        "unit_price": Decimal(price),
                    }
                )
            issued = appt.scheduled_at + timedelta(hours=1, minutes=30)
            invoice = self._invoice(appt.patient_id, issued, lines, receptionist)
            self._pay(invoice, issued, receptionist)

        for adm in sorted(admissions, key=lambda a: a.admitted_at):
            if adm.status != AdmissionStatus.DISCHARGED:
                continue
            days = max(1, -(-int((adm.discharged_at - adm.admitted_at).total_seconds()) // 86400))
            ward = adm.bed.ward
            lines = [
                {
                    "item_type": InvoiceItemType.ROOM,
                    "description": f"Room charges - {ward.name}, bed {adm.bed.bed_number} "
                    f"({days} day{'s' if days > 1 else ''})",
                    "quantity": days,
                    "unit_price": ward.daily_rate,
                    "admission_id": adm.id,
                }
            ]
            for test, price in self.rng.sample(DIAGNOSTIC_TESTS, self.rng.randint(1, 3)):
                lines.append(
                    {
                        "item_type": InvoiceItemType.DIAGNOSTIC,
                        "description": test,
                        "quantity": 1,
                        "unit_price": Decimal(price),
                    }
                )
            invoice = self._invoice(
                adm.patient_id, adm.discharged_at, lines, receptionist, admission_id=adm.id
            )
            self._pay(invoice, adm.discharged_at, receptionist)
        self.db.flush()
        # Continue the database sequence after the explicitly numbered seed invoices.
        self.db.execute(
            text("SELECT setval('invoice_number_seq', :n)"), {"n": max(self.invoice_counter, 1)}
        )

    def run(self) -> None:
        users = self.users()
        doctors, diagnoses = self.departments_and_doctors(users[Role.DOCTOR])
        patients = self.patients()
        wards = self.wards_and_beds()
        medicines = self.medicines()
        appointments = self.appointments(doctors, patients, diagnoses, users[Role.RECEPTIONIST])
        events = self.prescriptions(appointments, medicines, users[Role.PHARMACIST])
        self.stock_ledger(medicines, events, users[Role.PHARMACIST])
        admissions = self.admissions(wards, patients, doctors)
        self.invoices(appointments, admissions, users[Role.RECEPTIONIST])
        logger.info(
            "Seeded %d doctors, %d patients, %d appointments, %d admissions, %d invoices",
            len(doctors),
            len(patients),
            len(appointments),
            len(admissions),
            self.invoice_counter,
        )


def seed_demo_data(db: Session, password: str) -> bool:
    """Seed everything inside the caller's transaction. Returns False if data exists."""
    if db.scalar(select(func.count(User.id))):
        return False
    _Seeder(db, password).run()
    return True
