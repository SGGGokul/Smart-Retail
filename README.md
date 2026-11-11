# RetailIQ — Smart Retail Video Analytics & AI Copilot

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.4.2-black.svg)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19.3.0-61dafb.svg)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-v4-38bdf8.svg)](https://tailwindcss.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17%20with%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-dc382d.svg)](https://redis.io/)
[![YOLO11](https://img.shields.io/badge/YOLO-11n-00ffff.svg)](https://github.com/ultralytics/ultralytics)

RetailIQ is an enterprise-grade smart retail intelligence platform that unifies real-time computer vision, store traffic analytics, inventory monitoring, and a generative AI copilot into a single monorepo. It processes camera feeds and store imagery to compute customer dwell times, visitor counts, queue bottlenecks, and shelf occupancy while providing store managers with an interactive, RAG-grounded operations assistant.

---

## Table of Contents

- [What RetailIQ Does](#what-retailiq-does)
- [Key Implemented Features](#key-implemented-features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Repository Directory Structure](#repository-directory-structure)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
  - [Backend Setup (Local)](#backend-setup-local)
  - [Frontend Setup (Local)](#frontend-setup-local)
- [Environment Configuration](#environment-configuration)
- [Running the Application Locally](#running-the-application-locally)
- [Running with Docker Compose](#running-with-docker-compose)
- [Backend API Documentation](#backend-api-documentation)
- [Frontend Usage Guide](#frontend-usage-guide)
- [Image Detection Workflow](#image-detection-workflow)
- [Video Analytics Workflow](#video-analytics-workflow)
- [Customer Counting & Journey Tracking](#customer-counting--journey-tracking)
- [Database & Persistence](#database--persistence)
- [AI Assistant & Hybrid RAG](#ai-assistant--hybrid-rag)
- [CI/CD Automation & YOLO11n MLOps Platform](#cicd-automation--yolo11n-mlops-platform)
  - [CI/CD Pipeline Architecture](#cicd-pipeline-architecture)
  - [YOLO11n MLOps Lifecycle](#yolo11n-mlops-lifecycle)
  - [MLOps CLI & Reproduction Commands](#mlops-cli--reproduction-commands)
- [Testing Instructions](#testing-instructions)
- [Troubleshooting](#troubleshooting)
- [Current Limitations](#current-limitations)
- [Future Roadmap](#future-roadmap)

---

## What RetailIQ Does

Retail stores generate vast amounts of video footage that remains unanalyzed. RetailIQ turns CCTV and camera streams into actionable operational intelligence:
1. **Tracks Customer Journeys:** Identifies customers entering the store, monitors footfall across defined shopping zones, tracks queue wait times, and registers confirmed store exits.
2. **Visual Shelf & Object Detection:** Allows store associates to upload shelf or store imagery to run high-speed YOLO11n object detection with instant visual bounding-box overlays.
3. **Automated Incident Alerting:** Generates real-time alerts for checkout queue spikes, critical shelf depletion, and anomalous dwell times.
4. **Operations AI Copilot:** Answers natural-language store policy and analytics questions using hybrid RAG (dense vector retrieval + sparse keyword search) grounded strictly in actual store manuals, while seamlessly answering general knowledge questions via Groq LLM integration.

---

## Key Implemented Features

| Feature | Description | Primary Code / API Route |
| :--- | :--- | :--- |
| **Dedicated Image Detection** | High-performance inference on `.jpg`, `.jpeg`, `.png`, and `.webp` files (up to 10MB) returning bounding boxes, labels, confidence scores, and Base64-annotated images. | `POST /api/v1/images/detect`<br>`app/services/image_service.py` |
| **Video Processing Pipeline** | Async video upload for `.mp4`, `.avi`, `.mov`, and `.webm` files with background processing, job tracking, and FPS benchmarking. | `POST /api/v1/videos`<br>`app/services/video_service.py` |
| **Customer Journey Tracking** | Tracks visits, entry/exit boundary line crossings, polygon-based zone occupancy, dwell times, and repeat visit frequency. | `POST /api/v1/journey/*`<br>`app/services/visit_service.py` |
| **Zone Service** | Point-in-polygon containment math for convex and L-shaped concave shopping zones with temporary disappearance smoothing. | `app/services/zone_service.py` |
| **PostgreSQL 17 + pgvector** | Async database persistence for store entities, video jobs, visits, alerts, and 384-dimensional semantic document embeddings. | `app/db/session.py`<br>`app/models/` |
| **Redis Sliding-Window Rate Limiting** | Tier-based client IP rate limiting (10 req/min for uploads, 60 req/min for general APIs) with fail-closed security. | `app/core/rate_limit.py` |
| **Hybrid RAG Assistant** | Dual-channel retrieval (Reciprocal Rank Fusion over vector similarity + BM25 keyword matching) grounded on store SOPs. | `app/services/rag/`<br>`POST /api/v1/assistant/chat` |
| **Groq LLM Fallback & Security Guardrails** | Routes general knowledge questions to Groq LLMs without hallucinating store metrics; sanitizes prompt injection and Unicode homoglyphs. | `app/services/security/` |
| **Next.js 16 Web Dashboard** | 10 modern dashboards with reactive Recharts, tabbed image/video analytics, shelf bay monitors, and AI Copilot chat. | `Frontend/app/` |

---

## System Architecture

```mermaid
flowchart TD
    subgraph ClientLayer ["Client & Frontend (Port 3000)"]
        Browser["Store Manager Browser"]
        NextApp["Next.js 16 App Router<br>(React 19, TailwindCSS v4)"]
        CanvasOverlay["Interactive Canvas<br>Bounding Box Overlay"]
    end

    subgraph APILayer ["FastAPI Backend (Port 8000)"]
        Gateway["FastAPI Gateway & Lifespan"]
        RateLimiter["Redis Rate Limiter<br>(Sliding Window)"]
        Guardrails["Security Guardrails<br>(Input/Output Sanitization)"]
        
        subgraph Endpoints ["REST API Modules"]
            ImgAPI["Image Detection API<br>/api/v1/images/detect"]
            VidAPI["Video Processing API<br>/api/v1/videos"]
            JourneyAPI["Customer Journey API<br>/api/v1/journey"]
            ShelfAPI["Shelf Monitoring API<br>/api/v1/shelves"]
            ChatAPI["AI Copilot API<br>/api/v1/assistant/chat"]
        end
    end

    subgraph ProcessingLayer ["Computer Vision & AI Engines"]
        YOLO["YOLO11n Inference Engine<br>(PyTorch / OpenCV)"]
        VisitTracker["Visit & Zone Service<br>(Polygon Containment Math)"]
        HybridRAG["Hybrid RAG Engine<br>(Vector + BM25 RRF)"]
        GroqLLM["Groq Llama 3 / Mixtral API<br>(General Knowledge Fallback)"]
    end

    subgraph DataLayer ["Persistence & Storage"]
        PG[("PostgreSQL 17 + pgvector<br>(Store Data, Visits, Embeddings)")]
        RedisDB[("Redis 7<br>(Rate Limit Counters & Cache)")]
        FileStore["Local File Storage<br>(data/uploads, data/documents)"]
    end

    Browser <--> NextApp
    NextApp --> CanvasOverlay
    NextApp <-->|HTTP / JSON| Gateway
    Gateway --> RateLimiter
    RateLimiter --> RedisDB
    Gateway --> Guardrails
    Guardrails --> Endpoints

    ImgAPI --> YOLO
    VidAPI --> YOLO
    VidAPI --> VisitTracker
    JourneyAPI --> VisitTracker
    ChatAPI --> HybridRAG
    ChatAPI --> GroqLLM

    VisitTracker <--> PG
    HybridRAG <--> PG
    YOLO --> FileStore
    VidAPI --> FileStore
```

---

## Technology Stack

### Backend
- **Framework:** FastAPI 0.115+, Uvicorn, Starlette, Pydantic v2
- **Database ORM:** SQLAlchemy 2.0 (asyncio + `asyncpg`), Alembic
- **Database Engine:** PostgreSQL 17 with `pgvector` extension
- **Cache & Rate Limiting:** Redis 7 with `redis-py`
- **Computer Vision:** Ultralytics YOLO11n (`yolo11n.pt`), OpenCV (`opencv-python-headless`)
- **Natural Language Processing & RAG:** PyPDF, NumPy, Groq SDK

### Frontend
- **Framework:** Next.js 16.4.2 (App Router, Webpack/Turbopack enabled)
- **UI Library:** React 19.3.0, React DOM 19.3.0
- **Styling:** Tailwind CSS v4 (`@tailwindcss/postcss`)
- **Charts & Data Visualization:** Recharts 3.10.1
- **Icons:** Lucide React (`lucide-react`)
- **Testing:** Playwright 1.64.1 (E2E), Node.js native test runner

---

## Repository Directory Structure

```text
Smart-Retail/                          # Monorepo Root (Backend at root)
├── Frontend/                          # Next.js 16 Web Application
│   ├── app/                           # App Router pages (Dashboard, Analytics, Copilot)
│   ├── components/                    # Reusable React components (Charts, KPIs, Nav)
│   ├── lib/                           # Centralized API client & utility functions
│   ├── public/                        # Static SVG and image assets
│   ├── types/                         # TypeScript interfaces and API schemas
│   ├── e2e/                           # Playwright end-to-end test suites
│   ├── package.json                   # Frontend dependencies
│   ├── pnpm-lock.yaml                 # Frontend lockfile
│   ├── tsconfig.json                  # TypeScript configuration
│   ├── next.config.ts                 # Next.js configuration
│   └── Dockerfile                     # Multi-stage production container
├── app/                               # FastAPI Backend Application
│   ├── api/                           # Route controllers (health, analytics, images, etc.)
│   ├── core/                          # Settings, logging, rate limiting
│   ├── db/                            # Database connection session and Base model
│   ├── models/                        # SQLAlchemy database models
│   ├── schemas/                       # Pydantic request/response schemas
│   └── services/                      # CV inference, RAG, Visit & Zone services
├── alembic/                           # Database migration scripts (0001, 0002, 0003)
├── tests/                             # Backend Pytest test suites (170 tests)
│   ├── e2e/                           # Async E2E journey and rate limiting tests
│   └── ...                            # Unit tests for RAG, CV, Visits, and Guardrails
├── data/                              # Data directories
│   ├── documents/                     # Store SOP PDFs and operational text files
│   └── uploads/                       # Runtime video and image upload destination
├── docker-compose.yml                 # Monorepo multi-container Docker configuration
├── Dockerfile                         # Backend container definition
├── .dockerignore                      # Backend Docker build context exclusions
├── .gitignore                         # Monorepo root ignore rules
├── .env.example                       # Environment configuration template
├── requirements.txt                   # Backend Python dependencies
├── yolo11n.pt                         # YOLO11n weights file (5.6 MB)
└── README.md                          # Project documentation
```

---

## Prerequisites

- **Python:** 3.11, 3.12, or 3.13
- **Node.js:** v20.x or v22.x LTS
- **Package Manager:** `pnpm` (v9 or v12 recommended)
- **Database:** PostgreSQL 17 (with `pgvector` extension)
- **In-Memory Cache:** Redis 7
- **Docker & Docker Compose:** Docker Desktop (if using containerized setup)

---

## Installation and Setup

### 1. Clone the Repository
```powershell
git clone https://github.com/SGGGokul/Smart-Retail.git
cd Smart-Retail
```

### 2. Backend Setup (Local)
Create and activate a virtual environment, then install Python dependencies:

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify that the YOLO weights file exists at repository root (`yolo11n.pt`). If missing, download it via Ultralytics:
```powershell
python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"
```

### 3. Frontend Setup (Local)
Navigate into the `Frontend/` folder and install dependencies using `pnpm`:

```powershell
cd Frontend
pnpm install --frozen-lockfile
cd ..
```

---

## Environment Configuration

Copy `.env.example` to `.env` at repository root:

```powershell
Copy-Item .env.example .env
```

### Key Environment Variables

| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:password@localhost:5432/retailiq` | Async connection string for PostgreSQL. |
| `RATE_LIMIT_REDIS_URL` | `redis://localhost:6379/1` | Redis connection URL for rate limiter. |
| `RATE_LIMIT_ENABLED` | `true` | Enables or disables sliding-window rate limiting. |
| `MODEL_PATH` | `yolo11n.pt` | Path to YOLO11n model weights. |
| `GROQ_API_KEY` | `""` | (Optional) Groq API key for AI Copilot general knowledge queries. |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Browser base URL for frontend API calls. |

---

## Running the Application Locally

### 1. Start Infrastructure Dependencies
Ensure PostgreSQL 17 (with pgvector) and Redis 7 are running locally on ports `5432` and `6379`.

### 2. Run Database Migrations
```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 3. Start the Backend API Server
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*The FastAPI backend will be live at `http://127.0.0.1:8000`. Interactive Swagger API docs are accessible at `http://127.0.0.1:8000/docs`.*

### 4. Start the Frontend Development Server
In a separate terminal window:
```powershell
cd Frontend
pnpm run dev --port 3000
```
*The Next.js web application will be live at `http://localhost:3000`.*

---

## Running with Docker Compose

RetailIQ includes a root `docker-compose.yml` that starts PostgreSQL with pgvector, Redis 7, the FastAPI backend, and the Next.js frontend in a single command.

```powershell
docker compose up --build
```

### Services Started:
- **FastAPI Backend:** `http://localhost:8000`
- **Next.js Frontend:** `http://localhost:3000`
- **PostgreSQL 17 (pgvector):** `localhost:5432`
- **Redis 7:** `localhost:6379`

To stop the containers:
```powershell
docker compose down
```

---

## Backend API Documentation

### Key Endpoints

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Health** | `GET` | `/health` | Verifies service health, database connectivity, and Redis connectivity. |
| **Image Detection** | `POST` | `/api/v1/images/detect` | Multipart upload for image inference (`.jpg`, `.png`, `.webp`). |
| **Video Processing** | `POST` | `/api/v1/videos` | Multipart upload for video files (`.mp4`, `.avi`, `.mov`, `.webm`). |
| **Video Status** | `GET` | `/api/v1/videos/{job_id}` | Returns video processing status and metrics. |
| **Video Results** | `GET` | `/api/v1/videos/{job_id}/results` | Returns detailed object detection and customer track results. |
| **Shelf Monitoring** | `GET` | `/api/v1/shelves` | Lists all retail shelf bays with current stock status. |
| **Shelf Inference** | `POST` | `/api/v1/shelves/detect` | Runs shelf image inference for item counting. |
| **Analytics Summary** | `GET` | `/api/v1/analytics/summary` | Aggregate KPI statistics for today's store traffic and shelves. |
| **Traffic Analytics** | `GET` | `/api/v1/analytics/traffic` | Daily and hourly customer footfall breakdown. |
| **Alerts** | `GET` | `/api/v1/alerts` | Lists active unacknowledged incidents and alerts. |
| **AI Copilot Chat** | `POST` | `/api/v1/assistant/chat` | Dual-channel RAG + Groq query answering endpoint. |
| **Customer Journey** | `POST` | `/api/v1/journey/entrance` | Registers a customer entrance event. |
| **Customer Journey** | `POST` | `/api/v1/journey/exit` | Registers a confirmed customer exit event. |

---

## Image Detection Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Associate as Store Associate
    participant UI as Frontend (/video-analytics)
    participant API as FastAPI (/api/v1/images/detect)
    participant Service as ImageService & CVService
    participant YOLO as YOLO11n Model

    Associate->>UI: Selects .jpg, .png, or .webp image
    UI->>UI: Validates file size (<10MB) & displays preview
    UI->>API: POST /api/v1/images/detect (multipart/form-data)
    API->>API: Validates extension & reads binary into OpenCV
    API->>Service: detect_image(image_bytes)
    Service->>YOLO: Runs model.predict(conf=0.25)
    YOLO-->>Service: Bounding boxes, labels, confidences
    Service->>Service: Generates Base64 annotated image & coordinates
    Service-->>API: ImageDetectionResponse
    API-->>UI: JSON (detections, annotated_image_base64, dimensions)
    UI->>UI: Draws interactive canvas overlay with colored bounding boxes
```

---

## Video Analytics Workflow

1. **Submission:** Upload `.mp4`, `.avi`, `.mov`, or `.webm` footage via `POST /api/v1/videos`.
2. **Job Creation:** The backend stores the video under `data/uploads/`, registers a `VideoJob` in PostgreSQL with status `processing`, and spawns an asynchronous processing task.
3. **Tracking & Analysis:** The video pipeline samples frames, detects customer bounding boxes with YOLO11n, computes dwell times, and evaluates directional crossing lines.
4. **Polling:** The frontend polls `GET /api/v1/videos/{job_id}` until status reaches `completed`.
5. **Results Retrieval:** `GET /api/v1/videos/{job_id}/results` returns full detection coordinates, FPS benchmarks, and traffic counts.

---

## Unified Customer Intelligence & Daily Visitor Identity

RetailIQ implements an enterprise-grade multi-camera customer intelligence and shelf interaction system (`app/services/identity_service.py`, `app/services/shelf_service.py`, `app/services/visit_service.py`):

### 3-Level Identity Hierarchy
1. **Raw Person Detection:** Every bounding box generated by YOLO11n in a video frame. Raw detections never inflate unique footfall counters.
2. **Camera-Level Track:** Composite identity scoped to `camera_id + tracker_id + tracking_lifetime`. Tracker IDs are camera-local and transient.
3. **Store-Day Global Visitor Identity:** Anonymous identity scoped strictly to `store_id + store-local calendar date`. A person visiting a store counts as exactly **1 unique daily visitor** regardless of how many cameras observe them or how many times they exit and return on that local calendar day.
4. **Visit Sessions:** Each distinct entrance-to-exit journey generates an independent visit session linked to the person's daily visitor identity with an incremented `visit_number`.

### Midnight Boundary & Timezone Handling
- Store operating dates are resolved using store-specific IANA timezones (e.g., `America/New_York`, `Europe/London`, `UTC`).
- At local midnight (00:00:00), the previous store-day identities expire. Any customer entering the store on the subsequent calendar day receives a new anonymous daily identity.

### Anonymous Appearance Re-ID (Multi-Camera)
- **Privacy-Preserving Embeddings:** Uses a 3-tier upper-torso/lower-body spatial HSV color histogram embedding (no facial recognition, no PII, no biometric identifiers).
- **Ambiguity Margin Protection:** Requires cosine similarity >= 0.78 for confident matching. If the top-2 match candidates fall within a narrow margin (<= 0.10 difference), the match is isolated as `uncertain` to prevent silent identity cross-contamination.
- **Topological Conflict Resolution:** A single person cannot physically appear on two non-overlapping cameras at the exact same second. Such simultaneous appearances are flagged as distinct individuals unless explicitly registered as overlapping physical fields of view (`register_overlapping_cameras`).

### Shelf Monitoring & Product Interaction State Machine
- **Geometric Bay Fill:** Polygonal shelf bays compute item capacity and occupancy using point-in-polygon containment and spatial grid empty-slot detection.
- **Fill Health Classifications:**
  - Optimal (`ok`): Fill > 70%
  - Low Stock (`low`): Fill between 40% and 70%
  - Critical Restock (`critical`): Fill < 40%
- **Customer Interactions:** Monitors customer proximity and reaching events into designated interaction polygons.
- **Temporal Pickup State Machine:**
  - `candidate`: Initiated when shelf count decreases during/following an active customer reach.
  - `confirmed`: Promoted after sustained item disappearance across >= 5 consecutive frames.
  - `rejected`: Cancelled if item re-appears within temporal recovery window (transient occlusion).
  - `uncertain`: Flagged if reach evidence is ambiguous or contradictory.
- **Temporal Return State Machine:**
  - `candidate`: Initiated when new items appear in bay following customer interaction.
  - `confirmed`: Promoted after sustained presence across >= 5 consecutive frames.
  - Automatically associates with prior pickup events by the same visitor identity where reliable.

---

## Customer Counting & Journey Tracking

RetailIQ implements a dedicated visit and zone management service (`app/services/visit_service.py` and `app/services/zone_service.py`):
- **Sequential & Thread-Safe Customer IDs:** Generates predictable customer identifiers (`CUST-000001`, `CUST-000002`).
- **Zone Polygon Containment:** Uses the ray-casting algorithm to determine if a customer's `(x, y)` coordinate falls within defined convex or concave (L-shaped) shopping zones.
- **Directional Crossing Lines:** Evaluates vector cross products across virtual entrance/exit tripwires to register entry and exit events.
- **Session Continuity:** Tolerates short temporary tracking losses (e.g. occlusions behind displays) without closing active customer visits prematurely.
- **Repeat Visit Analytics:** Tracks repeat visits per customer identifier in PostgreSQL.

---

## Database & Persistence

The backend utilizes PostgreSQL 17 with Alembic migrations:
- **`stores` & `cameras`:** Physical store locations, camera configurations, and resolution manifests.
- **`video_jobs`:** Video processing state, file paths, and metadata.
- **`customer_visits` & `customer_events`:** Visitor timeline, zone transitions, entry timestamps, and exit timestamps.
- **`alerts` & `store_analytics`:** Incident reports, hourly traffic counters, and queue metrics.
- **`rag_documents` & `rag_document_chunks`:** Document metadata and 384-dimensional chunk embeddings stored using `pgvector`.

---

## AI Assistant & Hybrid RAG

The RetailIQ AI Assistant (`POST /api/v1/assistant/chat`) routes queries intelligently:

1. **Store-Specific Queries:**
   - Evaluates queries such as *"What is our store return policy?"* or *"How many customers visited today?"*.
   - Retrieves relevant text chunks from `data/documents/inventory_and_restocking_policy.pdf` and `store_operating_procedures.txt` using Reciprocal Rank Fusion (RRF) combining dense vector similarity with sparse BM25 scoring.
   - Merges retrieved SOP text with real database analytics counters.
   - Never fabricates or hallucinates visitor numbers.
2. **General Knowledge Queries:**
   - Questions such as *"Write a Python Fibonacci series"* or general inquiries are routed to Groq LLMs (Llama 3 / Mixtral) rather than returning a "document not found" error.
3. **Security Guardrails:**
   - Strips zero-width invisible characters and mathematical alphanumeric Unicode symbols.
   - Detects prompt injection attempts (e.g., *"ignore previous instructions"*).
   - Redacts exposed API keys and strips executable HTML/JavaScript from model outputs.

---

## CI/CD Automation & YOLO11n MLOps Platform

RetailIQ incorporates enterprise-grade CI/CD automation and an end-to-end MLOps platform tailored for YOLO11n object detection models.

### CI/CD Pipeline Architecture

All pull requests and commits to `main` trigger parallelized GitHub Actions workflows orchestrating testing, database migrations, container builds, security audits, container registry releases, and automated deployment verification:

```mermaid
flowchart TD
    PushPR["Git Push / Pull Request to main"] --> CI["ci.yml (Orchestrator)"]

    subgraph ParallelValidation ["Parallel CI Matrix"]
        CI --> B_CI["backend-tests.yml<br>(Python 3.11, Lint, Pytest)"]
        CI --> F_CI["frontend-tests.yml<br>(Node 20, tsc, Unit Tests, Build)"]
        CI --> DB_CI["database-integration.yml<br>(PostgreSQL 17 pgvector, Redis 7, Alembic)"]
        CI --> DOCK_CI["docker-build.yml<br>(BuildKit, Layer Cache, Compose Verify)"]
        CI --> SEC_CI["security.yml<br>(TruffleHog, pip-audit, pnpm audit)"]
        CI --> ML_CI["ml-validation.yml<br>(Dataset Check, MLOps Tests, Model Integrity)"]
    end

    B_CI & F_CI & DB_CI & DOCK_CI & SEC_CI & ML_CI --> GatesPassed{"All CI Jobs Pass?"}
    GatesPassed -->|Yes on main| Release["release.yml<br>(GHCR Container Images, SemVer Tagging)"]
    Release --> Deploy["deploy.yml<br>(Reusable CD Workflow, /api/v1/health Verification)"]
    Deploy --> HealthCheck{"Health Verified?"}
    HealthCheck -->|Failure| Rollback["Automatic Rollback Triggered"]
    HealthCheck -->|Success| Deployed["Production Live"]
    GatesPassed -->|No| BlockMerge["Block PR Merge / Alert"]
```

### YOLO11n MLOps Lifecycle

The MLOps platform manages the full lifecycle of custom YOLO retail detection models with strict quality gates:

```mermaid
flowchart LR
    Dataset["Dataset<br>(retail_dataset.yaml)"] --> Validator["DatasetValidator<br>(BBox Bounds [0,1], Classes, Leakage Check)"]
    Validator --> Versioner["DatasetVersioner<br>(Deterministic SHA256 Manifest)"]
    Versioner --> Training["YOLOTrainingPipeline<br>(Deterministic Seeds, Config Validation)"]
    Training --> Tracker["ExperimentTracker<br>(Metrics: mAP50, Loss, Latency)"]
    Tracker --> Evaluator["ModelEvaluator<br>(Validation Set Metrics & Benchmarks)"]
    Evaluator --> Gate["PromotionGate<br>(mAP Drop=0, Class Regr <= 2%, Latency <= 35ms)"]
    Gate -->|Approved| Registry["ModelRegistry<br>(candidate -> staging -> production)"]
    Registry --> Runtime["ModelService<br>(Checksum Validation, Dynamic Reload)"]
    Runtime --> Monitor["DriftMonitor<br>(Confidence, Empty Detection, Latency, TVD)"]
    Registry -.->|On Failure| RollbackModel["Atomic Model Rollback<br>(Previous Production Version)"]
```

1. **Dataset Validation & Versioning (`mlops/dataset/`):** Validates normalized bounding box constraints `[0, 1]`, class IDs, image-label pairing, and detects train/val/test data leakage. Generates deterministic SHA256 manifests.
2. **Reproducible Training Pipeline (`mlops/training/`):** Deterministic random seeds across Python, NumPy, and PyTorch. Configurable hyperparameters and automated artifact manifests (`training_manifest.json`).
3. **Experiment Tracking & Evaluation (`mlops/tracking/`, `mlops/evaluation/`):** Logs metrics across runs and generates standardized evaluation reports with per-class breakdowns and latency benchmarks.
4. **Promotion Gates & Model Registry (`mlops/registry/`, `mlops/evaluation/promotion_gate.py`):**
   - Automatically validates candidate models against production baselines.
   - Enforces zero mAP regression and a strict $\le 2\%$ tolerance ceiling for critical retail classes (`person`, `shelf`, `product`).
   - Maintains versioned checkpoints with SHA256 checksums and supports atomic production rollback.
5. **Runtime Inference Integration (`app/services/model_service.py`):**
   - Lazily loads approved production models from the registry.
   - Validates physical file checksum integrity before loading.
   - Exposes active model version metadata via `GET /api/v1/model/info` and dynamic reloading via `POST /api/v1/model/reload`.
6. **Continuous Monitoring & Drift Reporting (`mlops/monitoring/`):** Tracks rolling latency, confidence distributions, empty detection rates, and Total Variation Distance (TVD) for class frequency shifts.

### MLOps CLI & Reproduction Commands

```powershell
# 1. Run all MLOps test suites (Dataset, Training, Tracking, Registry, Monitoring, Model Service)
python -m pytest tests/ -k "mlops or model_inference" -v

# 2. Run dataset validation and generate version manifest
python -c "
from mlops.dataset.validator import DatasetValidator
from mlops.dataset.versioning import DatasetVersioner
validator = DatasetValidator('mlops/dataset/retail_dataset.yaml')
print('Classes:', validator.classes)
"

# 3. Launch reproducible YOLO11n training (dry-run for local validation)
python mlops/training/train.py --data mlops/dataset/retail_dataset.yaml --epochs 5 --imgsz 640 --batch 8 --dry-run

# 4. Check active production model info via API
curl http://127.0.0.1:8000/api/v1/model/info
```

---

## Testing Instructions

### Backend Test Suite
Run the 170-test suite using pytest:

```powershell
# Run all unit, service, RAG, and image detection tests
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

To run offline unit tests with live rate-limiting bypassed:
```powershell
$env:RATE_LIMIT_ENABLED = "false"
.\.venv\Scripts\python.exe -m pytest tests/test_image_detection.py tests/test_hybrid_rag.py tests/test_health.py tests/test_shelves.py tests/test_guardrails_and_groq.py -v
```

### Frontend Test Suite
Run TypeScript validation, unit tests, and production build:

```powershell
cd Frontend

# Typecheck
pnpm exec tsc --noEmit

# Unit tests
pnpm run test

# Production build
pnpm run build

# Playwright E2E tests (when backend is running)
pnpm exec playwright test
```

---

## Troubleshooting

### 1. Redis Connection / 429 Too Many Requests
- **Symptom:** Backend returns `429 Too Many Requests` immediately with log `Rate limiter failing closed due to Redis error`.
- **Cause:** Redis is offline or unreachable on port 6379.
- **Fix:** Start Redis via Docker (`docker compose up -d redis`) or set `RATE_LIMIT_ENABLED=false` in `.env`.

### 2. Database Connection Refused
- **Symptom:** `ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection`.
- **Cause:** PostgreSQL is not running on port 5432.
- **Fix:** Start PostgreSQL via Docker (`docker compose up -d postgres`) and run `alembic upgrade head`.

### 3. Image Upload Rejection on Video Endpoint
- **Symptom:** `Unsupported video format '.jpg'. Allowed formats: ['.avi', '.mov', '.mp4', '.webm']`.
- **Cause:** Submitting an image file to `POST /api/v1/videos`.
- **Fix:** Submit images to the dedicated `POST /api/v1/images/detect` endpoint. The frontend Video Analytics page automatically routes images to this endpoint.

---

## Current Limitations

1. **Generic Object Classes:** The YOLO11n model is trained on the 80 COCO classes (person, bottle, chair, etc.). It does not perform granular barcode-level or SKU-level product recognition.
2. **Shelf Out-of-Stock Estimation:** Shelf occupancy is calculated geometrically from detected bounding boxes within defined shelf regions; it does not constitute full planogram compliance verification.
3. **Local Video Storage:** Uploaded footage is stored on the local filesystem (`data/uploads/`) rather than an S3/cloud object store.

---

## Future Roadmap

- [ ] Multi-camera re-identification (ReID) across blind spots using deep feature embeddings.
- [ ] Integration of Vision-Language Models (VLMs) for zero-shot retail loss prevention detection.
- [ ] Direct RTSP stream ingestion for live CCTV IP cameras.
- [ ] Cloud object storage integration (AWS S3 / Google Cloud Storage) for uploaded videos.
- [ ] Role-based access control (RBAC) with SSO integration for store associates and enterprise managers.

---

## License

This project is licensed under the MIT License.
