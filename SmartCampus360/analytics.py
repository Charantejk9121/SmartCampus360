"""
analytics.py - MongoDB aggregation pipelines for SmartCampus 360.

All metrics are derived from live database queries.
Each pipeline is implemented as a standalone, documented function.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from database import get_complaints_collection, get_students_collection
import config

logger = logging.getLogger(__name__)


# ─── Pipeline 1: Complaints grouped by Category ───────────────────────────────
def complaints_by_category() -> list[dict]:
    """
    $group complaints by category → count.
    $sort descending by count.
    """
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "category": "$_id", "count": 1}},
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Pipeline 2: Complaints grouped by Status ─────────────────────────────────
def complaints_by_status() -> list[dict]:
    """
    $group complaints by status → count.
    Returns all status values even if some have zero in the dataset
    by merging with the full list.
    """
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "status": "$_id", "count": 1}},
    ]
    raw = {r["status"]: r["count"] for r in get_complaints_collection().aggregate(pipeline)}
    return [{"status": s, "count": raw.get(s, 0)} for s in config.STATUSES]


# ─── Pipeline 3: Priority Distribution ───────────────────────────────────────
def complaints_by_priority() -> list[dict]:
    """
    $group complaints by priority → count.
    """
    pipeline = [
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "priority": "$_id", "count": 1}},
    ]
    raw = {r["priority"]: r["count"] for r in get_complaints_collection().aggregate(pipeline)}
    return [{"priority": p, "count": raw.get(p, 0)} for p in config.PRIORITIES]


# ─── Pipeline 4: Date-based Complaint Trends (Daily) ─────────────────────────
def complaint_trends_daily(days: int = 30) -> list[dict]:
    """
    Group complaint counts by calendar day for the last `days` days.
    Uses $dateToString to produce a YYYY-MM-DD key compatible with all
    MongoDB server versions (avoids $dateTrunc version dependency).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$created_at",
                        "timezone": "UTC",
                    }
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "date": "$_id", "count": 1}},
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Pipeline 5: Average Resolution Time by Category ─────────────────────────
def avg_resolution_time_by_category() -> list[dict]:
    """
    For resolved complaints with both created_at and resolved_at,
    calculate average resolution time in hours per category.

    $subtract yields milliseconds → divide by 3_600_000 for hours.
    Excludes complaints where resolved_at ≤ created_at (data anomaly).
    """
    pipeline = [
        {
            "$match": {
                "status": "Resolved",
                "resolved_at": {"$ne": None, "$type": "date"},
                "created_at": {"$type": "date"},
            }
        },
        {
            "$project": {
                "category": 1,
                "resolution_ms": {
                    "$subtract": ["$resolved_at", "$created_at"]
                },
            }
        },
        {"$match": {"resolution_ms": {"$gt": 0}}},
        {
            "$group": {
                "_id": "$category",
                "avg_hours": {
                    "$avg": {
                        "$divide": ["$resolution_ms", 3_600_000]
                    }
                },
                "complaint_count": {"$sum": 1},
            }
        },
        {"$sort": {"avg_hours": 1}},
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "avg_hours": {"$round": ["$avg_hours", 2]},
                "complaint_count": 1,
            }
        },
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Pipeline 6: Department-wise Workload ────────────────────────────────────
def department_workload() -> list[dict]:
    """
    Per department: total complaints, unresolved count, resolved count.
    """
    pipeline = [
        {
            "$group": {
                "_id": "$department",
                "total": {"$sum": 1},
                "unresolved": {
                    "$sum": {
                        "$cond": [{"$ne": ["$status", "Resolved"]}, 1, 0]
                    }
                },
                "resolved": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "Resolved"]}, 1, 0]
                    }
                },
            }
        },
        {"$sort": {"total": -1}},
        {
            "$project": {
                "_id": 0,
                "department": "$_id",
                "total": 1,
                "unresolved": 1,
                "resolved": 1,
            }
        },
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Pipeline 7: High-Priority Unresolved Complaints ─────────────────────────
def high_priority_unresolved(limit: int = 20) -> list[dict]:
    """
    $match High-priority complaints that are Pending or In Progress.
    $project essential fields only.
    $sort by created_at descending (oldest first = most urgent).
    """
    pipeline = [
        {
            "$match": {
                "priority": "High",
                "status": {"$in": ["Pending", "In Progress"]},
            }
        },
        {"$sort": {"created_at": 1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "complaint_id": 1,
                "student_id": 1,
                "category": 1,
                "description": 1,
                "location": 1,
                "department": 1,
                "status": 1,
                "created_at": 1,
            }
        },
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Pipeline 8: Student Complaint History ───────────────────────────────────
def student_complaint_history(student_id: str) -> list[dict]:
    """
    Retrieve all complaints for a student and optionally $lookup
    the student document.
    """
    pipeline = [
        {"$match": {"student_id": student_id}},
        {"$sort": {"created_at": -1}},
        {
            "$lookup": {
                "from": config.STUDENTS_COLLECTION,
                "localField": "student_id",
                "foreignField": "student_id",
                "as": "student_info",
            }
        },
        {
            "$project": {
                "_id": 0,
                "complaint_id": 1,
                "category": 1,
                "description": 1,
                "priority": 1,
                "status": 1,
                "created_at": 1,
                "resolved_at": 1,
                "student_name": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$student_info.name", 0]},
                        "Unknown",
                    ]
                },
            }
        },
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Pipeline 9: Top-5 Complaint Categories ──────────────────────────────────
def top_five_categories() -> list[dict]:
    """Return the 5 most common complaint categories."""
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
        {"$project": {"_id": 0, "category": "$_id", "count": 1}},
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Pipeline 10: Resolved vs Unresolved Summary ──────────────────────────────
def resolved_vs_unresolved() -> dict:
    """
    Return counts for:
      resolved, unresolved (Pending + In Progress), total.
    """
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "resolved": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "Resolved"]}, 1, 0]
                    }
                },
                "pending": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "Pending"]}, 1, 0]
                    }
                },
                "in_progress": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "In Progress"]}, 1, 0]
                    }
                },
                "high_priority_unresolved": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$priority", "High"]},
                                    {"$ne": ["$status", "Resolved"]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {"$project": {"_id": 0}},
    ]
    results = list(get_complaints_collection().aggregate(pipeline))
    if not results:
        return {
            "total": 0,
            "resolved": 0,
            "pending": 0,
            "in_progress": 0,
            "high_priority_unresolved": 0,
            "resolution_rate": 0.0,
        }
    r = results[0]
    total = r.get("total", 0)
    resolved = r.get("resolved", 0)
    r["resolution_rate"] = round((resolved / total) * 100, 1) if total > 0 else 0.0
    return r


