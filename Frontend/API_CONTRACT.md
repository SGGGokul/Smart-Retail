# RetailIQ — FastAPI Backend Integration Contract

This document defines the REST API contract between the Next.js frontend (`RetailIQ`) and the Python/FastAPI backend service.

## Base Configuration

- **Default Base URL:** `http://localhost:8000`
- **Environment Variable:** `NEXT_PUBLIC_API_BASE_URL` in `.env.local`
- **Specification Version:** 1.0.0
- **Standard Protocol:** HTTP/1.1 or HTTP/2, JSON (`application/json`) payloads (except multipart form data for file uploads).

---

## Error Handling Convention

When an API error occurs, the backend must return an appropriate HTTP status code (4xx or 5xx) with a standard JSON error envelope:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested video job was not found.",
    "details": { "jobId": "vj-999" }
  }
}
```

### Standard Status Codes

- `200 OK`: Request succeeded.
- `201 Created`: Resource created.
- `204 No Content`: Successful request with no body.
- `400 Bad Request`: Validation failure or malformed payload.
- `404 Not Found`: Target resource not found.
- `408 Request Timeout`: Request processing exceeded server deadline.
- `422 Unprocessable Entity`: FastAPI Pydantic schema validation error.
- `500 Internal Server Error`: Unhandled server exception.

---

## Endpoints

### 1. Health Check

#### `GET /health`
Verifies backend service liveness and database/model dependency health.

- **Query Parameters:** None
- **Request Body:** None
- **Response `200 OK`:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptimeSeconds": 14250,
  "timestamp": "2026-10-18T10:30:00Z"
}
```

---

### 2. Analytics

#### `GET /api/v1/analytics/summary`
Returns aggregate KPI metrics for the store overview dashboard.

- **Query Parameters:** None
- **Request Body:** None
- **Response `200 OK`:**
```json
{
  "todayCustomers": 1248,
  "todayCustomersDelta": "+6% vs yesterday",
  "avgDwellMinutes": 22,
  "avgDwellDelta": "-2 min vs yesterday",
  "longestQueueCheckout": "Checkout 3",
  "longestQueueCount": 4,
  "shelvesNeedingRestock": 3,
  "criticalShelvesCount": 1,
  "lowStockShelvesCount": 2
}
```

#### `GET /api/v1/analytics/traffic`
Retrieves daily and hourly customer traffic counts.

- **Query Parameters:**
  - `range` (optional, string): `today` | `7d` | `30d` (default: `7d`)
- **Request Body:** None
- **Response `200 OK`:**
```json
{
  "daily": [
    { "day": "Mon", "customers": 942 },
    { "day": "Tue", "customers": 1010 },
    { "day": "Wed", "customers": 1158 },
    { "day": "Thu", "customers": 1084 },
    { "day": "Fri", "customers": 1372 },
    { "day": "Sat", "customers": 1490 },
    { "day": "Sun", "customers": 1248 }
  ],
  "hourly": [
    { "hour": "08", "customers": 92 },
    { "hour": "12", "customers": 210 },
    { "hour": "17", "customers": 226 }
  ],
  "totalCustomers": 8304
}
```

#### `GET /api/v1/analytics/dwell-time`
Retrieves customer dwell time per store department/section.

- **Query Parameters:** None
- **Request Body:** None
- **Response `200 OK`:**
```json
{
  "bySection": [
    { "section": "Produce", "minutes": 6 },
    { "section": "Bakery", "minutes": 4 },
    { "section": "Dairy", "minutes": 3 },
    { "section": "Beverages", "minutes": 5 },
    { "section": "Checkout", "minutes": 7 }
  ],
  "averageDwellMinutes": 22
}
```

#### `GET /api/v1/analytics/queues`
Retrieves active queue metrics across all store checkouts.

- **Query Parameters:** None
- **Request Body:** None
- **Response `200 OK`:**
```json
{
  "queues": [
    { "checkoutId": "co-1", "currentQueue": 2, "avgWaitMinutes": 2.5, "peakQueue": 4 },
    { "checkoutId": "co-2", "currentQueue": 3, "avgWaitMinutes": 4.2, "peakQueue": 5 },
    { "checkoutId": "co-3", "currentQueue": 4, "avgWaitMinutes": 6.8, "peakQueue": 7 }
  ],
  "updatedAt": "2026-10-18T10:30:00Z"
}
```

---

### 3. Shelf Monitoring

#### `GET /api/v1/shelves`
Lists all monitored retail shelf zones and their stock levels.

- **Query Parameters:**
  - `status` (optional, string): `all` | `low` | `critical`
