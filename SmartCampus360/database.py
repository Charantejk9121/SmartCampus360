"""
database.py - MongoDB connection management for SmartCampus 360
Provides a singleton client and helper functions for collection access.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import (
    ConnectionFailure,
    ConfigurationError,
    ServerSelectionTimeoutError,
)

import config

logger = logging.getLogger(__name__)

# ─── Singleton client ──────────────────────────────────────────────────────────

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """
    Return a singleton MongoClient, creating it on first call.
    Raises ConnectionFailure when the server is not reachable.
    """
    global _client
    if _client is None:
        try:
            _client = MongoClient(
                config.MONGODB_URI,
                serverSelectionTimeoutMS=config.SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=config.CONNECT_TIMEOUT_MS,
                socketTimeoutMS=config.SOCKET_TIMEOUT_MS,
                appname=config.APP_NAME,
            )
            # Verify connection immediately
            _client.admin.command("ping")
            logger.info("MongoDB connection established → %s", config.MONGODB_URI)
        except (ConnectionFailure, ServerSelectionTimeoutError, ConfigurationError) as exc:
            _client = None
            logger.error("MongoDB connection failed: %s", exc)
            raise
    return _client


def get_database() -> Database:
    """Return the application database."""
    return get_client()[config.MONGODB_DATABASE]


def get_complaints_collection() -> Collection:
    """Return the complaints collection."""
    return get_database()[config.COMPLAINTS_COLLECTION]


def get_students_collection() -> Collection:
    """Return the students collection."""
    return get_database()[config.STUDENTS_COLLECTION]


def ping() -> dict:
    """
    Attempt a ping and return a status dict:
      {"connected": bool, "uri_hint": str, "database": str, "error": str|None}
    The URI hint is safe to display — it never includes passwords.
    """
    uri = config.MONGODB_URI
    # Produce a safe URI hint (replace password with ***)
    safe_hint = _safe_uri(uri)
    try:
        get_client().admin.command("ping")
        return {
            "connected": True,
            "uri_hint": safe_hint,
            "database": config.MONGODB_DATABASE,
            "error": None,
        }
    except Exception as exc:
        return {
            "connected": False,
            "uri_hint": safe_hint,
            "database": config.MONGODB_DATABASE,
            "error": str(exc),
        }


def close_client() -> None:
    """Close the singleton client and reset the reference."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed.")


# ─── Helper ───────────────────────────────────────────────────────────────────

def _safe_uri(uri: str) -> str:
    """Return the URI with the password replaced by *** for safe display."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(uri)
        if parsed.password:
            safe = parsed._replace(
                netloc=f"{parsed.username}:***@{parsed.hostname}"
                + (f":{parsed.port}" if parsed.port else "")
            )
            return urlunparse(safe)
        # Show only host portion, not the full URI
        host = parsed.hostname or "localhost"
        port = f":{parsed.port}" if parsed.port else ""
        return f"mongodb://{host}{port}/"
    except Exception:
        return "mongodb://***/"


def collection_stats(collection: Collection) -> dict:
    """Return basic stats for a collection (document count, indexes)."""
    try:
        return {
            "name": collection.name,
            "count": collection.count_documents({}),
            "indexes": list(collection.index_information().keys()),
        }
    except Exception as exc:
        return {"name": collection.name, "count": -1, "indexes": [], "error": str(exc)}
