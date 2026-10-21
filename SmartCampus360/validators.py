"""
validators.py - Python-layer validation for SmartCampus 360.

MongoDB enforces structural and type constraints via $jsonSchema.
This module enforces additional business rules before sending data to the DB,
providing user-friendly error messages.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import config


class ValidationError(Exception):
    """Raised when user-provided data fails business-rule validation."""


def validate_complaint(data: dict[str, Any], is_update: bool = False) -> None:
    """
    Validate complaint data.
    Raises ValidationError with a descriptive message on failure.
    For updates (is_update=True), only validate fields that are present.
    """
    # ── category ──────────────────────────────────────────────────────────────
    if "category" in data:
        if data["category"] not in config.CATEGORIES:
            raise ValidationError(
                f"Invalid category '{data['category']}'. "
                f"Allowed: {', '.join(config.CATEGORIES)}"
            )

    # ── priority ──────────────────────────────────────────────────────────────
    if "priority" in data:
        if data["priority"] not in config.PRIORITIES:
            raise ValidationError(
                f"Invalid priority '{data['priority']}'. "
                f"Allowed: {', '.join(config.PRIORITIES)}"
            )

    # ── status ────────────────────────────────────────────────────────────────
    if "status" in data:
        if data["status"] not in config.STATUSES:
            raise ValidationError(
                f"Invalid status '{data['status']}'. "
                f"Allowed: {', '.join(config.STATUSES)}"
            )

    # ── description ───────────────────────────────────────────────────────────
    if "description" in data:
        desc = data["description"].strip()
        if len(desc) < config.MIN_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Description must be at least {config.MIN_DESCRIPTION_LENGTH} characters."
            )
        if len(desc) > config.MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Description must not exceed {config.MAX_DESCRIPTION_LENGTH} characters."
            )

    # ── required fields for new complaints ────────────────────────────────────
    if not is_update:
        required = [
            "complaint_id",
            "student_id",
            "category",
            "description",
            "location",
            "priority",
            "department",
        ]
        for field in required:
            if not data.get(field, "").strip():
                raise ValidationError(f"Field '{field}' is required and cannot be empty.")

    # ── complaint_id format ───────────────────────────────────────────────────
    if "complaint_id" in data and not is_update:
        cid = data["complaint_id"].strip()
        if not re.match(r"^CMP\d+$", cid):
            raise ValidationError(
                f"complaint_id must match pattern CMP<number>, got '{cid}'."
            )

    # ── timestamps ────────────────────────────────────────────────────────────
    for ts_field in ("created_at", "updated_at", "resolved_at"):
        if ts_field in data and data[ts_field] is not None:
            if not isinstance(data[ts_field], datetime):
                raise ValidationError(
                    f"'{ts_field}' must be a Python datetime object (BSON Date)."
                )

    # ── resolution consistency ────────────────────────────────────────────────
    if "status" in data and "resolved_at" in data:
        if data["status"] == "Resolved" and data["resolved_at"] is None:
            raise ValidationError(
                "resolved_at must be set when status is 'Resolved'."
            )
        if data["status"] != "Resolved" and data.get("resolved_at") is not None:
            raise ValidationError(
                "resolved_at should be null when status is not 'Resolved'."
            )


def validate_student(data: dict[str, Any], is_update: bool = False) -> None:
    """
    Validate student data.
    Raises ValidationError with a descriptive message on failure.
    """
    if not is_update:
        required = ["student_id", "name", "email", "building"]
        for field in required:
            if not data.get(field, "").strip():
                raise ValidationError(f"Field '{field}' is required.")

    # ── student_id format ─────────────────────────────────────────────────────
    if "student_id" in data and not is_update:
        sid = data["student_id"].strip()
        if not re.match(r"^STU\d+$", sid):
            raise ValidationError(
                f"student_id must match pattern STU<number>, got '{sid}'."
            )

    # ── email format ──────────────────────────────────────────────────────────
    if "email" in data:
        email = data["email"].strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValidationError(f"'{email}' is not a valid email address.")

    # ── name length ───────────────────────────────────────────────────────────
    if "name" in data:
        name = data["name"].strip()
        if len(name) < 2:
            raise ValidationError("Name must be at least 2 characters.")
        if len(name) > 100:
            raise ValidationError("Name must not exceed 100 characters.")


def sanitize_string(value: Any) -> str:
    """Strip and return a string, converting None to empty string."""
    if value is None:
        return ""
    return str(value).strip()
