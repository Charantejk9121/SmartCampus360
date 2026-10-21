# SmartCampus 360 — Viva Preparation
## CSE494: Intelligent NoSQL Databases — 30 Q&A

---

### Q1. Why did you choose MongoDB for this project instead of a relational database?

**Answer:**  
MongoDB fits this project for several reasons:
- **Flexible schema**: Complaint documents have optional fields (`resolved_at`, `resolution_notes`, `additional_details`) that are null for most records. BSON's native null type handles this without `NULL` column sprawl.
- **JSON-native storage**: Complaints map naturally to documents — no object-relational mismatch.
- **Built-in aggregation pipeline**: Grouping, filtering, date-truncation, and `$lookup` across collections are handled in the database without application-layer joins.
- **Horizontal scalability**: MongoDB can shard across nodes as complaint volume grows across campuses.
- **PyMongo integration**: The official Python driver provides a clean, Pythonic API.

---

### Q2. What is a BSON document?

**Answer:**  
BSON (Binary JSON) is MongoDB's binary-encoded serialisation format. It extends JSON with additional data types:
- `date` — 64-bit UTC milliseconds timestamp (used for `created_at`, `resolved_at`)
- `ObjectId` — 12-byte unique identifier auto-generated for `_id`
- `null` — native null value
- `int32`, `int64`, `double`, `decimal128` — typed numeric values
- `bool`, `array`, `embedded document`

BSON allows MongoDB to store and query typed data efficiently without string parsing.

---

### Q3. When would you embed data versus reference it?

**Answer:**  
**Embed** when:
- Data is accessed together most of the time
- The embedded data belongs to one parent (one-to-one or one-to-few)
- Example: Embedding tags or sub-issues inside a complaint document

**Reference** (use separate collection + `$lookup`) when:
- Data is shared across multiple documents
- Data grows large or independently updated
- Example: Students are referenced by `student_id` in complaints, not embedded, because a student exists independently and may file many complaints. `$lookup` joins the two collections in Pipeline 8.

---

### Q4. Explain MongoDB $jsonSchema validation.

**Answer:**  
`$jsonSchema` is applied to a collection as a validator. MongoDB checks every insert and update against it:

```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "required": ["complaint_id", "category"],
    "properties": {
      "category": {
        "bsonType": "string",
        "enum": ["WiFi", "Electricity", "Water"]
      },
      "created_at": { "bsonType": "date" }
    }
  }
}
```

- `validationLevel: "moderate"` — only validates new/modified documents (does not re-validate existing ones on reads).
- `validationAction: "error"` — rejects invalid documents with a `WriteError`.

---

### Q5. What are CRUD operations? Give PyMongo examples.

**Answer:**  
| Operation | PyMongo | Use in Project |
|---|---|---|
| **Create** | `col.insert_one(doc)` | Submit new complaint |
| **Read** | `col.find({})`, `col.find_one({...})` | Browse/search complaints |
| **Update** | `col.update_one(filter, {"$set": update})` | Change status, resolve |
| **Delete** | `col.delete_one({"complaint_id": "CMP1001"})` | Remove complaint |
| **Bulk Insert** | `col.insert_many(docs)` | Load sample data |
| **Count** | `col.count_documents({})` | KPI metrics |

---

### Q6. What is a unique index? How is it created?

**Answer:**  
A unique index guarantees that no two documents have the same value for the indexed field. MongoDB raises a `DuplicateKeyError` on violation.

```python
col.create_index([("complaint_id", ASCENDING)], unique=True, name="idx_complaint_id_unique")
```

In this project, unique indexes enforce `complaint_id` in complaints and `student_id` in students. If an application tries to insert `CMP1001` twice, MongoDB rejects the second insert with a `DuplicateKeyError` which PyMongo raises and the application catches and reports to the user.

---

### Q7. What is a compound index?

**Answer:**  
A compound index indexes multiple fields together:

