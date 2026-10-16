# Technical Implementation Plan: Question Paper Analysis & Next-Paper Preparation

**Branch**: `001-qpi-core-workflow` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/001-qpi-core-workflow/spec.md`  

---

## 1. Summary & Technical Approach

This plan defines the end-to-end technical implementation for the **Question Paper Intelligence (QPI)** platform. The system processes uploaded question paper drafts (PDF/DOCX), extracts discrete questions and sub-questions, computes hybrid semantic/lexical similarity against historical exam archives, analyzes syllabus unit representation and Bloom's difficulty balance, and synthesizes actionable recommendations to guide faculty in preparing their **NEXT** question paper.

### Architectural Core Philosophy:
* **Deterministic-First Architecture**: 100% of database operations, vector embeddings, similarity search math, unit representation percentages, question counts, difficulty stats, and RBAC rules are implemented using fast, deterministic Python, SQL, and `pgvector` code.
* **Targeted Google ADK Agents**: AI Agents are reserved strictly for unstructured reasoning tasks where LLMs genuinely add value: document layout parsing fallbacks, Bloom's Taxonomy cognitive depth classification, and synthesizing human-friendly narrative paper recommendations.
* **Stitch Visual Language Adaptation**: The frontend inherits the visual hierarchy, Oxford Blue palette (`#000a1e`), Inter typography, 1px low-contrast borders, Bento grid layouts, and split-pane document viewer from the Stitch design reference, while strictly adapting all copy to the exam question-paper domain.

---

## 2. Technical Context

* **Languages/Versions**: Python 3.12 (Backend & Agents), TypeScript 5.0+ / Next.js 15 (Frontend).
* **Primary Dependencies**: FastAPI, Celery, PyMuPDF (`fitz`), Tesseract OCR, `sentence-transformers` (`all-mpnet-base-v2`), `rank-bm25`, Next.js 15 App Router, Tailwind CSS, TanStack Query, Recharts, Google ADK SDK (`google-genai`).
* **Storage**: PostgreSQL 16 with `pgvector` extension (relational + 768d vector index), Redis 7 (task queue & cache), AWS S3 / MinIO (encrypted document storage).
* **Testing**: `pytest` (backend unit & contract tests), `jest` + React Testing Library (frontend UI tests).
* **Target Platform**: Dockerized container deployment on AWS EKS / ECS Fargate or self-hosted institution infrastructure.
* **Project Type**: Web Application (Next.js Frontend + FastAPI REST API + Async Celery Workers + ADK Agent Microservices).
* **Performance Goals**: $<90$ seconds end-to-end analysis processing time for a 50-question paper (p95); $<10$ms vector similarity lookup.
* **Constraints**: 25MB max upload file size; AES-256 field-level encryption; zero standing third-party access to question contents.

---

## 3. Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance Status | Justification / Implementation Evidence |
| :--- | :--- | :--- |
| **I. Formative Assessment & Next-Paper Intelligence** | **PASS** | Product positioning and insights screens focus entirely on unit coverage gaps, difficulty balance, and next-paper recommendations rather than plagiarism detection. |
| **II. Stitch Design Fidelity with QPI Adaptation** | **PASS** | UI specs inherit Oxford Blue palette (`#000a1e`), Inter typography, Bento grid layout, and split-pane document viewer from Stitch `DESIGN.md`, with 0% research/manuscript copy. |
| **III. Hybrid Similarity & Scalable Vector Search** | **PASS** | Combines 768d `sentence-transformers` vector cosine distance (`pgvector` HNSW index) and BM25 lexical keyword matching at atomic question level. |
| **IV. Deterministic-First Engineering & ADK Agents** | **PASS** | Math, SQL aggregations, similarity formulas, and vector queries are 100% deterministic code. ADK agents used only for layout fallback, Bloom's categorization, and advice synthesis. |
| **V. Strict Institutional Data Confidentiality** | **PASS** | Encrypted S3 storage, field-level AES-256 encryption, TLS 1.3, institutional SSO authentication, and append-only audit logging (`audit_logs` table). |

---

