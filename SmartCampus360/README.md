# SmartCampus 360
## Intelligent Campus Complaint & Facility Analytics System

**Course:** CSE494 — Intelligent NoSQL Databases

---

## Overview

SmartCampus 360 is a full-stack web application for managing and analysing campus facility complaints. It demonstrates MongoDB document modelling, schema validation, CRUD operations, aggregation pipelines, and Python-MongoDB integration using PyMongo — all backed by a live MongoDB database and presented through a premium Streamlit web interface.

### Key Features
- 📋 **Complaint Management** — Submit, browse, filter, update, and resolve campus complaints
- 📊 **Live Analytics** — 10 MongoDB aggregation pipelines visualised with Plotly
- 🎓 **Student Directory** — Manage student records linked to complaints
- 🔍 **Database Explorer** — Inspect collections, schemas, indexes, and run live queries
- ⚙️ **Settings** — Schema initialisation and safe sample-data loading

---

## Architecture

```
Browser ──→ Streamlit (app.py)
               │
               ├── operations.py   (CRUD via PyMongo)
               ├── analytics.py    (Aggregation pipelines)
               ├── validators.py   (Python-layer validation)
               ├── models.py       ($jsonSchema + indexes)
               └── database.py     (PyMongo client)
                        │
                    MongoDB
               ┌────────────────┐
               │  complaints    │
               │  students      │
               └────────────────┘
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| MongoDB | 4.4 or higher (local) or Atlas |
| pip | latest |

---

## Setup (Windows PowerShell)

### 1. Navigate to the project folder

```powershell
cd "C:\Users\chara\Documents\mongo db pro\SmartCampus360"
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> If you see an execution policy error, run:  
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

---

## MongoDB Setup

### Option A: Local MongoDB

1. Download and install MongoDB Community Edition from https://www.mongodb.com/try/download/community
2. Start the MongoDB service:
   ```powershell
   mongod --dbpath "C:\data\db"
   ```
   Or ensure the MongoDB service is running in Windows Services.

3. The application connects to `mongodb://localhost:27017/` by default — no additional configuration needed.

### Option B: MongoDB Atlas (Cloud)

1. Create a free cluster at https://cloud.mongodb.com
2. Create a database user and whitelist your IP address.
3. Copy the connection string (SRV format).
4. Create a `.env` file in the project folder:
   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```
5. Set your Atlas URI:
   ```
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
   MONGODB_DATABASE=campus_complaints
   ```

---

## Environment Configuration

Copy the example file and edit:

```powershell
Copy-Item .env.example .env
notepad .env
```

The `.env` file is git-ignored and must **never** be committed.

---

## Database Initialization

Run once to create collections with validators and indexes:

```powershell
python scripts\initialize_database.py
```

To also update validators on existing collections:

```powershell
python scripts\initialize_database.py --force-validators
```

This is **idempotent** — safe to run multiple times.

---

## Sample Data

### Via the web interface (recommended)
1. Start the app (see below)
2. Go to **Settings → Sample Data**
3. Click **"Load Sample Data"**

### Via command line
```powershell
python -c "from sample_data import insert_sample_data; print(insert_sample_data())"
```

Sample data is **synthetic and fictitious** — it is safe to load in any environment.  
Existing records are **never overwritten** — duplicates are silently skipped.

---

## Running the Application

```powershell
streamlit run app.py
```

The application opens at `http://localhost:8501` in your default browser.

---

## Running Tests

### Unit tests (no MongoDB required)

```powershell
python -m pytest tests\test_validation.py -v
```

### Integration tests (MongoDB required)

```powershell
python -m pytest tests\test_crud.py -v
python -m pytest tests\test_analytics.py -v
```

### All tests

```powershell
python -m pytest tests\ -v
```

### Smoke test script

```powershell
python scripts\run_database_tests.py
```

> Integration tests use an isolated database (`test_campus_complaints_pytest`).  
> They **never** modify your production database.

---

## Project Structure

```
SmartCampus360/
├── app.py                  ← Streamlit application (main entry point)
├── config.py               ← Configuration (env vars, enumerations)
├── database.py             ← PyMongo client singleton
├── models.py               ← $jsonSchema validators + index creation
├── validators.py           ← Python-layer business rule validation
├── operations.py           ← CRUD operations (insert, find, update, delete)
├── analytics.py            ← MongoDB aggregation pipelines (10 pipelines)
├── sample_data.py          ← Synthetic dataset generator (idempotent)
├── requirements.txt        ← Python dependencies
├── .env.example            ← Environment variable template
├── .gitignore              ← Git exclusions
├── scripts/
│   ├── initialize_database.py   ← CLI schema initializer
│   └── run_database_tests.py    ← Live smoke-test script
├── tests/
│   ├── test_validation.py  ← Unit tests (no DB required)
│   ├── test_crud.py        ← CRUD integration tests
│   └── test_analytics.py   ← Aggregation integration tests
└── docs/
    ├── project_report.md   ← Full academic project report
    └── viva_questions.md   ← 30 viva Q&A
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ServerSelectionTimeoutError` | Ensure MongoDB is running: `mongod --dbpath C:\data\db` |
| `ModuleNotFoundError: pymongo` | Activate virtualenv: `.venv\Scripts\Activate.ps1` then `pip install -r requirements.txt` |
| `Set-ExecutionPolicy` error | Run: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| "Database not connected" in UI | Check `.env` file or start local `mongod` |
| Plotly charts not rendering | Upgrade: `pip install --upgrade plotly streamlit` |
| `DuplicateKeyError` on sample data | Normal — existing records are skipped automatically |

---

## Screenshots for Academic Submission

Capture the following screens after loading sample data:

1. Overview dashboard — KPI cards + all 4 charts
2. Complaints list with category filter applied
3. Create Complaint form (filled in)
4. Complaint detail panel (edit/resolve expanded)
5. Analytics → Category tab
6. Analytics → Trends tab
7. Analytics → Resolution Time tab
8. Analytics → Department Workload tab
9. Students directory
10. Database Explorer → Collections + schema validator
11. Database Explorer → Run pipeline
12. Settings → Connection status + sample data result

---

## Academic Notes

- All database operations use **PyMongo** — there is no SQLite, Firebase, or fake data layer.
- All dashboard metrics are computed from **live MongoDB aggregation pipeline results**.
- Schema validation uses **MongoDB $jsonSchema** with `validationAction: "error"`.
- Timestamps are stored as **BSON Date** objects (Python `datetime` with UTC timezone).
- Sample data loading is **idempotent** — safe to run multiple times without data loss.