- **Request Body:** None
- **Response `200 OK`:**
```json
{
  "shelves": [
    {
      "id": "sh-A4",
      "name": "Beverages",
      "aisle": "Aisle 4",
      "fillPct": 38,
      "status": "critical",
      "lastChecked": "14:05"
    },
    {
      "id": "sh-A2",
      "name": "Dairy",
      "aisle": "Aisle 2",
      "fillPct": 58,
      "status": "low",
      "lastChecked": "12:58"
    }
  ],
  "totalCount": 6,
  "criticalCount": 2,
  "lowStockCount": 2
}
```

---

### 4. Alerts

#### `GET /api/v1/alerts`
Lists system and vision alerts with optional filtering.

- **Query Parameters:**
  - `severity` (optional, string): `info` | `warning` | `critical`
  - `acknowledged` (optional, boolean): `true` | `false`
- **Request Body:** None
- **Response `200 OK`:**
```json
{
  "alerts": [
    {
      "id": "al-01",
      "type": "Shelf low stock",
      "time": "14:05",
      "area": "Aisle 4",
      "severity": "critical",
      "description": "Beverages shelf fill dropped below 40%.",
      "acknowledged": false
    }
  ],
  "totalCount": 8,
  "unacknowledgedCount": 4
}
```

#### `PATCH /api/v1/alerts/{id}`
Updates an alert's status (e.g., marks it as acknowledged).

- **Path Parameters:**
  - `id` (string, required): Alert identifier (e.g., `al-01`)
- **Request Body (`application/json`):**
```json
{
  "acknowledged": true,
  "notes": "Restocking team notified via radio"
}
```
- **Response `200 OK`:**
```json
{
  "id": "al-01",
  "type": "Shelf low stock",
  "time": "14:05",
  "area": "Aisle 4",
  "severity": "critical",
  "description": "Beverages shelf fill dropped below 40%.",
  "acknowledged": true
}
```

---

### 5. Video Processing & Computer Vision

#### `POST /api/v1/videos`
Uploads a CCTV or store video file for asynchronous detection and tracking.

- **Request Body (`multipart/form-data`):**
  - `file`: Binary video file (`.mp4`, `.webm`, `.mov`, `.avi`)
- **Response `201 Created` or `200 OK`:**
```json
{
  "jobId": "vj-101",
  "filename": "store_evening_cam1.mp4",
  "status": "queued",
  "message": "Video queued for CV inference."
}
```

#### `GET /api/v1/videos/{id}`
Checks the processing status of a video job.

- **Path Parameters:**
  - `id` (string, required): Video job identifier
- **Response `200 OK`:**
```json
{
  "id": "vj-101",
  "file": "store_evening_cam1.mp4",
  "uploaded": "Today 15:30",
  "status": "processing",
  "frames": 2400,
  "customersDetected": 184,
  "durationSeconds": 180,
  "fps": 30
}
```

#### `GET /api/v1/videos/{id}/results`
Fetches detailed detection bounding boxes, customer counts, and metrics for a completed video job.

- **Path Parameters:**
  - `id` (string, required): Video job identifier
- **Response `200 OK`:**
```json
{
  "jobId": "vj-101",
  "status": "done",
  "totalFrames": 5400,
  "customersDetected": 342,
  "peakCount": 24,
  "averageDwellSeconds": 132,
  "detections": [
    {
      "id": "det-1",
      "label": "person",
      "confidence": 0.94,
      "box": { "x": 120, "y": 80, "width": 64, "height": 140 }
    }
  ]
}
```

---

### 6. AI Assistant

#### `POST /api/v1/assistant/chat`
Sends user retail queries to the GenAI / LLM assistant service.

- **Request Body (`application/json`):**
```json
{
  "message": "Which aisles had the highest congestion between 12pm and 2pm?",
  "conversationId": "conv-4819"
}
```
- **Response `200 OK`:**
```json
{
  "answer": "Aisle 4 (Beverages) and Checkout 3 experienced highest congestion between 12:00 and 14:00, with average wait times reaching 6.8 minutes.",
  "conversationId": "conv-4819",
  "suggestedFollowUps": [
    "Show shelf stock levels in Aisle 4",
    "Compare queue lengths across all checkouts"
  ]
}
```

---

## Frontend Integration Mode

The frontend client in `lib/api.ts` implements these exact contracts with:
- Configurable timeout handling (`DEFAULT_TIMEOUT_MS = 8000ms`).
- Typed errors (`ApiClientError`).
- Graceful fallback: If the backend is unreachable or returns non-2xx status, the UI clearly displays demo data or an offline banner, without falsely claiming data originated from live backend services.
