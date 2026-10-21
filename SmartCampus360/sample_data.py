"""
sample_data.py - Realistic synthetic dataset for SmartCampus 360 demonstrations.

All records are clearly fictitious campus data.
Insertion is idempotent: existing records (matched by complaint_id / student_id)
are skipped — no existing data is overwritten.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
import random

from pymongo.errors import BulkWriteError

import config
from database import get_complaints_collection, get_students_collection

logger = logging.getLogger(__name__)

# ─── Deterministic seed for reproducible demonstrations ───────────────────────
random.seed(42)

# ─── Synthetic Students (20 records) ─────────────────────────────────────────
SAMPLE_STUDENTS = [
    {"student_id": "STU101", "name": "Arjun Mehta",      "email": "arjun.mehta@campus.edu",      "building": "Block A"},
    {"student_id": "STU102", "name": "Priya Sharma",     "email": "priya.sharma@campus.edu",     "building": "Block B"},
    {"student_id": "STU103", "name": "Rohit Verma",      "email": "rohit.verma@campus.edu",      "building": "Block C"},
    {"student_id": "STU104", "name": "Sneha Patel",      "email": "sneha.patel@campus.edu",      "building": "Block D"},
    {"student_id": "STU105", "name": "Vikram Singh",     "email": "vikram.singh@campus.edu",     "building": "Block A"},
    {"student_id": "STU106", "name": "Ananya Rao",       "email": "ananya.rao@campus.edu",       "building": "Block E"},
    {"student_id": "STU107", "name": "Karthik Nair",     "email": "karthik.nair@campus.edu",     "building": "Block B"},
    {"student_id": "STU108", "name": "Meera Iyer",       "email": "meera.iyer@campus.edu",       "building": "Block F"},
    {"student_id": "STU109", "name": "Aditya Kumar",     "email": "aditya.kumar@campus.edu",     "building": "Block C"},
    {"student_id": "STU110", "name": "Pooja Gupta",      "email": "pooja.gupta@campus.edu",      "building": "Block G"},
    {"student_id": "STU111", "name": "Rahul Desai",      "email": "rahul.desai@campus.edu",      "building": "Block D"},
    {"student_id": "STU112", "name": "Divya Krishnan",   "email": "divya.krishnan@campus.edu",   "building": "Block H"},
    {"student_id": "STU113", "name": "Siddharth Joshi",  "email": "siddharth.joshi@campus.edu",  "building": "Block A"},
    {"student_id": "STU114", "name": "Kavya Nambiar",    "email": "kavya.nambiar@campus.edu",    "building": "Block B"},
    {"student_id": "STU115", "name": "Nikhil Pandey",    "email": "nikhil.pandey@campus.edu",    "building": "Block E"},
    {"student_id": "STU116", "name": "Shreya Bhatt",     "email": "shreya.bhatt@campus.edu",     "building": "Block C"},
    {"student_id": "STU117", "name": "Varun Malhotra",   "email": "varun.malhotra@campus.edu",   "building": "Block F"},
    {"student_id": "STU118", "name": "Nisha Reddy",      "email": "nisha.reddy@campus.edu",      "building": "Block D"},
    {"student_id": "STU119", "name": "Ayush Saxena",     "email": "ayush.saxena@campus.edu",     "building": "Block G"},
    {"student_id": "STU120", "name": "Tanvi Kulkarni",   "email": "tanvi.kulkarni@campus.edu",   "building": "Block H"},
]

# ─── Complaint templates ───────────────────────────────────────────────────────
_COMPLAINT_TEMPLATES = [
    # WiFi
    ("WiFi",                "IT Support",              "High",   "WiFi connectivity is completely down in the entire floor. Students cannot attend online classes or submit assignments."),
    ("WiFi",                "IT Support",              "Medium", "Internet speed is extremely slow in the reading room. Pages take over a minute to load even on wired connections."),
    ("WiFi",                "IT Support",              "Low",    "WiFi password needs to be updated for the new semester. Several students received incorrect credentials."),
    ("WiFi",                "IT Support",              "High",   "No internet access in Laboratory 3 for the past three days. Research work is severely impacted."),
    ("WiFi",                "IT Support",              "Medium", "WiFi drops out intermittently in the hostel common area throughout the evening hours."),
    # Electricity
    ("Electricity",         "Electrical & Utilities",  "High",   "Power outage in Block C since yesterday evening. Fans, lights, and charging points are all non-functional."),
    ("Electricity",         "Electrical & Utilities",  "High",   "Short circuit in Room 204 causing repeated tripping of the main breaker and is a potential fire hazard."),
    ("Electricity",         "Electrical & Utilities",  "Medium", "Street lights on the eastern pathway between the library and hostel have been non-functional for a week."),
    ("Electricity",         "Electrical & Utilities",  "Low",    "One of the three ceiling fans in Classroom 101 has stopped working. The room gets uncomfortably warm in the afternoon."),
    ("Electricity",         "Electrical & Utilities",  "Medium", "Generator backup does not activate during power cuts in the girls hostel. Inverter power is insufficient for all rooms."),
    # Water
    ("Water",               "Plumbing & Utilities",    "High",   "No water supply in Block D washrooms for the past 48 hours. Situation is becoming a sanitation emergency."),
    ("Water",               "Plumbing & Utilities",    "High",   "Overhead tank on the third floor is leaking heavily causing damage to the ceiling below and posing a safety risk."),
    ("Water",               "Plumbing & Utilities",    "Medium", "Water pressure in the ground floor washrooms is too low during morning peak hours for adequate use."),
    ("Water",               "Plumbing & Utilities",    "Low",    "Drinking water cooler in the science building canteen is not working. Students have no cold water access."),
    ("Water",               "Plumbing & Utilities",    "Medium", "Drain in the boys hostel ground floor bathroom is blocked causing water logging every morning."),
    # Cleanliness
    ("Cleanliness",         "Housekeeping",            "High",   "Garbage bins in the cafeteria area have not been emptied for three days causing foul odour and health concerns."),
    ("Cleanliness",         "Housekeeping",            "Medium", "Washrooms on the second floor of the academic block are not being cleaned regularly. Soap dispensers are empty."),
    ("Cleanliness",         "Housekeeping",            "Low",    "Corridor outside Room 310 has not been swept in two days. Dust and litter are accumulating noticeably."),
    ("Cleanliness",         "Housekeeping",            "Medium", "Common room in Block F has leftover food waste from an event two days ago and has not been cleaned since."),
    ("Cleanliness",         "Housekeeping",            "Low",    "Spider webs and dust on the ceiling fans and lights in Seminar Hall 2 need to be cleaned before the scheduled event."),
    # Classroom Equipment
    ("Classroom Equipment", "Facilities Management",   "High",   "Projector in Room 205 has stopped working completely. Multiple lectures are being disrupted as alternatives are unavailable."),
    ("Classroom Equipment", "Facilities Management",   "Medium", "Air conditioner in the computer lab runs only intermittently and does not maintain the required temperature for equipment."),
    ("Classroom Equipment", "Facilities Management",   "High",   "All charging ports in the smart classroom are non-functional. Students cannot charge laptops during long sessions."),
    ("Classroom Equipment", "Facilities Management",   "Low",    "Whiteboard in Classroom 108 has permanent stains that cannot be erased with regular markers and cleaning."),
    ("Classroom Equipment", "Facilities Management",   "Medium", "Speaker system in the auditorium produces distorted audio. Urgent repair needed before convocation rehearsal."),
    # Hostel Maintenance
    ("Hostel Maintenance",  "Hostel Administration",   "High",   "Door lock on Room 412 is broken. The door cannot be locked from inside, posing a serious security concern for residents."),
    ("Hostel Maintenance",  "Hostel Administration",   "Medium", "Window pane in Room 318 is cracked and shaking in wind. It needs to be replaced before the winter season."),
    ("Hostel Maintenance",  "Hostel Administration",   "Low",    "Mattress in Room 224 is severely worn and causing back discomfort. Replacement was requested two months ago."),
    ("Hostel Maintenance",  "Hostel Administration",   "Medium", "Bathroom tiles on the third floor corridor are cracked and slippery, posing a potential fall hazard for students."),
    ("Hostel Maintenance",  "Hostel Administration",   "High",   "Roof leaking in Room 501 during rain, causing water to drip onto beds and furniture. Books and electronics at risk."),
    # Security
    ("Security",            "Campus Security",         "High",   "Main entry gate camera is non-functional. There is no CCTV coverage of the primary entrance for over a week."),
    ("Security",            "Campus Security",         "High",   "Unauthorized individuals were spotted inside the hostel premises late at night. Guard post was unattended."),
    ("Security",            "Campus Security",         "Medium", "Library entry gate access card reader is malfunctioning. Students with valid cards are being denied entry."),
    ("Security",            "Campus Security",         "Low",    "Perimeter wall near the sports complex has a gap large enough for a person to pass through. Needs immediate sealing."),
    ("Security",            "Campus Security",         "Medium", "Parking area lights are not working making it unsafe for students returning to hostels after late-night study sessions."),
    # Other
    ("Other",               "General Administration",  "Medium", "Campus bus schedule has not been updated and the new timetable is unavailable on the notice board or the portal."),
    ("Other",               "General Administration",  "Low",    "Vending machine near the library entrance has been accepting payment but not dispensing items for three days."),
    ("Other",               "General Administration",  "Medium", "Sports equipment room lock is broken and the room has been inaccessible to students for the past week."),
    ("Other",               "General Administration",  "High",   "First aid kit in the hostel common room is empty. Medical supplies were used during an incident and not replenished."),
    ("Other",               "General Administration",  "Low",    "Notice boards in the academic block have outdated notices from last semester and need to be cleared and updated."),
]

_LOCATIONS = [
    "Block A", "Block B", "Block C", "Block D", "Block E",
    "Block F", "Block G", "Block H",
    "Main Library", "Computer Lab 1", "Computer Lab 2",
    "Seminar Hall 1", "Seminar Hall 2", "Auditorium",
    "Canteen", "Sports Complex", "Administrative Building",
    "Classroom 101", "Classroom 205", "Classroom 310",
    "Boys Hostel Ground Floor", "Girls Hostel Block 3",
]

_STUDENT_IDS = [s["student_id"] for s in SAMPLE_STUDENTS]


def _make_complaint(
    idx: int,
    category: str,
    department: str,
    priority: str,
    description: str,
    days_ago_created: int,
    status: str,
    days_ago_resolved: int | None = None,
) -> dict:
    """Build a single complaint document with BSON dates."""
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(days=days_ago_created, hours=random.randint(0, 23))
    updated_at = created_at + timedelta(hours=random.randint(1, 48))

    resolved_at = None
    if status == "Resolved" and days_ago_resolved is not None:
        resolved_at = now - timedelta(days=days_ago_resolved, hours=random.randint(0, 12))
        if resolved_at <= created_at:
            resolved_at = created_at + timedelta(hours=random.randint(2, 72))
        updated_at = resolved_at

    return {
        "complaint_id": f"CMP{1001 + idx}",
        "student_id": random.choice(_STUDENT_IDS),
        "category": category,
        "description": description,
        "location": random.choice(_LOCATIONS),
        "priority": priority,
        "status": status,
        "department": department,
        "created_at": created_at,
        "updated_at": updated_at,
        "resolved_at": resolved_at,
        "resolution_notes": (
            f"Issue resolved by {department} team. Service restored to normal."
            if status == "Resolved"
            else None
        ),
        "additional_details": None,
    }


def _build_complaints() -> list[dict]:
    """Build ~80 synthetic complaint documents."""
    complaints = []
    idx = 0

    statuses_schedule = [
        # (status, days_ago_created, days_ago_resolved)
        ("Resolved",    60,  55),
        ("Resolved",    58,  53),
        ("Resolved",    55,  50),
        ("Resolved",    52,  48),
        ("Resolved",    50,  45),
        ("Resolved",    48,  43),
        ("Resolved",    45,  40),
        ("Resolved",    42,  38),
        ("Resolved",    40,  36),
        ("Resolved",    38,  34),
        ("Resolved",    35,  30),
        ("Resolved",    33,  28),
        ("Resolved",    30,  26),
        ("Resolved",    28,  24),
        ("Resolved",    25,  21),
        ("Resolved",    22,  18),
        ("Resolved",    20,  16),
        ("Resolved",    18,  14),
        ("Resolved",    15,  11),
        ("Resolved",    12,   8),
        ("Resolved",    10,   6),
        ("Resolved",     8,   4),
        ("Resolved",     6,   3),
        ("Resolved",     5,   2),
        ("Resolved",     4,   1),
        ("In Progress", 30,  None),
        ("In Progress", 25,  None),
        ("In Progress", 20,  None),
        ("In Progress", 18,  None),
        ("In Progress", 15,  None),
        ("In Progress", 12,  None),
        ("In Progress", 10,  None),
        ("In Progress",  8,  None),
        ("In Progress",  6,  None),
        ("In Progress",  5,  None),
        ("Pending",     28,  None),
        ("Pending",     22,  None),
        ("Pending",     18,  None),
        ("Pending",     15,  None),
        ("Pending",     12,  None),
        ("Pending",     10,  None),
        ("Pending",      8,  None),
        ("Pending",      7,  None),
        ("Pending",      6,  None),
        ("Pending",      5,  None),
        ("Pending",      4,  None),
        ("Pending",      3,  None),
        ("Pending",      2,  None),
        ("Pending",      1,  None),
        ("Pending",      0,  None),
    ]

    template_idx = 0
    for status, days_created, days_resolved in statuses_schedule:
        template = _COMPLAINT_TEMPLATES[template_idx % len(_COMPLAINT_TEMPLATES)]
        cat, dept, pri, desc = template

        # For unresolved slots, occasionally keep original priority (some High)
        complaints.append(
            _make_complaint(
                idx=idx,
                category=cat,
                department=dept,
                priority=pri,
                description=desc,
                days_ago_created=days_created,
                status=status,
                days_ago_resolved=days_resolved,
            )
        )
        idx += 1
        template_idx += 1

    # Add more recent complaints for a richer trend chart (last 30 days)
    extra_templates = _COMPLAINT_TEMPLATES * 2
    for day in range(1, 30, 2):
        t = extra_templates[day % len(extra_templates)]
        cat, dept, pri, desc = t
        status = random.choice(["Pending", "In Progress", "Resolved"])
        days_res = random.randint(0, day - 1) if status == "Resolved" and day > 1 else None
        complaints.append(
            _make_complaint(
                idx=idx,
                category=cat,
                department=dept,
                priority=pri,
                description=desc,
                days_ago_created=day,
                status=status,
                days_ago_resolved=days_res,
            )
        )
        idx += 1

    return complaints


def insert_sample_data() -> dict[str, int]:
    """
    Insert sample students and complaints idempotently.
    Existing records (same student_id / complaint_id) are skipped.
    Returns counts of newly inserted documents.
    """
    now = datetime.now(timezone.utc)

    # ── Students ──────────────────────────────────────────────────────────────
    student_col = get_students_collection()
    existing_students = set(student_col.distinct("student_id"))
    new_students = [
        {**s, "created_at": now - timedelta(days=random.randint(180, 360))}
        for s in SAMPLE_STUDENTS
        if s["student_id"] not in existing_students
    ]
    students_inserted = 0
    if new_students:
        try:
            result = student_col.insert_many(new_students, ordered=False)
            students_inserted = len(result.inserted_ids)
        except BulkWriteError as bwe:
            students_inserted = bwe.details.get("nInserted", 0)
            logger.warning("Some student inserts skipped (duplicates): %s", bwe.details)

    # ── Complaints ────────────────────────────────────────────────────────────
    complaint_col = get_complaints_collection()
    existing_complaints = set(complaint_col.distinct("complaint_id"))
    all_complaints = _build_complaints()
    new_complaints = [
        c for c in all_complaints
        if c["complaint_id"] not in existing_complaints
    ]
    complaints_inserted = 0
    if new_complaints:
        try:
            result = complaint_col.insert_many(new_complaints, ordered=False)
            complaints_inserted = len(result.inserted_ids)
        except BulkWriteError as bwe:
            complaints_inserted = bwe.details.get("nInserted", 0)
            logger.warning(
                "Some complaint inserts skipped (duplicates): %s", bwe.details
            )

    logger.info(
        "Sample data inserted: %d students, %d complaints.",
        students_inserted,
        complaints_inserted,
    )
    return {
        "students_inserted": students_inserted,
        "complaints_inserted": complaints_inserted,
        "students_skipped": len(SAMPLE_STUDENTS) - students_inserted,
        "complaints_skipped": len(all_complaints) - complaints_inserted,
    }