```python
col.create_index([("status", ASCENDING), ("priority", ASCENDING)])
```

This accelerates queries that filter on both `status` and `priority` simultaneously, which is a common pattern in the High-Priority Unresolved pipeline (`$match` on `priority: "High"` and `status: {"$ne": "Resolved"}`).

**Trade-off:** Compound indexes are larger and slower to write but significantly faster for multi-field queries.

---

### Q8. Explain the aggregation pipeline.

**Answer:**  
An aggregation pipeline is an ordered sequence of **stages**. Each stage transforms the document stream:

```
Input Documents → [$match] → [$group] → [$sort] → [$project] → Output
```

Common stages:
- `$match` — filter (like SQL WHERE)
- `$group` — aggregate by field (like SQL GROUP BY)
- `$sort` — sort results
- `$project` — select/rename/compute fields
- `$lookup` — join from another collection
- `$limit` / `$skip` — pagination
- `$unwind` — flatten arrays

---

### Q9. What does $match do?

**Answer:**  
`$match` filters documents using the same query syntax as `find()`:

```python
{"$match": {"status": "Pending", "priority": "High"}}
```

It should be placed as early as possible in the pipeline to reduce the number of documents processed by subsequent stages, improving performance. MongoDB can use indexes during a `$match` stage.

---

### Q10. What does $group do?

**Answer:**  
`$group` combines multiple documents into a single output document per group key:

```python
{"$group": {
    "_id": "$category",            # Group key
    "count": {"$sum": 1},          # Count documents
    "avg_hours": {"$avg": "$resolution_ms"}
}}
```

Accumulators: `$sum`, `$avg`, `$min`, `$max`, `$push`, `$addToSet`.

---

### Q11. What does $project do?

**Answer:**  
`$project` reshapes documents — including or excluding fields and creating computed fields:

```python
{"$project": {
    "_id": 0,                           # Exclude _id
    "category": "$_id",                 # Rename _id to category
    "avg_hours": {"$round": ["$avg_hours", 2]}  # Round to 2 decimal places
}}
```

---

### Q12. What does $sort do?

**Answer:**  
`$sort` orders documents by one or more fields:

```python
{"$sort": {"count": -1}}   # Descending
{"$sort": {"created_at": 1}}  # Ascending
```

When placed after `$group`, it sorts the aggregated results. When placed before `$limit`, it determines which documents are kept.

---

### Q13. Explain $lookup.

**Answer:**  
`$lookup` performs a left outer join with another collection:

```python
{"$lookup": {
    "from": "students",           # Collection to join
    "localField": "student_id",   # Field in complaints
    "foreignField": "student_id", # Field in students
    "as": "student_info"          # Output array field
}}
```

Result: each complaint document gets a `student_info` array containing matching student documents. `$arrayElemAt` extracts the first element.

---

### Q14. What does $avg do?

**Answer:**  
`$avg` calculates the arithmetic mean of a field across a group:

```python
{"$group": {
    "_id": "$category",
    "avg_hours": {"$avg": {"$divide": ["$resolution_ms", 3600000]}}
}}
```

In Pipeline 5, `$avg` computes the average resolution time in hours by dividing the millisecond difference (`$subtract` of two dates) by 3,600,000.

---

### Q15. What does $sum do?

**Answer:**  
`$sum` adds numeric values across a group. With `1` it counts documents:

```python
{"$sum": 1}   # Count all documents in group
{"$sum": "$revenue"}   # Sum a numeric field
{"$sum": {"$cond": [{"$eq": ["$status", "Resolved"]}, 1, 0]}}  # Conditional count
```

In Pipeline 6 (department workload), conditional `$sum` counts resolved and unresolved complaints per department in a single `$group` stage.

---

### Q16. What is PyMongo?

