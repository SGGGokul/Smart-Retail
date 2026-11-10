# RetailIQ – Complete Technical Documentation

> **Scope** – This document provides a thorough, source‑code‑driven description of the **Smart‑Retail** (RetailIQ) platform as it exists in the local monorepo `D:\Download\CISG\Backend`.  All claims are backed by concrete file references; anything not found in the code is marked **Not verified in the repository**.

---

## 1. Project Overview

RetailIQ is a **full‑stack smart‑retail video‑analytics platform** that enables store managers to gain actionable insights from CCTV video streams and static images, and to query store‑specific knowledge through an AI Copilot.

| Business Problem | Technical Solution |
|-------------------|--------------------|
| • Manual foot‑fall counting and inventory checks are labor‑intensive. | • Automated detection of people and objects using a YOLO‑11n model (Nano variant). |
| • No unified view of customer journeys across multiple cameras. | • Multi‑camera **Re‑ID** (lightweight HSV‑histogram based) merges detections into a daily visitor identity. |
| • Shelf stock levels must be manually inspected. | • Geometric **shelf‑monitoring** estimates occupancy and flags low‑stock zones. |
| • Store policies & SOPs are scattered in documents. | • **AI Copilot** with hybrid **RAG** (dense vector + BM25) retrieves relevant sections and generates answers via Groq LLM. |

The platform consists of a **FastAPI backend** (`app/`) and a **Next.js frontend** (`Frontend/`), orchestrated via Docker Compose.  All persistent data lives in PostgreSQL (with the `pgvector` extension for embeddings) and temporary job state lives in Redis.

---

## 2. Implemented Features (source‑verified)

| Feature | Status | Core implementation (file) | API endpoint(s) | DB tables (if any) | Notes |
|---------|--------|----------------------------|-----------------|--------------------|-------|
| **Image‑based object detection** | Implemented | `app/services/cv_service.py::detect_image` | `POST /api/v1/images/detect` (`app/api/images.py`) | `image_detection` (temporary, not persisted) | Returns COCO class list with bounding boxes & confidence. |
| **Video‑based object detection & analytics** | Implemented | `app/services/video_service.py::process_video_job` | `POST /api/v1/videos/upload` (`app/api/videos.py`) – creates job; `GET /api/v1/videos/status/{job_id}` | `video_job`, `video_frame`, `analytics_event` (see models) | Background worker extracts frames, runs YOLO, stores results. |
| **Customer counting & footfall analytics** | Implemented | `app/services/analytics_service.py::compute_footfall` | `GET /api/v1/analytics/footfall` (`app/api/analytics.py`) | `visit`, `event` | Uses entry/exit zone events from `zone_service`. |
| **Customer journey tracking** | Implemented | `app/services/visit_service.py` (track sessions) | `GET /api/v1/customer_journey/{visit_id}` (`app/api/customer_journey.py`) | `visit`, `event` | Handles multiple entrance‑exit cycles per daily visitor. |
| **Entry / exit detection** | Implemented | `app/services/zone_service.py::detect_zone_crossing` | `POST /api/v1/zone/events` (internal use) | `zone_event` | Zones are defined per camera in `data/external/multiview-retail-tracking`. |
| **Dwell‑time calculation** | Implemented | `app/services/analytics_service.py::calculate_dwell_time` | `GET /api/v1/analytics/dwell` (`app/api/analytics.py`) | `visit`, `event` | Based on timestamps of zone entry/exit. |
| **Shopping‑zone occupancy** | Implemented | `app/services/zone_service.py::is_inside_zone` | internal | `zone_state` (computed, not persisted) | Uses point‑in‑polygon checks. |
| **Daily unique visitor identities** | Implemented | `app/services/identity_service.py::assign_daily_visitor_id` | internal | `daily_visitor` (model `RetailIntelligence` table) | Resets at midnight (UTC). |
| **Multi‑camera Re‑ID** | Implemented (lightweight) | `app/services/identity_service.py::match_across_cameras` (HSV histogram) | internal | `visitor_match` (temporary) | **Not a deep‑learning Re‑ID model** – documented as HSV‑based heuristic. |
| **Shelf occupancy monitoring** | Implemented | `app/services/shelf_service.py::process_shelf_frame` | `GET /api/v1/shelves/status` (`app/api/shelves.py`) | `shelf_zone`, `shelf_event` | Polygons defined in `data/documents/shelf_layout.json`. |
| **Product interaction (pickup/return) detection** | Implemented | `app/services/shelf_service.py::detect_pickup_return` | internal | `shelf_interaction` | Uses a 5‑frame disappearance rule; not SKU‑level. |
| **Retail alerts & analytics** | Implemented | `app/services/alert_service.py` (not listed but imported by `app/api/alerts.py`) | `GET /api/v1/alerts` | `alert` | Simple threshold‑based alerts (e.g., low stock). |
| **AI Copilot** | Implemented | `app/services/assistant_service.py::handle_query` | `POST /api/v1/assistant/chat` (`app/api/assistant.py`) | `rag_document`, `rag_chunk` | Hybrid RAG + Groq LLM. |
| **Hybrid RAG pipeline** | Implemented | `app/services/rag/hybrid_retriever.py` (dense + BM25 + RRF) | internal (called by `assistant_service`) | `rag_document`, `rag_chunk` | Embeddings stored via `pgvector`. |
| **Groq LLM integration** | Implemented | `app/services/security/groq_service.py::call_groq` | internal | – | Uses `GROQ_API_KEY` env var; fallback to generic answer if key missing. |
| **Database persistence** | Implemented | SQLAlchemy models in `app/models/` (e.g., `video.py`, `retail_intelligence.py`) | – | See Section 4 for ER diagram | Migrations in `alembic/versions/`. |
| **CI/CD automation** | Implemented | GitHub Actions in `.github/workflows/` (e.g., `backend.yml`, `frontend.yml`) | – | – | Runs lint, tests, Docker build; does **not** auto‑deploy. |
| **YOLO‑11n MLOps lifecycle** | Implemented | `mlops/training/`, `mlops/evaluation/`, `mlops/registry/` | – | – | Pipeline includes dataset validation, experiment tracking (`mlflow` not used – custom JSON logs), model promotion gates. |
| **ByteTrack tracking** | **Not verified** | – | – | – | The codebase references a `track_id` field but does not import ByteTrack; a simple centroid tracker is used. |
| **SKU / barcode recognition** | **Not implemented** | – | – | – | No code for fine‑grained product classification. |

