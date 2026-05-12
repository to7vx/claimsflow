"""Reference data for the Saudi healthcare context.

Names, cities, ICD-10 codes, CPT codes, and plan templates used by the
synthetic-data generators. Kept in a single module so the data is easy to
audit and extend — and easy to swap out for licensed reference data later.

> [!NOTE]
> ICD-10 / CPT codes here use the *public* code lists. The descriptions are
> paraphrased — neither WHO nor AMA license the textual descriptions for
> redistribution. For a real product, license proper data.
"""

from __future__ import annotations

# ─────────────────────────── Geography ───────────────────────────

SAUDI_CITIES: list[str] = [
    "Riyadh",
    "Jeddah",
    "Mecca",
    "Medina",
    "Dammam",
    "Khobar",
    "Dhahran",
    "Tabuk",
    "Abha",
    "Taif",
    "Buraidah",
    "Hail",
    "Najran",
    "Jubail",
    "Yanbu",
]

# ─────────────────────────── Names ───────────────────────────

MALE_NAMES_AR: list[str] = [
    "محمد", "أحمد", "عبدالله", "علي", "خالد", "فيصل", "سلطان", "سعود",
    "ناصر", "بندر", "تركي", "ماجد", "سعد", "نواف", "عبدالرحمن", "عبدالعزيز",
    "فهد", "وليد", "ياسر", "زياد",
]
MALE_NAMES_EN: list[str] = [
    "Mohammed", "Ahmed", "Abdullah", "Ali", "Khalid", "Faisal", "Sultan", "Saud",
    "Nasser", "Bandar", "Turki", "Majed", "Saad", "Nawaf", "AbdulRahman", "AbdulAziz",
    "Fahad", "Waleed", "Yasser", "Ziyad",
]

FEMALE_NAMES_AR: list[str] = [
    "فاطمة", "نورة", "عائشة", "مريم", "هند", "ريم", "سارة", "لطيفة",
    "منى", "أمل", "ليلى", "هدى", "جواهر", "العنود", "دانة", "غادة",
    "روان", "شيخة", "مها", "نوف",
]
FEMALE_NAMES_EN: list[str] = [
    "Fatima", "Noura", "Aisha", "Mariam", "Hind", "Reem", "Sara", "Latifa",
    "Mona", "Amal", "Layla", "Huda", "Jawaher", "AlAnoud", "Dana", "Ghada",
    "Rawan", "Shaikha", "Maha", "Nouf",
]

FAMILY_NAMES_AR: list[str] = [
    "آل سعود", "العتيبي", "الشمري", "الحربي", "القحطاني", "الدوسري", "المطيري",
    "الزهراني", "الغامدي", "العنزي", "المالكي", "الشهري", "الجهني", "البلوي",
    "العمري", "الحارثي", "السبيعي", "النفيعي", "الخالدي", "الرشيد",
]
FAMILY_NAMES_EN: list[str] = [
    "Al-Saud", "Al-Otaibi", "Al-Shammari", "Al-Harbi", "Al-Qahtani", "Al-Dosari",
    "Al-Mutairi", "Al-Zahrani", "Al-Ghamdi", "Al-Anazi", "Al-Maliki", "Al-Shahri",
    "Al-Juhani", "Al-Balawi", "Al-Omari", "Al-Harthi", "Al-Subaie", "Al-Nufaie",
    "Al-Khalidi", "Al-Rasheed",
]

# ─────────────────────────── Provider names ───────────────────────────

PROVIDER_NAME_PREFIXES_EN: list[str] = [
    "Specialist", "International", "National", "Central", "Royal", "Care",
    "Medical", "Health", "Family", "Wellness",
]
PROVIDER_NAME_PREFIXES_AR: list[str] = [
    "التخصصي", "الدولي", "الوطني", "المركزي", "الملكي", "الرعاية",
    "الطبي", "الصحي", "العائلي", "العافية",
]

# ─────────────────────────── Plans ───────────────────────────