# ─── Bonus: Monthly Trend ─────────────────────────────────────────────────────
def complaint_trends_monthly(months: int = 12) -> list[dict]:
    """Group complaint counts by YYYY-MM for the last `months` months."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m",
                        "date": "$created_at",
                        "timezone": "UTC",
                    }
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "month": "$_id", "count": 1}},
    ]
    return list(get_complaints_collection().aggregate(pipeline))


# ─── Overall Summary Aggregation ──────────────────────────────────────────────
def get_dashboard_summary() -> dict:
    """
    Return a comprehensive dashboard summary dict.
    All metrics are derived from MongoDB aggregations.
    """
    summary = resolved_vs_unresolved()

    # Average resolution time (overall)
    avg_pipeline = [
        {
            "$match": {
                "status": "Resolved",
                "resolved_at": {"$ne": None, "$type": "date"},
                "created_at": {"$type": "date"},
            }
        },
        {
            "$project": {
                "resolution_ms": {"$subtract": ["$resolved_at", "$created_at"]}
            }
        },
        {"$match": {"resolution_ms": {"$gt": 0}}},
        {
            "$group": {
                "_id": None,
                "avg_hours": {
                    "$avg": {"$divide": ["$resolution_ms", 3_600_000]}
                },
            }
        },
    ]
    avg_result = list(get_complaints_collection().aggregate(avg_pipeline))
    summary["avg_resolution_hours"] = (
        round(avg_result[0]["avg_hours"], 1) if avg_result else None
    )

    return summary
