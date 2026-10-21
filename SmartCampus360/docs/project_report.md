# SmartCampus 360 — Project Report
## CSE494: Intelligent NoSQL Databases

---

## 1. Title Page

| Field | Value |
|---|---|
| **Project Title** | SmartCampus 360 — Intelligent Campus Complaint & Facility Analytics System |
| **Course** | CSE494: Intelligent NoSQL Databases |
| **Technology** | Python · Streamlit · MongoDB · PyMongo |
| **Database** | campus_complaints (MongoDB) |
| **Version** | 1.0.0 |

---

## 2. Abstract

SmartCampus 360 is a full-stack web application built for managing, tracking, and analysing campus facility complaints. It demonstrates key concepts of intelligent NoSQL databases: document modelling with BSON, MongoDB JSON Schema validation, CRUD operations via PyMongo, and complex aggregation pipelines for real-time analytics. The application provides an executive dashboard, complaint lifecycle management, student directory, interactive analytics, a database explorer, and academic documentation — all backed by a live MongoDB database.

---

## 3. Problem Statement

University campuses generate hundreds of maintenance and facility complaints each month across departments — WiFi outages, power failures, water supply issues, security concerns, and more. Traditional spreadsheet or email-based tracking is inefficient: complaints are lost, priorities are unclear, and resolution metrics are unavailable. Campus administrators need a centralised system that captures structured complaint data, enforces data quality, enables rapid status updates, and provides actionable analytics on department workloads and resolution performance.

---

## 4. Objectives

1. Model campus complaint and student data as MongoDB documents.
2. Enforce data integrity via $jsonSchema validators and unique indexes.
3. Implement full CRUD operations for complaints and students using PyMongo.
4. Build at least 8 meaningful aggregation pipelines for analytics.
5. Provide an interactive Streamlit web interface with premium visual design.
6. Demonstrate MongoDB concepts suitable for academic examination.

---

## 5. Real-World Relevance

- **Document Databases fit unstructured complaints**: Complaints have varying optional fields (resolution notes, additional details) that fit BSON's flexible schema better than rigid SQL tables.
- **Aggregation pipelines replace complex SQL joins**: Grouping by category, calculating average resolution time, and generating trend charts are all handled natively in MongoDB without application-layer aggregation.
- **Horizontal scalability**: As complaint volume grows (multiple campuses, years of history), MongoDB's sharding allows linear scale-out without schema migrations.
- **Real-time analytics**: Aggregation pipeline results reflect live data without ETL or data warehouse overhead.

---

## 6. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (User)                        │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP
┌─────────────────────────▼───────────────────────────────┐
│             Streamlit Application (app.py)               │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐  │
│  │Overview  │ │Complaints │ │Analytics │ │Students  │  │
│  └──────────┘ └───────────┘ └──────────┘ └──────────┘  │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Business Logic Layer                      │   │
│  │  operations.py  analytics.py  validators.py       │   │
│  └──────────────────────┬───────────────────────────┘   │
│                          │ PyMongo                        │
└──────────────────────────┼──────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                  MongoDB                                  │
│  ┌───────────────┐   ┌───────────────┐                   │
│  │  complaints   │   │   students    │                   │
│  │  collection   │   │  collection   │                   │
│  └───────────────┘   └───────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | Application logic |
| Web Framework | Streamlit 1.39 | UI rendering and state |
| Database | MongoDB | Primary data store |
| DB Driver | PyMongo 4.9 | Python–MongoDB interface |
| Data Analysis | Pandas 2.2 | DataFrame transformations |
| Visualizations | Plotly 5.24 | Interactive charts |
| Config | python-dotenv | Environment variable loading |
| Schema Validation | MongoDB $jsonSchema | Document structure enforcement |

---

## 8. MongoDB Database & Collection Design

### Database: `campus_complaints`

#### Collection: `complaints`

| Field | BSON Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | Auto | MongoDB default |
| `complaint_id` | string | ✅ | Unique, format CMP\d+ |
| `student_id` | string | ✅ | References students collection |
| `category` | string | ✅ | Enum: WiFi, Electricity, etc. |
| `description` | string | ✅ | Min 10 chars |
| `location` | string | ✅ | Building/room |
| `priority` | string | ✅ | Enum: Low, Medium, High |
| `status` | string | ✅ | Enum: Pending, In Progress, Resolved |
| `department` | string | ✅ | Responsible department |
| `created_at` | date | ✅ | BSON UTC Date |
| `updated_at` | date | ✅ | BSON UTC Date |
| `resolved_at` | date\|null | ❌ | Set when status = Resolved |
| `resolution_notes` | string\|null | ❌ | Optional resolution text |
| `additional_details` | string\|null | ❌ | Optional extra context |