## 4. Architectural Deep-Dive (22 Required Sections)

### 4.1 System Architecture
```
[ Next.js 15 App Router Frontend (Tailwind + Recharts) ]
                         │  (TLS 1.3 / REST / JSON)
                         ▼
           [ FastAPI Backend API Gateway ]
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
[ Auth & RBAC ]  [ Postgres + pgvector ]  [ Celery Async Worker Queue ]
                         │                         │
                         ├─────────────────────────┼─────────────────────────┐
                         ▼                         ▼                         ▼
              [ Document Extraction ]     [ Hybrid Search Engine ]    [ Google ADK Agents ]
              (PyMuPDF / Tesseract)      (Sentence-Transformers     (Reasoning & Feedback)
                                          + pgvector HNSW + BM25)
```

### 4.2 Frontend Architecture & Route Structure
* **Framework**: Next.js 15 (App Router, TypeScript, React 19).
* **Routes**:
  * `/` -> Redirects to `/dashboard`
  * `/dashboard` -> Faculty Dashboard (KPI tiles, recent paper submissions table, quick upload drop zone).
  * `/upload` -> Paper Upload & Scan workspace (step-by-step metadata form, drop zone, processing progress polling).
  * `/reports/[id]` -> Originality & Match Report (radial score gauge, split-pane paper viewer with highlighted text spans, matched question list).
  * `/insights` -> QPI Preparation Insights (draft freshness score, unit/topic representation list, Bloom's difficulty breakdown, 5-year overused topic trend bar chart).
* **State Management**: TanStack Query (React Query v5) for async API caching & background refetching; Zustand for client-side viewer state.

### 4.3 Backend Architecture & API Boundaries
* **Framework**: FastAPI (Python 3.12, async endpoints).
* **API Versioning**: `/api/v1` prefix across all endpoints.
* **Core Endpoints**:
  * `POST /api/v1/papers/upload` -> Accepts PDF/DOCX + metadata; queues processing task.
  * `GET /api/v1/papers/{id}/status` -> Returns job state & progress percentage.
  * `GET /api/v1/reports/{id}` -> Returns Originality & Match Report payload.
  * `GET /api/v1/reports/{id}/insights` -> Returns Preparation Insights payload.
  * `POST /api/v1/papers/{id}/approve` -> Marks draft as approved for archive.
  * `GET /api/v1/reports/{id}/export-pdf` -> Streams signed PDF summary report.

### 4.4 PostgreSQL / pgvector Data Model
* Full relational schema defined in [data-model.md](./data-model.md).
* Tables: `users`, `departments`, `courses`, `syllabus_units`, `question_paper_drafts`, `questions`, `similarity_matches`, `qpi_reports`, `next_paper_recommendations`, `audit_logs`.
* Vector Index: `CREATE INDEX idx_questions_embedding_hnsw ON questions USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);`.

### 4.5 Document Extraction & Question Segmentation Pipeline
1. **PyMuPDF Extraction**: Extracts raw text blocks with font size, bold flags, and spatial bounding boxes $(x_0, y_0, x_1, y_1)$.
2. **Regex Layout Parser**: Identifies section headers (`Section A`, `Part I`), question numbers (`Q1.`, `1.`, `Question 4`), and sub-parts (`(a)`, `(b)`).
3. **Question Normalization**: Cleans whitespace, strips header/footer boilerplate, and builds atomic `Question` objects linked to parent papers.

### 4.6 OCR Fallback
* When native PDF text extraction yields $<50$ total characters (scanned PDF), the extraction pipeline triggers Tesseract OCR (`pytesseract`).
* Converts PDF pages to 300 DPI PNG images using `pdf2image`, applies grayscale thresholding, extracts text, and passes clean OCR output back to the question segmentation pipeline.

### 4.7 Question Embedding Pipeline
* **Model**: `sentence-transformers/all-mpnet-base-v2` (768-dimensional dense vectors).
* **Execution**: Executed in batch mode inside Celery workers using PyTorch CPU / ONNX Runtime.
* **Vector Persistence**: Embeddings are stored directly in the `questions.embedding` vector column in PostgreSQL.

### 4.8 Hybrid Semantic + BM25 Similarity Pipeline
* **Semantic Score**: Cosine distance computed via `pgvector`:
  $$\text{SemanticScore} = 1 - (\vec{v}_{draft} \cdot \vec{v}_{hist})$$
* **Lexical Score**: `rank-bm25` score normalized between $0.0$ and $1.0$.
* **Composite Score**:
  $$\text{CompositeScore} = 0.70 \cdot \text{SemanticScore} + 0.30 \cdot \text{LexicalScore}$$
* Matches categorized into `EXACT` ($\ge 0.90$), `PARAPHRASED` ($0.75 - 0.89$), and `CONCEPTUAL` ($0.60 - 0.74$).

### 4.9 Originality / Repetition Scoring Methodology
* **Question Repetition Index ($QR_i$)**: Assigned weight based on match tier ($1.0$ for Exact, $0.7$ for Paraphrase, $0.4$ for Conceptual).
* **Paper Originality Score**:
  $$\text{Paper Originality Score} = \max\left(0, 100\% - \sum_{i=1}^{N} \left( \frac{\text{Marks}_i}{\text{TotalMarks}} \times QR_i \times 100\% \right)\right)$$

### 4.10 Unit / Topic Analysis
* SQL queries compute actual marks allocated per syllabus unit versus target unit weightage:
  $$\text{UnitCoverage\%} = \frac{\sum \text{Marks of questions in Unit } U}{\text{Total Paper Marks}} \times 100\%$$
* Flags Overrepresented Units ($>35\%$) and Underrepresented Units ($<10\%$).

### 4.11 Question-Type & Bloom's Taxonomy Classification
* **Question Type**: Deterministically classified via mark allocation and prompt keywords (e.g., 1 mark = MCQ, "Calculate"/"Solve" = Numerical, "Derive"/"Prove" = Derivation).
* **Bloom's Taxonomy**: Classified by the ADK `ClassifierAgent` into Remember, Understand, Apply, Analyze, Evaluate, Create.

### 4.12 Google ADK Agent Boundaries & Responsibilities
* **`QuestionParserAgent`**: Invoked ONLY when regex/layout extraction fails on irregular multi-column PDF layouts.
* **`ClassifierAgent`**: Invoked to categorize question text into Bloom's Taxonomy cognitive levels and resolve ambiguous topic tags.
* **`RecommendationAgent`**: Invoked at the end of report generation to ingest structured diagnostic stats and synthesize 3–5 actionable recommendations for writing the NEXT paper.

### 4.13 Background Processing / Job Architecture
* **Task Queue**: Celery + Redis.
* **Job Workflow**: `Upload` -> `Queue` -> `Extract & OCR` -> `Embed Questions` -> `Vector Match` -> `Compute Analytics` -> `ADK Recommendations` -> `Report Complete`.
* **Status Polling**: Frontend polls `GET /api/v1/papers/{id}/status` every 2 seconds during processing.

### 4.14 Authentication / RBAC / Data Scoping
* **Auth Protocol**: JWT access tokens (15-min expiry) + HTTP-only refresh cookies.
* **RBAC Roles**:
  * `FACULTY`: Can upload and view own papers/reports only.
  * `DEPT_HEAD`: Can view department-wide paper submissions and aggregate analytics.
  * `ARCHIVAL_ADMIN`: Manages course archives and historical paper ingest.
  * `SYSTEM_ADMIN`: Manages user accounts and security audit logs.

### 4.15 File / Object Storage
* Raw uploaded files stored in S3/MinIO bucket `qpi-paper-uploads` with server-side AES-256 encryption (`SSE-S3`).
* Storage path: `s3://qpi-paper-uploads/{dept_code}/{course_code}/{academic_year}/{paper_id}.pdf`.

### 4.16 Report Generation
* **Live Report**: JSON payload served via API to Next.js frontend.
* **Signed PDF Export**: WeasyPrint / ReportLab generates a formal PDF summary report containing score gauges, topic charts, and signed approval metadata for university department records.

### 4.17 Frontend Integration with Stitch Design
* Tailored Tailwind config (`tailwind.config.ts`) importing Oxford Blue (`#000a1e`), Slate (`#505f76`), Off-White Slate (`#f7f9fb`), Emerald (`#009c6b`), and Rose (`#ba1a1a`).
* Recharts integration for circular score gauges, Bloom's difficulty radar charts, and 5-year overused topic bar charts.

### 4.18 Error Handling & Edge Cases
* **Corrupt / Encrypted PDFs**: Rejected at upload validation stage with HTTP 400.
* **OCR Failure**: Logged in audit trail; user alerted with manual text verification banner.
* **Celery Worker Timeout**: Tasks hard-killed after 180 seconds; status marked `FAILED` with retry option.

### 4.19 Testing Strategy
* **Unit Tests**: `pytest` for similarity algorithms, parsing regex, and scoring formulas ($>85\%$ line coverage).
* **Contract Tests**: OpenAPI schema validation for API endpoints.
* **UI Tests**: React Testing Library for score gauges, split-pane paper viewer, and upload progress components.

### 4.20 Local Development Environment
* Docker Compose (`docker-compose.yml`) running PostgreSQL 16 with `pgvector`, Redis 7, and MinIO.
* Backend run via Uvicorn (`uvicorn app.main:app --reload`).
* Frontend run via Next.js dev server (`npm run dev`).

### 4.21 Environment Variables & External Dependencies
* `DATABASE_URL`: `postgresql+asyncpg://qpi:secret@localhost:5432/qpi_db`
* `REDIS_URL`: `redis://localhost:6379/0`
* `S3_ENDPOINT_URL`: `http://localhost:9000`
* `GEMINI_API_KEY`: Google ADK Gemini API key (for Agent reasoning)
* `JWT_SECRET_KEY`: 256-bit secret key for token signing.

### 4.22 Deployment Considerations
* **Infrastructure as Code**: Terraform scripts provisioning EKS / ECS Fargate, AWS RDS PostgreSQL 16 (pgvector enabled), and S3 buckets.
* **CI/CD Pipeline**: GitHub Actions running SAST (Semgrep), unit tests, Docker build, container scanning (Trivy), and rolling deployment.

---

## 5. Project Structure Mappings

```text
question-paper-intelligence/
├── specs/001-qpi-core-workflow/
│   ├── spec.md                  # Feature Specification
│   ├── plan.md                  # Technical Implementation Plan (this file)
│   ├── research.md              # Phase 0 Research Artifact
│   ├── data-model.md            # Phase 1 Data Model Artifact
│   ├── quickstart.md            # Phase 1 Quickstart Artifact
│   ├── contracts/
│   │   └── api-spec.json        # Phase 1 OpenAPI Spec Artifact
│   └── checklists/
│       └── requirements.md      # Requirements Quality Checklist
│
├── frontend/                    # Next.js 15 App Router Frontend
│   ├── app/ (dashboard, upload, reports, insights)
│   ├── components/ (ui, layout, reports, insights)
│   └── lib/ (api client, utils)
│
├── backend/                     # FastAPI Backend & Extraction Engine
│   ├── app/ (api, core, db, services, tasks)
│   └── alembic/ (migrations)
│
└── agents/                      # Google ADK Agents
    ├── question_parser_agent/
    ├── classifier_agent/
    └── recommendation_agent/
```

---

## 6. Verification & Done When

- [x] Technical implementation plan written to `specs/001-qpi-core-workflow/plan.md`.
- [x] Phase 0 research artifact generated (`research.md`).
- [x] Phase 1 data model generated (`data-model.md`).
- [x] Phase 1 API contract generated (`contracts/api-spec.json`).
- [x] Phase 1 quickstart guide generated (`quickstart.md`).
- [x] All 22 required architectural sections detailed.
- [x] Constitution checks evaluated and passed.

> [!NOTE]
> No application code under `frontend/`, `backend/`, or `agents/` has been generated or modified. Ready for task breakdown (`/speckit-tasks`).
