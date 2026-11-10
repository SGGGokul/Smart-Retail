# RetailIQ – Architecture Diagrams

## 1. High‑Level System Diagram
```mermaid
flowchart TD
    subgraph FE[Frontend (Next.js)]
        UI[UI Pages & Components]
        APIClient[API Client (lib/api)]
    end
    subgraph BE[Backend (FastAPI)]
        Router[API Routers]
        Service[Service Layer]
        DB[PostgreSQL + pgvector]
        Redis[Redis (job queue & cache)]
        CV[YOLO‑11n (torch)]
        RAG[Hybrid Retrieval (dense + BM25)]
        LLM[Groq LLM]
    end
    UI -->|HTTP/JSON| APIClient -->|calls| Router
    Router --> Service
    Service --> DB
    Service --> Redis
    Service --> CV
    Service --> RAG --> LLM
    DB -->|stores| VideoJob[video_job]
    DB -->|stores| RetailInt[retail_intelligence]
    DB -->|stores| RagDoc[rag_document]
    Redis -->|queues| VideoJob
```

## 2. Backend Component Diagram
```mermaid
graph LR
    A[FastAPI] --> B[API Routers]
    B --> C[Services]
    C --> D[CV Service]
    C --> E[Video Service]
    C --> F[Shelf Service]
    C --> G[Identity Service]
    C --> H[Analytics Service]
    C --> I[RAG Service]
    D --> J[YOLO‑11n Model (torch)]
    E --> K[Redis Job Queue]
    I --> L[pgvector DB (embeddings)]
    I --> M[BM25 Engine (in‑memory)]
    I --> N[Groq LLM]
    H --> O[Event & Visit DB tables]
```

## 3. Database & Persistence Diagram
```mermaid
erDiagram
    STORE ||--o{ CAMERA : "has"
    CAMERA ||--o{ VIDEO_JOB : "records"
    VIDEO_JOB ||--o{ VIDEO_FRAME : "contains"
    STORE ||--o{ RETAIL_INTELLIGENCE : "aggregates"
    RETAIL_INTELLIGENCE ||--o{ VISIT : "has"
    VISIT ||--o{ EVENT : "generates"
    RETAIL_INTELLIGENCE ||--o{ SHELF_ZONE : "defines"
    SHELF_ZONE ||--o{ SHELF_EVENT : "logs"
    RETAIL_INTELLIGENCE ||--o{ RAG_DOCUMENT : "stores"
    RAG_DOCUMENT ||--o{ RAG_CHUNK : "has"
    RAG_CHUNK }|..|{ PGVECTOR : "embedding"
```

## 4. Frontend ↔ Backend Communication Diagram
```mermaid
sequenceDiagram
    participant UI as Frontend (React/TS)
    participant API as API Client (lib/api)
    participant BE as FastAPI Backend
    participant DB as PostgreSQL
    participant RED as Redis
    UI->>API: POST /api/v1/videos/upload (multipart)
    API->>BE: upload_video()
    BE->>RED: enqueue video job
    BE->>DB: store VideoJob metadata
    RED->>BE: background worker picks job
    BE->>CV: run YOLO inference on frames
    CV->>BE: detections per frame
    BE->>DB: persist analytics events
    BE->>API: job status endpoint
    API->>UI: poll /status, display results
```

## 5. Computer‑Vision Inference Pipeline (YOLO‑11n)
```mermaid
flowchart TD
    A[Video Upload] --> B[Save to /data/uploads]
    B --> C[Create VideoJob record]
    C --> D[Background worker reads job]
    D --> E[Extract frames (OpenCV)]
    E --> F[Pre‑process (resize, normalize)]
    F --> G[YOLO‑11n model inference]
    G --> H[Filter by confidence ≥ 0.3]
    H --> I[Optional tracking (centroid tracker)]
    I --> J[Zone & Shelf checks]
    J --> K[Persist detections & analytics]
    K --> L[Update VideoJob status]
``` 

## 6. RAG Retrieval & Generation Pipeline
```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as /assistant/chat
    participant BE as FastAPI
    participant RAG as HybridRetriever
    participant DB as PostgreSQL (pgvector)
    participant LLM as Groq
    UI->>API: POST query
    API->>BE: handle_query()
    BE->>RAG: retrieve_dense(query)
    RAG->>DB: SELECT * FROM rag_chunk ORDER BY embedding <‑> query_vector
    BE->>RAG: retrieve_sparse(query)  
    RAG->>DB: BM25 search over rag_document.text
    RAG->>RAG: Combine results via Reciprocal Rank Fusion
    RAG->>BE: top‑k chunks
    BE->>LLM: prompt = system + chunks + user query
    LLM->>BE: generated answer
    BE->>API: response (with citations)
    API->>UI: display answer
```

## 7. CI/CD Workflow Diagram
```mermaid
flowchart TD
    subgraph PR[Pull Request]
        Lint[Lint (flake8, ESLint)]
        Unit[Backend Unit Tests]
        FrontTest[Frontend Playwright Tests]
        Build[Docker Build]
        Sec[Security Scan (trivy)]
    end
    PR --> Lint --> Unit --> FrontTest --> Build --> Sec
    Sec -->|pass| Deploy[No auto‑deploy (manual step)]
```

## 8. YOLO‑11n MLOps Lifecycle
```mermaid
flowchart LR
    DS[Dataset Validation] --> TR[Training (mlops/training)]
    TR --> EV[Evaluation (mlops/evaluation)]
    EV --> MET[Metrics: mAP50, mAP50‑95, latency]
    MET --> REG[Model Registry (mlops/registry)]
    REG --> GATE[Promotion Gate (thresholds)]
    GATE --> PROD[Production Model (weights/yolo11n.pt)]
    PROD --> INF[Inference Service (cv_service)]
    INF --> MON[Monitoring (mlops/monitoring)]
```

---
*All diagrams reference files that exist in the repository (e.g., `mlops/training/`, `app/services/cv_service.py`).*