#### Collection: `students`

| Field | BSON Type | Required |
|---|---|---|
| `_id` | ObjectId | Auto |
| `student_id` | string | ✅ |
| `name` | string | ✅ |
| `email` | string | ✅ |
| `building` | string | ✅ |
| `created_at` | date | ✅ |

---

## 9. Sample Documents

### Complaint Document
```json
{
  "_id": {"$oid": "..."},
  "complaint_id": "CMP1001",
  "student_id": "STU101",
  "category": "WiFi",
  "description": "WiFi connectivity is completely down in the entire floor. Students cannot attend online classes.",
  "location": "Block A",
  "priority": "High",
  "status": "Resolved",
  "department": "IT Support",
  "created_at": {"$date": "2024-09-15T08:30:00Z"},
  "updated_at": {"$date": "2024-09-17T14:22:00Z"},
  "resolved_at": {"$date": "2024-09-17T14:22:00Z"},
  "resolution_notes": "Router replaced and connectivity restored.",
  "additional_details": null
}
```

### Student Document
```json
{
  "_id": {"$oid": "..."},
  "student_id": "STU101",
  "name": "Arjun Mehta",
  "email": "arjun.mehta@campus.edu",
  "building": "Block A",
  "created_at": {"$date": "2024-06-01T00:00:00Z"}
}
```

---

## 10. Schema Validation Implementation

Schema validation is applied using MongoDB's `$jsonSchema` validator during `db.create_collection()` and can be updated with `collMod`:

```python
# models.py
COMPLAINT_JSON_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["complaint_id", "student_id", "category", ...],
        "properties": {
            "category": {
                "bsonType": "string",
                "enum": ["WiFi", "Electricity", "Water", ...]
            },
            "created_at": {"bsonType": "date"},
            "resolved_at": {"bsonType": ["date", "null"]},
            ...
        }
    }
}

db.create_collection(
    "complaints",
    validator=COMPLAINT_JSON_SCHEMA,
    validationLevel="moderate",   # Existing docs not re-validated on reads
    validationAction="error"      # Reject invalid inserts/updates
)
```

**MongoDB enforces:**
- Required field presence
- BSON type correctness (`date`, `string`, `null`)
- Enum membership (category, priority, status)
- String length (minLength on description)

**Python layer enforces additionally:**
- Complaint ID format (regex `CMP\d+`)
- Email format (regex)
- Business rules (resolved_at ↔ status consistency)
- Friendly error messages before reaching MongoDB

---

## 11. Indexing Strategy

```python
# Unique indexes (enforce uniqueness at DB level)
complaints.create_index([("complaint_id", ASCENDING)], unique=True)
students.create_index([("student_id", ASCENDING)], unique=True)

# Query acceleration indexes
complaints.create_index([("status", ASCENDING)])
complaints.create_index([("category", ASCENDING)])
complaints.create_index([("priority", ASCENDING)])
complaints.create_index([("student_id", ASCENDING)])
complaints.create_index([("created_at", DESCENDING)])

# Compound index for common filter combination
complaints.create_index([("status", ASCENDING), ("priority", ASCENDING)])

# Students
students.create_index([("email", ASCENDING)])
```

**Trade-offs:** Indexes consume additional disk space and slow down write operations slightly. They dramatically improve read performance for filtered queries and aggregation `$match` stages. For a complaint system where reads far outnumber writes, this trade-off is highly favourable.

---

## 12. CRUD Implementation

### Create (insert_one)
```python
col.insert_one({
    "complaint_id": "CMP1001",
    "status": "Pending",
    "created_at": datetime.now(timezone.utc),
    ...
})
```

### Read (find, find_one)
```python
col.find({"status": "Pending"}).sort("created_at", -1).limit(20)
col.find_one({"complaint_id": "CMP1001"})
```

### Update (update_one)
```python
col.update_one(
    {"complaint_id": "CMP1001"},
    {"$set": {"status": "Resolved", "resolved_at": datetime.now(timezone.utc)}}
)
```

### Delete (delete_one)
```python
col.delete_one({"complaint_id": "CMP1001"})
```

### Bulk Insert (insert_many)
```python
col.insert_many(sample_docs, ordered=False)
```

---

## 13. Aggregation Pipelines

