"""
tests/test_analytics.py - Integration tests for aggregation pipelines.
Requires a running MongoDB instance.

Run with:  python -m pytest tests/test_analytics.py -v
"""

import pytest
import sys, os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DB = "test_campus_complaints_analytics"
import config as cfg
cfg.MONGODB_DATABASE = TEST_DB
cfg.COMPLAINTS_COLLECTION = "test_complaints_analytics"
cfg.STUDENTS_COLLECTION = "test_students_analytics"

# Reset singleton so database.py picks up new cfg values
import database as _db_module
_db_module._client = None

import analytics as an
from models import initialize_database
from database import get_database, get_client


# ─── Test fixtures ────────────────────────────────────────────────────────────

def _make_doc(cid, category, status, priority, days_ago, resolved_days_ago=None):
    now = datetime.now(timezone.utc)
    created = now - timedelta(days=days_ago)
    resolved = None
    if status == "Resolved" and resolved_days_ago is not None:
        resolved = now - timedelta(days=resolved_days_ago)
        if resolved <= created:
            resolved = created + timedelta(hours=24)
    return {
        "complaint_id": cid,
        "student_id": "STU001",
        "category": category,
        "description": "Analytics test complaint with sufficient description length.",
        "location": "Test Building",
        "priority": priority,
        "status": status,
        "department": "IT Support",
        "created_at": created,
        "updated_at": created,
        "resolved_at": resolved,
        "resolution_notes": "Done" if status == "Resolved" else None,
        "additional_details": None,
    }


@pytest.fixture(scope="module", autouse=True)
def setup_analytics_db():
    try:
        get_client().admin.command("ping")
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")

    db = get_database()
    db.drop_collection("test_complaints_analytics")
    db.drop_collection("test_students_analytics")
    initialize_database()

    col = db["test_complaints_analytics"]
    sample_docs = [
        _make_doc("CMP_A1", "WiFi",      "Pending",     "High",   5),
        _make_doc("CMP_A2", "WiFi",      "Resolved",    "Medium", 10, 7),
        _make_doc("CMP_A3", "WiFi",      "In Progress", "Low",    2),
        _make_doc("CMP_A4", "Electricity","Pending",    "High",   3),
        _make_doc("CMP_A5", "Electricity","Resolved",   "High",   15, 12),
        _make_doc("CMP_A6", "Water",     "Resolved",    "Medium", 20, 17),
        _make_doc("CMP_A7", "Water",     "Pending",     "Low",    1),
        _make_doc("CMP_A8", "Security",  "In Progress", "High",   4),
        _make_doc("CMP_A9", "Cleanliness","Pending",    "Low",    6),
        _make_doc("CMP_A10","Other",     "Resolved",    "Medium", 30, 25),
    ]
    col.insert_many(sample_docs)

    yield

    db.drop_collection("test_complaints_analytics")
    db.drop_collection("test_students_analytics")


# ─── Pipeline Tests ───────────────────────────────────────────────────────────

class TestAggregationPipelines:

    def test_complaints_by_category_returns_list(self):
        result = an.complaints_by_category()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_complaints_by_category_has_required_keys(self):
        result = an.complaints_by_category()
        for row in result:
            assert "category" in row
            assert "count" in row
            assert row["count"] > 0

    def test_complaints_by_status_covers_all_statuses(self):
        result = an.complaints_by_status()
        statuses = {r["status"] for r in result}
        import config
        for s in config.STATUSES:
            assert s in statuses

    def test_complaints_by_status_counts_correct(self):
        result = an.complaints_by_status()
        status_map = {r["status"]: r["count"] for r in result}
        # 4 Pending, 2 In Progress, 4 Resolved
        assert status_map.get("Pending", 0) == 4
        assert status_map.get("In Progress", 0) == 2
        assert status_map.get("Resolved", 0) == 4

    def test_complaints_by_priority_all_priorities(self):
        result = an.complaints_by_priority()
        assert len(result) == 3
        priorities = {r["priority"] for r in result}
        assert "High" in priorities
        assert "Medium" in priorities
        assert "Low" in priorities

    def test_complaint_trends_daily_returns_dates(self):
        result = an.complaint_trends_daily(days=60)
        assert isinstance(result, list)
        if result:
            assert "date" in result[0]
            assert "count" in result[0]

    def test_avg_resolution_time_by_category_positive(self):
        result = an.avg_resolution_time_by_category()
        assert isinstance(result, list)
        for row in result:
            assert row["avg_hours"] > 0, f"avg_hours should be positive: {row}"

    def test_avg_resolution_time_excludes_unresolved(self):
        result = an.avg_resolution_time_by_category()
        # Only resolved categories appear
        result_cats = {r["category"] for r in result}
        # WiFi, Electricity, Water, Other have resolved complaints
        assert "WiFi" in result_cats
        assert "Electricity" in result_cats

    def test_department_workload_totals_correct(self):
        result = an.department_workload()
        assert isinstance(result, list)
        total = sum(r["total"] for r in result)
        assert total == 10  # 10 sample documents

    def test_department_workload_unresolved_count(self):
        result = an.department_workload()
        dept_map = {r["department"]: r for r in result}
        it = dept_map.get("IT Support", {})
        # All 10 go to IT Support in our test data
        assert it.get("total", 0) == 10
        assert it.get("resolved", 0) == 4
        assert it.get("unresolved", 0) == 6

    def test_high_priority_unresolved_only_high_pending(self):
        result = an.high_priority_unresolved(limit=20)
        for row in result:
            assert row["priority"] == "High"
            assert row["status"] != "Resolved"

    def test_resolved_vs_unresolved_totals(self):
        result = an.resolved_vs_unresolved()
        assert result["total"] == 10
        assert result["resolved"] == 4
        assert result["pending"] == 4
        assert result["in_progress"] == 2
        assert result["resolution_rate"] == 40.0

    def test_resolved_vs_unresolved_empty_safe(self):
        """Simulate empty collection behavior."""
        db = get_database()
        db.drop_collection("test_complaints_analytics_empty")
        orig = cfg.COMPLAINTS_COLLECTION
        cfg.COMPLAINTS_COLLECTION = "test_complaints_analytics_empty"
        try:
            result = an.resolved_vs_unresolved()
            assert result["total"] == 0
            assert result["resolution_rate"] == 0.0
        finally:
            cfg.COMPLAINTS_COLLECTION = orig
            db.drop_collection("test_complaints_analytics_empty")

    def test_top_five_categories_limit(self):
        result = an.top_five_categories()
        assert len(result) <= 5

    def test_top_five_categories_sorted_desc(self):
        result = an.top_five_categories()
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_student_complaint_history_returns_list(self):
        result = an.student_complaint_history("STU001")
        assert isinstance(result, list)
        assert len(result) == 10

    def test_student_complaint_history_unknown_student(self):
        result = an.student_complaint_history("STU_UNKNOWN")
        assert result == []

    def test_monthly_trend_returns_list(self):
        result = an.complaint_trends_monthly(months=6)
        assert isinstance(result, list)

    def test_dashboard_summary_has_all_keys(self):
        result = an.get_dashboard_summary()
        required = ["total", "resolved", "pending", "in_progress",
                    "resolution_rate", "avg_resolution_hours"]
        for key in required:
            assert key in result, f"Key '{key}' missing from dashboard summary"

    def test_avg_resolution_hours_is_float_or_none(self):
        result = an.get_dashboard_summary()
        val = result.get("avg_resolution_hours")
        assert val is None or isinstance(val, float)