PLAN_TEMPLATES: list[dict] = [
    {
        "name_en": "Gold Family",
        "tier": "gold",
        "annual_limit": 500_000.0,
        "copay_percent": 10.0,
        "deductible": 0.0,
        "covered": ["outpatient", "inpatient", "pharmacy", "dental", "optical"],
        "exclusions": ["F.*", "Z41.2"],  # mental health, elective cosmetic
    },
    {
        "name_en": "Silver Individual",
        "tier": "silver",
        "annual_limit": 200_000.0,
        "copay_percent": 20.0,
        "deductible": 1_000.0,
        "covered": ["outpatient", "inpatient", "pharmacy"],
        "exclusions": ["F.*", "Z41.2", "K00.*"],  # + most dental
    },
    {
        "name_en": "Bronze Essentials",
        "tier": "bronze",
        "annual_limit": 75_000.0,
        "copay_percent": 30.0,
        "deductible": 3_000.0,
        "covered": ["outpatient", "inpatient"],
        "exclusions": ["F.*", "Z41.2", "K00.*", "H52.*"],  # + optical
    },
    {
        "name_en": "Platinum Family",
        "tier": "platinum",
        "annual_limit": 1_000_000.0,
        "copay_percent": 0.0,
        "deductible": 0.0,
        "covered": ["outpatient", "inpatient", "pharmacy", "dental", "optical", "maternity"],
        "exclusions": ["Z41.2"],
    },
]

# ─────────────────────────── Clinical codes ───────────────────────────
# Common Saudi outpatient diagnoses. Code → English description.

ICD10_COMMON: dict[str, str] = {
    "E11.9": "Type 2 diabetes without complications",
    "E11.65": "Type 2 diabetes with hyperglycemia",
    "I10": "Essential hypertension",
    "J45.909": "Asthma, unspecified, uncomplicated",
    "J06.9": "Acute upper respiratory infection",
    "K21.9": "Gastro-esophageal reflux disease",
    "M54.5": "Low back pain",
    "R51": "Headache",
    "N39.0": "Urinary tract infection",
    "E78.5": "Hyperlipidemia, unspecified",
    "B34.9": "Viral infection, unspecified",
    "L20.9": "Atopic dermatitis",
    "H10.9": "Conjunctivitis, unspecified",
    "K59.00": "Constipation, unspecified",
    "F32.9": "Major depressive disorder (excluded by most plans)",
    "Z00.00": "General adult medical examination",
}

# Pediatric subset — used for ~25% of claims to model family coverage.
ICD10_PEDIATRIC: dict[str, str] = {
    "J06.9": "Acute upper respiratory infection",
    "H66.90": "Otitis media, unspecified",
    "A09": "Infectious gastroenteritis",
    "L20.9": "Atopic dermatitis",
    "J45.909": "Asthma, unspecified",
    "Z00.121": "Routine child health exam with abnormal findings",
}

# CPT procedure codes. Code → (English description, typical SAR cost).
CPT_COMMON: dict[str, tuple[str, float]] = {
    "99213": ("Office visit, established patient, 20–29 min", 250.0),
    "99214": ("Office visit, established patient, 30–39 min", 380.0),
    "99203": ("Office visit, new patient, 30–44 min", 450.0),
    "80050": ("General health panel (lab)", 180.0),
    "80061": ("Lipid panel", 120.0),
    "83036": ("HbA1c glycated hemoglobin", 90.0),
    "84443": ("TSH thyroid stimulating hormone", 110.0),
    "85025": ("Complete blood count with differential", 70.0),
    "71046": ("Chest X-ray, 2 views", 220.0),
    "76700": ("Abdominal ultrasound, complete", 480.0),
    "93000": ("Electrocardiogram", 180.0),
    "94010": ("Spirometry / pulmonary function", 240.0),
    "73610": ("Foot X-ray", 200.0),
    "12001": ("Simple wound repair", 350.0),
    "90471": ("Immunization administration", 60.0),
    "J7613": ("Albuterol inhalation solution (pharmacy)", 45.0),
    "J1885": ("Ketorolac injection (pharmacy)", 75.0),
}

# Reasonable (diagnosis, procedure-set) pairings for medical-necessity logic.
# Stage 3 will flag claims whose procedures don't appear in this dict.
APPROPRIATE_PROCEDURES: dict[str, list[str]] = {
    "E11.9": ["99213", "99214", "83036", "80061", "85025"],
    "E11.65": ["99214", "83036", "80061", "85025"],
    "I10": ["99213", "99214", "93000", "80061"],
    "J45.909": ["99213", "94010", "71046", "J7613"],
    "J06.9": ["99213", "85025"],
    "K21.9": ["99213", "99214"],
    "M54.5": ["99213", "73610", "12001"],
    "R51": ["99213", "85025"],
    "N39.0": ["99213", "80050", "85025"],
    "E78.5": ["99213", "80061"],
    "B34.9": ["99213", "85025"],
    "L20.9": ["99213"],
    "H10.9": ["99213"],
    "K59.00": ["99213", "76700"],
    "F32.9": ["99213", "99214"],
    "Z00.00": ["99203", "99213", "80050", "85025"],
    "H66.90": ["99213", "90471"],
    "A09": ["99213", "85025"],
    "Z00.121": ["99213", "80050", "85025", "90471"],
}
