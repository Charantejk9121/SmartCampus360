"""
scripts/initialize_database.py
Run this script once (or repeatedly — it is idempotent) to:
  1. Create MongoDB collections with $jsonSchema validators.
  2. Create all required indexes.

Usage:
    python scripts/initialize_database.py
    python scripts/initialize_database.py --force-validators
"""

import sys
import os
import argparse
import logging

# Ensure the parent directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import ping, get_database
from models import initialize_database
import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Initialize SmartCampus 360 database.")
    parser.add_argument(
        "--force-validators",
        action="store_true",
        help="Update $jsonSchema validators on existing collections.",
    )
    args = parser.parse_args()

    logger.info("Checking MongoDB connection…")
    status = ping()
    if not status["connected"]:
        logger.error("Cannot connect to MongoDB: %s", status["error"])
        logger.error("Ensure MongoDB is running or set MONGODB_URI in your .env file.")
        sys.exit(1)

    logger.info("Connected to database: %s", config.MONGODB_DATABASE)
    logger.info("Initializing schema%s…",
                " (force validator update)" if args.force_validators else "")

    result = initialize_database(force_validator_update=args.force_validators)

    for collection, outcome in result.items():
        logger.info("  %-30s → %s", collection, outcome)

    logger.info("Database initialization complete.")


if __name__ == "__main__":
    main()