**Answer:**  
PyMongo is the official synchronous Python driver for MongoDB. It provides:
- `MongoClient` — connection management
- `Database`, `Collection` — MongoDB object wrappers
- `insert_one()`, `find()`, `update_one()`, `delete_one()`, `aggregate()` — CRUD and aggregation
- `pymongo.errors` — typed exceptions (`DuplicateKeyError`, `WriteError`, `ConnectionFailure`)
- Automatic BSON serialisation/deserialisation of Python dicts and datetime objects

---

### Q17. What are BSON Dates? Why are they important?

**Answer:**  
BSON Date stores a 64-bit integer counting milliseconds since the Unix epoch (1970-01-01 UTC). In PyMongo, Python `datetime` objects are automatically serialised as BSON Dates.

**Why important:**
- Enables `$subtract` between two dates to get millisecond differences
- Enables `$dateToString` for grouping by day/month in trend pipelines
- Supports range queries (`$gte`, `$lte`) with proper chronological ordering
- Timezone-aware `datetime.now(timezone.utc)` avoids naive datetime issues with Atlas

**In this project:** All `created_at`, `updated_at`, `resolved_at` fields are stored as BSON Dates, never as strings.

---

### Q18. What are the trade-offs of indexes?

**Answer:**  
| Benefit | Cost |
|---|---|
| Faster reads (`find`, `$match`) | Slower writes (index update on every insert/update/delete) |
| Unique constraint enforcement | Additional disk/memory usage |
| Covered queries (no document fetch) | Complex index selection by query planner |

**Strategy in this project:**
- Unique indexes on `complaint_id` and `student_id` are mandatory for correctness.
- `status`, `category`, `priority` indexes accelerate the most common filters.
- Compound `(status, priority)` index supports the high-priority unresolved query.
- `created_at` descending index supports the default sort on the complaints list.

---

### Q19. How is data consistency maintained?

**Answer:**  
1. **$jsonSchema** enforces required fields and type correctness at the database level.
2. **Python validators** (`validators.py`) check business rules (status↔resolved_at consistency) before issuing any write.
3. **Unique indexes** prevent duplicate `complaint_id` and `student_id` values.
4. **`update_one` with `$set`** only modifies specified fields — other fields are untouched.
5. **Confirmation dialogs** in the UI prevent accidental destructive actions.
6. **Student deletion guard** — a student cannot be deleted if they have complaints.

---

### Q20. How does the application handle errors?

**Answer:**  
| Error Type | Handling |
|---|---|
| `ConnectionFailure` / `ServerSelectionTimeoutError` | `ping()` returns `{"connected": False}`. UI shows "MongoDB not reachable" and stops page rendering. |
| `DuplicateKeyError` | Caught in `create_complaint()`, user shown friendly message with suggested ID |
| `WriteError` | Logged, exception re-raised, UI displays error message |
| `ValidationError` (Python) | Raised before DB write, user shown descriptive message |
| `KeyError` | Raised from `update_*()` when document not found, UI shows error |
| Empty aggregation result | Every pipeline returns empty list; UI shows empty state |

Credentials and stack traces are never displayed to end users.

---

### Q21. What is validationLevel in MongoDB?

**Answer:**  
`validationLevel` controls which documents are validated:
- `"strict"` — validate ALL documents on insert and update (including previously existing documents)
- `"moderate"` — validate new inserts and updates to documents that already pass validation; pre-existing invalid documents are not blocked on updates

This project uses `"moderate"` to allow safe re-application of validators to an existing collection without blocking legacy data.

---

### Q22. What is validationAction?

**Answer:**  
`validationAction` controls what MongoDB does when validation fails:
- `"error"` — rejects the operation with a `WriteError` (used in this project)
- `"warn"` — allows the operation but logs a warning to the MongoDB log

This project uses `"error"` to enforce data quality strictly.

---

### Q23. How does $dateTrunc differ from $dateToString?