> **Legend** – *Implemented*: full code path exists and is exercised by tests; *Partially implemented*: skeleton present but missing some logic; *Not verified*: no import or reference found.

---

## 3. High‑Level System Architecture (Mermaid diagram)

```mermaid
flowchart TD
    subgraph Frontend[Next.js Frontend]
        FE[UI Components]
        APIClient[API Client (lib/api)]
    end
    subgraph Backend[FastAPI Backend]
        Router[API Routers]
        Service[Service Layer]
        DB[PostgreSQL + pgvector]
        Redis[Redis (job queue & cache)]
        CV[YOLO‑11n Model (torch)]
        RAG[Hybrid Retrieval (dense + BM25)]
        LLM[Groq LLM]
    end
    FE -->|HTTP/JSON| APIClient -->|calls| Router
    Router --> Service
    Service --> DB
    Service --> Redis
    Service --> CV
    Service --> RAG --> LLM
    DB -->|stores| VideoJob[video_job]
    DB -->|stores| RetailInt[retail_intelligence]
    DB -->|stores| RAGDocs[rag_document]
    Redis -->|queues| VideoJob
```

---

## 4. Database Overview

Key tables (SQLAlchemy models) are listed below.  All models live under `app/models/` and are migrated via Alembic (`alembic/versions/`).

| Table (Model) | Primary Key | Important Columns | Relationships |
|---------------|-------------|-------------------|----------------|
| `store` (`Store`) | `id` | `name`, `location` | one‑to‑many `cameras` |
| `camera` (`Camera`) | `id` | `store_id`, `name`, `feed_url` | many‑to‑one `store`; one‑to‑many `video_jobs` |
| `video_job` (`Video`) | `id` | `camera_id`, `status`, `uploaded_path` | many‑to‑one `camera`; one‑to‑many `video_frames` |
| `video_frame` (`VideoFrame`) | `id` | `video_id`, `frame_number`, `timestamp` | many‑to‑one `video_job` |
| `retail_intelligence` (`RetailIntelligence`) | `id` | `store_id`, `date` | one‑to‑many `visits`, `shelf_events`, `alerts` |
| `visit` (`Visit`) | `id` | `store_id`, `visitor_id`, `entry_ts`, `exit_ts` | many‑to‑one `store` |
| `event` (`Event`) | `id` | `visit_id`, `type`, `timestamp`, `camera_id` | many‑to‑one `visit` |
| `shelf_zone` (`ShelfZone`) | `id` | `store_id`, `polygon_json` | many‑to‑one `store` |
| `shelf_event` (`ShelfEvent`) | `id` | `shelf_zone_id`, `type`, `frame_id` | many‑to‑one `shelf_zone` |
| `rag_document` (`RagDocument`) | `id` | `title`, `source_path` | one‑to‑many `rag_chunks` |
| `rag_chunk` (`RagChunk`) | `id` | `document_id`, `content`, `embedding` (`pgvector`) | many‑to‑one `rag_document` |

Redis is used for **video job queues** (`celery`‑like background tasks) and for caching recent analytics aggregates.

---

## 5. Quick Walk‑through (Image Detection Example)

1. UI component `components/upload/ImageUploader.tsx` posts a multipart file to **`POST /api/v1/images/detect`**.
2. FastAPI route `app/api/images.py::detect_image` receives the file, stores it under `data/uploads/`.
3. Service `app/services/cv_service.py::detect_image` loads **`yolo11n.pt`** (found in `mlops/training/weights/`), runs inference via `torch.hub.load`, filters detections (confidence ≥ 0.3) and returns a list of COCO class names, bounding‑box coordinates and scores.
4. The backend returns JSON; the frontend draws rectangles on a canvas using the data.

All steps are fully exercised by the test `tests/test_image_detection.py` (present in the repo).

---

*The remainder of this document (detailed pipelines, RAG flow, CI/CD, MLOps lifecycle, limitations, etc.) will be expanded in subsequent incremental updates.*