### Pipeline 1: Complaints by Category
```python
[
    {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$project": {"_id": 0, "category": "$_id", "count": 1}}
]
```
**Output:** `[{"category": "WiFi", "count": 18}, ...]`

### Pipeline 5: Average Resolution Time
```python
[
    {"$match": {"status": "Resolved", "resolved_at": {"$ne": None}}},
    {"$project": {
        "category": 1,
        "resolution_ms": {"$subtract": ["$resolved_at", "$created_at"]}
    }},
    {"$match": {"resolution_ms": {"$gt": 0}}},
    {"$group": {
        "_id": "$category",
        "avg_hours": {"$avg": {"$divide": ["$resolution_ms", 3600000]}}
    }},
    {"$project": {"_id": 0, "category": "$_id",
                  "avg_hours": {"$round": ["$avg_hours", 2]}}}
]
```

### Pipeline 8: Student Complaint History with $lookup
```python
[
    {"$match": {"student_id": "STU101"}},
    {"$lookup": {
        "from": "students",
        "localField": "student_id",
        "foreignField": "student_id",
        "as": "student_info"
    }},
    {"$project": {
        "complaint_id": 1, "category": 1, "status": 1,
        "student_name": {"$arrayElemAt": ["$student_info.name", 0]}
    }}
]
```

---

## 14. PyMongo Connection & Implementation

```python
from pymongo import MongoClient

client = MongoClient(
    "mongodb://localhost:27017/",
    serverSelectionTimeoutMS=5000,
    appname="SmartCampus360"
)
client.admin.command("ping")   # Verify connectivity
db = client["campus_complaints"]
complaints = db["complaints"]
```

All operations use `datetime.now(timezone.utc)` for timezone-aware BSON Dates, avoiding naive datetime issues with MongoDB Atlas.

---

## 15. Application Screenshots Checklist

Take screenshots of the following for academic submission:
- [ ] Overview dashboard with KPI cards and all charts populated
- [ ] Complaints list with filters applied
- [ ] Create Complaint form
- [ ] Complaint detail / edit panel
- [ ] Analytics — Category tab with donut and bar chart
- [ ] Analytics — Trends tab with area chart
- [ ] Analytics — Resolution Time tab
- [ ] Analytics — Department Workload tab
- [ ] Students directory
- [ ] Database Explorer — collection stats and schema validator
- [ ] Database Explorer — run a pipeline
- [ ] Settings — connection status
- [ ] Settings — sample data initialization result

---

## 16. Testing & Results

### Unit Tests (no MongoDB required)
```
tests/test_validation.py
  TestComplaintValidation   — 15 tests
  TestStudentValidation     — 8 tests
  TestSanitizeString        — 3 tests
```

### Integration Tests (require MongoDB)
```
tests/test_crud.py
  TestStudentCRUD           — 8 tests
  TestComplaintCRUD         — 13 tests

tests/test_analytics.py
  TestAggregationPipelines  — 18 tests
```

### Smoke Test Script
```
scripts/run_database_tests.py — 25+ checks
```

> **Note:** Integration test results depend on a live MongoDB connection. Tests against an isolated database (`test_campus_complaints_pytest`) and clean up automatically. Production data is never accessed.

---

## 17. Limitations

1. No authentication — the application assumes a trusted internal network.
2. Single-database instance — no replica set or sharding configuration.
3. No real-time push updates — the dashboard refreshes on page reload or manual refresh.
4. Email notifications are not implemented.
5. File attachment support (photos of issues) is not implemented.
6. The `$lookup` in Pipeline 8 performs a full collection scan on students unless an index on `student_id` is present (index is created by the initializer).

---

## 18. Future Enhancements

1. Role-based access control (admin, department staff, student).
2. Email/SMS notifications when complaint status changes.
3. File upload support for attaching photos to complaints.
4. MongoDB Change Streams for real-time dashboard updates.
5. Geographic map view of campus complaints by building.
6. Machine learning–based priority prediction from description text.
7. REST API layer to support a mobile application.
8. Sharded cluster for multi-campus deployment.

---

## 19. Conclusion

SmartCampus 360 successfully demonstrates the practical use of MongoDB as an intelligent NoSQL database for a real-world campus management scenario. The system implements MongoDB document modelling, $jsonSchema validation, unique and compound indexes, full CRUD operations via PyMongo, and ten aggregation pipelines covering grouping, date-based trends, average calculations, $lookup joins, and statistical summaries. The Streamlit web interface presents all analytics in interactive Plotly charts, and the codebase is organised into clearly separated modules with comprehensive tests and documentation.