**Answer:**  
- `$dateTrunc` — available from MongoDB 5.0+. Truncates a date to a unit boundary (`day`, `month`, `week`). Returns a BSON Date.
- `$dateToString` — available in all versions. Converts a date to a formatted string. Can be used for grouping by day (`"%Y-%m-%d"`) or month (`"%Y-%m"`).

This project uses `$dateToString` in trend pipelines for maximum version compatibility (works with MongoDB 4.0+).

---

### Q24. What is the difference between find() and aggregate()?

**Answer:**  
| `find()` | `aggregate()` |
|---|---|
| Returns documents as-is | Can transform, group, join, compute |
| Supports projection and sort | Full pipeline of stages |
| Simpler, faster for simple retrieval | Essential for analytics |

In this project: `find()` is used for complaint/student retrieval and filtering; `aggregate()` is used for all dashboard metrics and chart data.

---

### Q25. How does $lookup handle missing matches?

**Answer:**  
`$lookup` performs a **left outer join**: if no matching document exists in the foreign collection, the `as` field is set to an empty array `[]`. In Pipeline 8:

```python
"student_name": {"$ifNull": [
    {"$arrayElemAt": ["$student_info.name", 0]},
    "Unknown"
]}
```

`$arrayElemAt` on an empty array returns `null`, and `$ifNull` substitutes `"Unknown"` — preventing null pointer errors in display.

---

### Q26. How is idempotent sample data loading implemented?

**Answer:**  
```python
existing = set(col.distinct("complaint_id"))
new_docs = [d for d in all_docs if d["complaint_id"] not in existing]
col.insert_many(new_docs, ordered=False)
```

`distinct("complaint_id")` retrieves all existing IDs in one query. Only documents with IDs not already in the database are inserted. `BulkWriteError` is caught and the `nInserted` count extracted. This ensures running the loader multiple times never duplicates data.

---

### Q27. How are timestamps managed consistently?

**Answer:**  
- `created_at` — set to `datetime.now(timezone.utc)` at document creation, never changed.
- `updated_at` — set to `datetime.now(timezone.utc)` on every `update_complaint()` call.
- `resolved_at` — set to `datetime.now(timezone.utc)` when status becomes `"Resolved"`. Reset to `null` if complaint is reopened (status changed from Resolved).

All use timezone-aware `datetime` objects (UTC). PyMongo serialises these as BSON Dates automatically.

---

### Q28. How does the application prevent re-seeding on every startup?

**Answer:**  
The app does NOT call `insert_sample_data()` on startup. Sample data loading is triggered only by an explicit button click in the Settings page. The `_ensure_db_initialized()` function (called on startup) only creates collections and indexes — it never inserts data. This ensures user data is never overwritten by an automatic process.

---

### Q29. What is $subtract used for in Pipeline 5?

**Answer:**  
When `$subtract` is applied to two BSON Date fields, MongoDB returns the difference in **milliseconds**:

```python
"resolution_ms": {"$subtract": ["$resolved_at", "$created_at"]}
```

This gives the resolution time in milliseconds. Dividing by 3,600,000 (milliseconds in an hour) converts it to hours:

```python
"avg_hours": {"$avg": {"$divide": ["$resolution_ms", 3600000]}}
```

A `$match: {"resolution_ms": {"$gt": 0}}` guard removes anomalous records where `resolved_at` ≤ `created_at`.

---

### Q30. What are the known limitations of this project?

**Answer:**  
1. **No authentication** — all users have full access. A production system would use role-based access control.
2. **Synchronous driver** — PyMongo is synchronous; under heavy concurrent load, an async driver (Motor) would be preferable.
3. **No replica set** — running on a standalone MongoDB node means no automatic failover.
4. **No Change Streams** — the dashboard refreshes only on page reload, not in real-time.
5. **Student deletion restriction** — students cannot be deleted if they have complaints. Handling this (e.g., anonymising the student) would require a more complex workflow.
6. **`$lookup` performance** — without an index on `students.student_id`, the lookup is a collection scan. The index is created by the initializer but must be verified on Atlas.
