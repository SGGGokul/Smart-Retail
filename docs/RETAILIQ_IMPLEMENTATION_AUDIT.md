# Implementation Audit – Repository Overview

## Verified Repository Structure
The local workspace **D:\Download\CISG\Backend** matches the monorepo described in the GitHub project. The top‑level directories are:

```
Backend/
├─ .github/                # GitHub Actions workflows
├─ .venv/                  # Python virtual environment (local only)
├─ alembic/                # Database migration scripts
├─ app/                    # FastAPI backend source
│   ├─ api/                # API router modules
│   ├─ core/               # Configuration, logging, rate‑limit, state helpers
│   ├─ db/                 # SQLAlchemy session & base
│   ├─ models/             # ORM model definitions
│   ├─ schemas/            # Pydantic request/response schemas
│   ├─ services/           # Business‑logic layer (CV, RAG, analytics, etc.)
│   └─ main.py             # FastAPI application entry point
├─ data/                   # Sample documents, uploads, external assets
├─ mlops/                  # YOLO11n training / evaluation / model registry
├─ results/                # Sample inference frames, ground‑truth data
├─ tests/                  # Backend unit‑ and integration‑tests
├─ Frontend/               # Next.js (React, TypeScript) UI
│   ├─ app/                # Next.js page hierarchy (e.g. /video‑analytics)
│   ├─ components/         # Re‑usable UI components (charts, dashboard, layout)
│   ├─ lib/                # API client wrappers used by the UI
│   ├─ public/             # Static assets
│   └─ types/              # TypeScript type definitions for API contracts
└─ ... (configuration files, Dockerfiles, README, etc.)
```

## Important Source Files (selected for audit)
| Area | File | Purpose |
|------|------|---------|
| **API routers** | `app/api/alerts.py` | CRUD endpoints for alert definitions |
| | `app/api/analytics.py` | Analytics aggregation endpoints |
| | `app/api/assistant.py` | AI Copilot (RAG) request handling |
| | `app/api/customer_journey.py` | Visitor‑journey related routes |
| | `app/api/events.py` | Event logging & retrieval |
| | `app/api/images.py` | Image upload & detection endpoint |
| | `app/api/model.py` | Model metadata & reload endpoints |
| | `app/api/shelves.py` | Shelf‑monitoring CRUD APIs |
| | `app/api/videos.py` | Video upload, job creation, status polling |
| **Core services** | `app/services/cv_service.py` | Loads YOLO‑11n, runs inference on images/video frames |
| | `app/services/video_service.py` | Background video‑job orchestration, frame extraction, analytics pipeline |
| | `app/services/shelf_service.py` | Shelf polygon config, occupancy state machine |
| | `app/services/identity_service.py` | Person detection → tracker → daily‑visitor identity logic |
| | `app/services/visit_service.py` | Visit‑session handling, re‑identification across cameras |
| | `app/services/zone_service.py` | Zone definition & entry/exit detection |
| | `app/services/analytics_service.py` | Computes footfall, dwell‑time, occupancy metrics |
| | `app/services/assistant_service.py` | High‑level orchestration of the AI Copilot workflow |
| | `app/services/rag/*` | Document ingestion, embedding, hybrid retrieval, response generation |
| | `app/services/security/*` | Input guardrails, output sanitisation, Groq integration |
| **Models** | `app/models/video.py` | Video job DB model |
| | `app/models/retail_intelligence.py` | Core analytics tables (visits, events, shelves) |
| | `app/models/rag.py` | Document & chunk persistence (pgvector) |
| **MLOps** | `mlops/training/` | Training scripts for YOLO‑11n (dataset loading, hyper‑params) |
| | `mlops/evaluation/` | Evaluation metrics calculation (mAP, latency, etc.) |
| | `mlops/registry/` | Model‑registry utilities and promotion gates |
| **Tests** | `tests/` | Pytest suite covering API routes, services and CV pipeline |

These files constitute the concrete implementation basis for the documentation that follows. All subsequent sections will reference the exact file paths and function/class names listed above.

---
*This audit file is generated incrementally; further stages will expand on each component.*
