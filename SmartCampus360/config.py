"""
config.py - Configuration management for SmartCampus 360
Reads connection settings from environment variables with safe local fallbacks.
"""

import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# ─── MongoDB Connection ────────────────────────────────────────────────────────
MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "campus_complaints")

# ─── Server Timeouts (milliseconds) ───────────────────────────────────────────
SERVER_SELECTION_TIMEOUT_MS: int = int(
    os.getenv("SERVER_SELECTION_TIMEOUT_MS", "5000")
)
CONNECT_TIMEOUT_MS: int = int(os.getenv("CONNECT_TIMEOUT_MS", "5000"))
SOCKET_TIMEOUT_MS: int = int(os.getenv("SOCKET_TIMEOUT_MS", "10000"))

# ─── Collections ──────────────────────────────────────────────────────────────
COMPLAINTS_COLLECTION: str = "complaints"
STUDENTS_COLLECTION: str = "students"

# ─── Application Metadata ─────────────────────────────────────────────────────
APP_NAME: str = "SmartCampus 360"
APP_VERSION: str = "1.0.0"
APP_DESCRIPTION: str = (
    "Intelligent Campus Complaint & Facility Analytics System"
)
COURSE_NAME: str = "CSE494: Intelligent NoSQL Databases"

# ─── Domain Enumerations ──────────────────────────────────────────────────────
CATEGORIES: list[str] = [
    "WiFi",
    "Electricity",
    "Water",
    "Cleanliness",
    "Classroom Equipment",
    "Hostel Maintenance",
    "Security",
    "Other",
]

PRIORITIES: list[str] = ["Low", "Medium", "High"]

STATUSES: list[str] = ["Pending", "In Progress", "Resolved"]

# Default department assignments per category
CATEGORY_DEPARTMENT_MAP: dict[str, str] = {
    "WiFi": "IT Support",
    "Electricity": "Electrical & Utilities",
    "Water": "Plumbing & Utilities",
    "Cleanliness": "Housekeeping",
    "Classroom Equipment": "Facilities Management",
    "Hostel Maintenance": "Hostel Administration",
    "Security": "Campus Security",
    "Other": "General Administration",
}

DEPARTMENTS: list[str] = sorted(set(CATEGORY_DEPARTMENT_MAP.values()))

# ─── Pagination ───────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# ─── Validation ───────────────────────────────────────────────────────────────
MIN_DESCRIPTION_LENGTH: int = 10
MAX_DESCRIPTION_LENGTH: int = 1000
