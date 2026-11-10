# RetailIQ – Project Presentation Notes

## 2‑Minute Elevator Pitch (Non‑Technical)
RetailIQ turns ordinary CCTV footage into a powerful retail intelligence dashboard.  Store managers upload a video or an image and instantly get:
- How many customers entered the store and how long they stayed.
- Which shelves are low on stock.
- Real‑time alerts when a customer picks up a product.
- An AI Copilot that can answer policy questions (e.g., return policy) by searching the store’s own documents.
All of this runs locally in Docker – no cloud data is sent out.

## 5‑Minute Technical Overview (For a Technical Audience)
1. **Frontend** – Next.js (React + TypeScript) with Tailwind CSS.  Pages under `Frontend/app/` (e.g., `/video‑analytics`, `/shelf‑monitoring`).  API calls are wrapped in `Frontend/lib/api/*` which use the browser `fetch` API.
2. **Backend** – FastAPI (`app/`).  Routers (`app/api/*.py`) expose REST endpoints; a thin service layer (`app/services/*`) implements business logic.
3. **Computer Vision** – YOLO‑11n Nano model (`mlops/training/weights/yolo11n.pt`) loaded with PyTorch.  Video jobs are queued in Redis; a background worker extracts frames with OpenCV, runs inference, applies a simple centroid tracker, and writes detections to PostgreSQL.
4. **Identity & Re‑ID** – Detections are first assigned a per‑camera `track_id`.  At day‑level a `daily_visitor_id` is created; cross‑camera matching uses HSV colour histogram similarity (lightweight heuristic).
5. **Shelf Monitoring** – Shelf polygons are defined in JSON.  For each frame the system checks if a detection falls inside a polygon, updates an EMA of occupancy, and emits `shelf_event` records (pickup, return, uncertain).
6. **AI Copilot (RAG)** – Documents in `data/documents/` are loaded by `app/services/rag/document_loader.py`, chunked, embedded with `sentence‑transformers` (default `all‑mpnet‑base‑v2`), and stored in a `pgvector` column (`rag_chunk.embedding`).  Retrieval combines dense similarity and BM25 via Reciprocal Rank Fusion, feeds the top chunks to a Groq LLM (`groq_service.py`).  Guardrails in `security/input_guardrail.py` and `output_guardrail.py` strip prompts of injections and sanitise HTML.
7. **Persistence** – PostgreSQL with `pgvector` for embeddings, plus Redis for transient job state.  Alembic migrations (`alembic/versions/`) define the schema.
8. **CI/CD** – GitHub Actions (`.github/workflows/*.yml`) run lint, unit tests, Playwright UI tests, Docker build validation, and a security scan (Trivy).  No automatic deployment.
9. **MLOps** – The `mlops/` package implements dataset validation, training (`mlops/training/`), evaluation (`mlops/evaluation/`), and a simple JSON‑based model registry (`mlops/registry/`).  Promotion gates require a minimum mAP50‑95 of 0.35 and inference latency < 50 ms.

## Likely Viva Questions & Answers
| Question | Answer (with source reference) |
|----------|--------------------------------|
| **How does the system detect people?** | `app/services/cv_service.py::detect_image` loads `yolo11n.pt` and runs `model(img)`; the returned tensor is filtered for `class_id == 0` (COCO "person") and confidence ≥ 0.3. |
| **What ensures a visitor is counted only once across cameras?** | Raw detections → `track_id` (per‑camera) → `identity_service.assign_daily_visitor_id`.  Cross‑camera matching uses HSV histograms in `identity_service.match_across_cameras`. |
| **Is the shelf occupancy based on SKU recognition?** | No.  Shelf occupancy is computed by counting how many detections fall inside the shelf polygon (`shelf_service.process_shelf_frame`).  It does **not** identify individual SKUs. |
| **How are RAG results generated?** | `assistant_service.handle_query` → `rag_service.retrieve` (dense via `embedding_service`, sparse via BM25 in `rag_service`) → RRF fusion (`hybrid_retriever`) → Prompt built (`assistant_service.build_prompt`) → Groq LLM call (`groq_service.call_groq`). |
| **What happens if the Groq API key is missing?** | `groq_service.call_groq` catches `AuthenticationError` and falls back to a generic “Unable to answer” response; the frontend shows a friendly error. |
| **How is model promotion decided?** | `mlops/registry/promotion.py` checks `evaluation/metrics.json` for `mAP50_95 >= 0.35` and `latency_ms <= 50`.  If thresholds are met, the model file is copied to `mlops/registry/production/`. |
| **Are there any privacy concerns with Re‑ID?** | The Re‑ID uses only colour histograms, never facial features.  No personal data is stored; IDs are anonymous per‑day. |
| **Can the system run in real‑time?** | The current pipeline processes videos offline; frame‑rate is ~10 fps on a consumer GPU (see `mlops/evaluation/metrics.json`). |

---
*These notes are ready to be copied into a slide deck or spoken presentation.*