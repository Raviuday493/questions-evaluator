# Implementation Task Breakdown: Question Paper Analysis & Next-Paper Preparation

**Feature Branch**: `001-qpi-core-workflow`  
**Feature Directory**: `specs/001-qpi-core-workflow/`  
**Spec Reference**: [specs/001-qpi-core-workflow/spec.md](./spec.md)  
**Plan Reference**: [specs/001-qpi-core-workflow/plan.md](./plan.md)  

---

## Architectural Constraints & Implementation Rules

1. **Deterministic vs. Agent Separation**: Deterministic calculations (DB operations, vector cosine distance, BM25 scoring, repetition counts, percentages, syllabus weightage math, RBAC filters) MUST be implemented in pure Python/SQL (`backend/app/services/`). Google ADK Agents MUST be reserved strictly for unstructured LLM reasoning (layout extraction fallback, Bloom's Taxonomy categorization, advice synthesis).
2. **Configurable Similarity Thresholds**: Match boundaries (Exact $\ge 0.90$, Paraphrased $0.75-0.89$, Conceptual $0.60-0.74$) MUST be configurable via environment variables (`EXACT_MATCH_THRESHOLD`, `PARAPHRASE_MATCH_THRESHOLD`, `CONCEPTUAL_MATCH_THRESHOLD`) in `backend/app/core/config.py`.
3. **Pluggable Embedding Interface**: Embedding generation MUST be encapsulated behind an abstract interface (`BaseEmbeddingProvider` in `backend/app/services/embedding_provider.py`) to allow substituting `Sentence-Transformers` with other providers without changing application logic.
4. **Structured Agent I/O**: Google ADK agents MUST accept structured JSON inputs and return validated Pydantic schemas (`PydanticOutputParser`).
5. **Stitch Visual Fidelity**: All frontend UI components MUST consume tokens from Stitch `academic_precision/DESIGN.md` via Tailwind theme extension, while presenting 100% exam domain concepts.

---

## Phase 1: Setup & Shared Infrastructure

**Purpose**: Initialize project folder structures, configuration, and dependencies across frontend, backend, and agents.

- [x] T001 Initialize Next.js 15 frontend application structure in `frontend/` with TypeScript, Tailwind CSS, App Router, and TanStack Query.
- [x] T002 Configure Stitch design system tokens (Oxford Blue `#000a1e` palette, Inter typography, 1px borders) in `frontend/tailwind.config.ts`.
- [x] T003 [P] Initialize FastAPI backend project structure in `backend/` with Pydantic v2 settings, logging, and CORS middleware in `backend/app/main.py`.
- [x] T004 [P] Setup Celery task queue configuration and Redis connection in `backend/app/core/celery_app.py`.
- [x] T005 [P] Setup Google ADK Agent microservice structure in `agents/` with base settings in `agents/config.py`.
- [x] T006 [P] Create Docker Compose environment file (`docker-compose.yml`) for PostgreSQL 16 with `pgvector`, Redis 7, and MinIO object storage.
- [x] T007 Add environment variable schema and validation in `backend/app/core/config.py` (including configurable match thresholds).

---

## Phase 2: Foundational Prerequisites (Blocking Core Infrastructure)

**Purpose**: Implement database models, storage abstractions, and authentication infrastructure required before implementing user stories.

- [x] T008 Setup Alembic migration framework in `backend/alembic/` and create initial migrations for `users`, `departments`, `courses`, `syllabus_units`, `question_paper_drafts`, `questions`, `similarity_matches`, `qpi_reports`, `next_paper_recommendations`, and `audit_logs` tables per `specs/001-qpi-core-workflow/data-model.md`.
- [x] T009 [P] Create SQLAlchemy / SQLModel ORM entity classes in `backend/app/models/` matching the database schema.
- [x] T010 [P] Implement abstract file storage provider interface (`BaseStorageProvider`) and S3/MinIO implementation in `backend/app/services/storage_service.py`.
- [x] T011 [P] Implement abstract embedding provider interface (`BaseEmbeddingProvider`) and `SentenceTransformersProvider` in `backend/app/services/embedding_provider.py`.
- [x] T012 [P] Implement authentication and RBAC middleware (JWT verification, role scoping) in `backend/app/core/security.py`.
- [x] T013 [P] Implement audit logging service in `backend/app/services/audit_service.py` to record immutable access and modification records in `audit_logs`.
- [x] T014 Write unit tests for storage service and security middleware in `backend/tests/unit/test_security_and_storage.py`.
- [x] T015 Write unit tests for pluggable embedding provider interface in `backend/tests/unit/test_embedding_provider.py`.
- [x] T016 Create base frontend layout components (`SidebarNav`, `MobileHeader`, `MobileBottomNav`, `BentoGrid`) in `frontend/components/layout/` following Stitch specs.

---

## Phase 3: User Story 1 – Draft Question Paper Upload & Multi-Tier Analysis (Priority: P1 - MVP Vertical Slice)

**Goal**: Deliver a functional vertical slice allowing faculty to upload a PDF/DOCX paper, parse questions, generate embeddings, execute hybrid vector/lexical search against historical papers, and view processing progress.

**Independent Test**: Upload a 20-question PDF exam draft via `/upload`. Verification passes when questions are extracted, vector embeddings generated, hybrid similarity computed against past papers, and results persisted in PostgreSQL.

### Tests for User Story 1
- [x] T017 [P] [US1] Write unit tests for layout-aware PDF/DOCX question segmentation parser in `backend/tests/unit/test_document_parser.py`.
- [x] T018 [P] [US1] Write unit tests for hybrid vector/BM25 similarity engine in `backend/tests/unit/test_similarity_engine.py`.
- [x] T019 [P] [US1] Write API contract test for paper upload endpoint (`POST /api/v1/papers/upload`) in `backend/tests/contract/test_upload_api.py`.

### Implementation for User Story 1
- [x] T020 [P] [US1] Implement layout-aware document extraction service (`PyMuPDF` text/spatial block parser + regex question segmenter) in `backend/app/services/document_parser.py`.
- [x] T021 [P] [US1] Implement Tesseract OCR fallback service in `backend/app/services/ocr_service.py` triggered when PDF text yield is $<50$ characters.
- [x] T022 [US1] Implement ADK `QuestionParserAgent` in `agents/question_parser_agent/agent.py` as a fallback for complex multi-column layouts.
- [x] T023 [P] [US1] Implement hybrid similarity search service in `backend/app/services/similarity_engine.py` combining `pgvector` HNSW cosine distance and `rank-bm25` lexical scores using configurable thresholds from `config.py`.
- [x] T024 [US1] Implement Celery async processing pipeline (`process_paper_task`) in `backend/app/tasks/paper_tasks.py` orchestrating Extraction -> Embedding -> Vector Search -> Originality Scoring.
- [x] T025 [US1] Implement paper upload and status endpoints (`POST /api/v1/papers/upload`, `GET /api/v1/papers/{id}/status`) in `backend/app/api/v1/endpoints/papers.py`.
- [x] T026 [P] [US1] Create frontend file drop zone component (`DropZone`) with drag-and-drop & file validation in `frontend/components/upload/DropZone.tsx`.
- [x] T027 [P] [US1] Create paper metadata form component (`MetadataForm`) with Course Code, Term, and Exam Type selectors in `frontend/components/upload/MetadataForm.tsx`.
- [x] T028 [P] [US1] Create real-time processing progress panel component (`AnalysisProgress`) in `frontend/components/upload/AnalysisProgress.tsx`.
- [x] T029 [US1] Assemble full upload & scan page in `frontend/app/(dashboard)/upload/page.tsx` with step-by-step state management and API status polling.
- [x] T030 [US1] Run end-to-end MVP validation test confirming PDF upload to DB persistence.

---

## Phase 4: User Story 2 – Explainable Originality & Question Match Report (Priority: P2)

**Goal**: Render an explainable split-pane report displaying overall originality score, match summary cards, color-coded highlighted draft text spans, and side-by-side matched historical questions.

**Independent Test**: Navigate to `/reports/[id]`. Verification passes when clicking a matched question card auto-scrolls the right-pane paper viewer to the corresponding highlighted text span (Red for Exact, Amber for Conceptual).

### Tests for User Story 2
- [ ] T031 [P] [US2] Write unit test for paper originality weighted scoring formula in `backend/tests/unit/test_originality_calculator.py`.
- [ ] T032 [P] [US2] Write API contract test for report endpoint (`GET /api/v1/reports/{id}`) in `backend/tests/contract/test_report_api.py`.
- [ ] T033 [P] [US2] Write UI component test for split-pane document viewer in `frontend/tests/components/test_digital_paper_viewer.test.tsx`.

### Implementation for User Story 2
- [ ] T034 [P] [US2] Implement deterministic originality score calculator in `backend/app/services/originality_calculator.py` computing weighted paper originality (0–100%).
- [ ] T035 [US2] Implement report data builder service in `backend/app/services/report_service.py` fetching matched questions, source paper provenance, and span highlights.
- [ ] T036 [US2] Implement report API endpoint (`GET /api/v1/reports/{id}`) in `backend/app/api/v1/endpoints/reports.py`.
- [ ] T037 [P] [US2] Create radial score gauge component (`RadialScoreGauge`) using SVG circular progress ring in `frontend/components/reports/RadialScoreGauge.tsx`.
- [ ] T038 [P] [US2] Create match summary cards component (`MatchSummaryCards`) for severity index and scan details in `frontend/components/reports/MatchSummaryCards.tsx`.
- [ ] T039 [P] [US2] Create matched question list item component (`MatchedQuestionCard`) with match % badges in `frontend/components/reports/MatchedQuestionCard.tsx`.
- [ ] T040 [P] [US2] Create interactive digital paper viewer component (`DigitalPaperViewer`) with color-coded text highlights and zoom toolbar in `frontend/components/reports/DigitalPaperViewer.tsx`.
- [ ] T041 [US2] Assemble split-pane Originality & Match Report page in `frontend/app/(dashboard)/reports/[id]/page.tsx`.
- [ ] T042 [P] [US2] Implement Faculty Dashboard page in `frontend/app/(dashboard)/dashboard/page.tsx` rendering KPI tiles, recent submissions table, and quick upload CTA.
- [ ] T043 [US2] Verify end-to-end interactive reporting experience from dashboard click to split-pane highlight navigation.

---

## Phase 5: User Story 3 – QPI Preparation Insights & Syllabus Balance Analysis (Priority: P3)

**Goal**: Compute and display Unit/Topic representation percentages, Bloom's Taxonomy cognitive depth breakdown, question-type distribution, and 5-year overused topic trend charts.

**Independent Test**: View `/insights` for a course. Verification passes when unit weightage imbalances (over/underrepresented), Bloom's Taxonomy breakdown, and saturated topic warnings are displayed correctly.

### Tests for User Story 3
- [ ] T044 [P] [US3] Write unit test for deterministic unit representation & topic frequency aggregator in `backend/tests/unit/test_analytics_service.py`.
- [ ] T045 [P] [US3] Write unit test for ADK `ClassifierAgent` structured output parsing in `agents/tests/test_classifier_agent.py`.
- [ ] T046 [P] [US3] Write API contract test for insights endpoint (`GET /api/v1/reports/{id}/insights`) in `backend/tests/contract/test_insights_api.py`.

### Implementation for User Story 3
- [ ] T047 [P] [US3] Implement deterministic analytics service in `backend/app/services/analytics_service.py` calculating Unit Coverage %, question-type breakdown, and 5-year historical topic frequencies.
- [ ] T048 [US3] Implement ADK `ClassifierAgent` in `agents/classifier_agent/agent.py` to categorize question text into Bloom's Taxonomy cognitive levels (Remember → Create) with structured JSON output.
- [ ] T049 [US3] Implement Preparation Insights API endpoint (`GET /api/v1/reports/{id}/insights`) in `backend/app/api/v1/endpoints/insights.py`.
- [ ] T050 [P] [US3] Create Proposed Draft Freshness score card component (`FreshnessGaugeCard`) in `frontend/components/insights/FreshnessGaugeCard.tsx`.
- [ ] T051 [P] [US3] Create Conceptual/Unit Gap list component (`ConceptualGapList`) in `frontend/components/insights/ConceptualGapList.tsx`.
- [ ] T052 [P] [US3] Create 5-Year Overused Topic Trend bar chart component (`TopicTrendBarChart`) using Recharts with saturation alert tooltips in `frontend/components/insights/TopicTrendBarChart.tsx`.
- [ ] T053 [P] [US3] Create Bloom's Taxonomy Cognitive Depth breakdown chart (`BloomsDistributionChart`) in `frontend/components/insights/BloomsDistributionChart.tsx`.
- [ ] T054 [P] [US3] Create Question Format Breakdown card (`QuestionTypeChart`) in `frontend/components/insights/QuestionTypeChart.tsx`.
- [ ] T055 [US3] Assemble full QPI Preparation Insights page in `frontend/app/(dashboard)/insights/page.tsx`.
- [ ] T056 [US3] Verify insights calculation accuracy against test syllabus weightage data.

---

## Phase 6: User Story 4 – Actionable Next-Paper Recommendations & Iterative Re-Analysis (Priority: P4)

**Goal**: Synthesize prioritized actionable recommendations for writing the NEXT paper draft, enable draft re-upload for delta analysis, support paper approval for archival, and generate exportable PDF reports.

**Independent Test**: Review recommendations, upload an updated draft paper, observe updated originality score (e.g. from 72% to 91%), and export signed PDF report.

### Tests for User Story 4
- [ ] T057 [P] [US4] Write unit test for ADK `RecommendationAgent` advice generation in `agents/tests/test_recommendation_agent.py`.
- [ ] T058 [P] [US4] Write API contract test for paper approval and PDF export endpoints in `backend/tests/contract/test_approval_pdf_api.py`.

### Implementation for User Story 4
- [ ] T059 [US4] Implement ADK `RecommendationAgent` in `agents/recommendation_agent/agent.py` consuming structured diagnostic metrics and producing 3–5 prioritized next-paper recommendations.
- [ ] T060 [P] [US4] Implement PDF report generator service in `backend/app/services/pdf_export_service.py` rendering signed QPI Summary Reports.
- [ ] T061 [US4] Implement paper approval and PDF export endpoints (`POST /api/v1/papers/{id}/approve`, `GET /api/v1/reports/{id}/export-pdf`) in `backend/app/api/v1/endpoints/reports.py`.
- [ ] T062 [P] [US4] Create Next-Paper Recommendation panel component (`RecommendationPanel`) in `frontend/components/insights/RecommendationPanel.tsx`.
- [ ] T063 [P] [US4] Create paper approval dialog component (`ApprovePaperModal`) with digital signature trigger in `frontend/components/reports/ApprovePaperModal.tsx`.
- [ ] T064 [US4] Integrate recommendation cards into `/insights` and `/reports/[id]` views.
- [ ] T065 [US4] Implement iterative re-analysis flow linking updated draft uploads to previous audit records.
- [ ] T066 [US4] Connect "Approve for Archive" and "Download PDF Report" actions in `frontend/app/(dashboard)/reports/[id]/page.tsx`.
- [ ] T067 [US4] Verify end-to-end feedback loop: Flagged Paper -> Recommendation -> Revised Draft -> Higher Score -> Approved Archive.
- [ ] T068 [US4] Execute quickstart validation suite (`quickstart.md`).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Security hardening, performance tuning, documentation, and final validation.

- [ ] T069 [P] Perform security hardening: audit field-level encryption, verify CORS/CSP headers, and enforce rate-limiting middleware in `backend/app/main.py`.
- [ ] T070 [P] Optimize database query performance: verify HNSW index execution plans and add composite indexes on `(course_id, academic_year)` in `backend/app/models/`.
- [ ] T071 [P] Verify 100% adherence of frontend components to Stitch design tokens (`academic_precision/DESIGN.md`) and confirm zero manuscript/research copy leakage.
- [ ] T072 [P] Update API documentation and OpenAPI schemas in `backend/docs/`.
- [ ] T073 Perform end-to-end load testing confirming $<90$s processing latency under 50 concurrent paper uploads.
- [ ] T074 Execute full test suite (`pytest` + React Testing Library) confirming $>85\%$ backend test coverage and zero regression failures.
- [ ] T075 Final validation against project constitution (`.specify/memory/constitution.md`).

---

## Dependencies & Execution Order

```
Phase 1: Setup (T001 - T007)
   │
   ▼
Phase 2: Foundational Prerequisites (T008 - T016)  <-- BLOCKS ALL USER STORIES
   │
   ├───────────────────────────────┬───────────────────────────────┐
   ▼                               ▼                               ▼
Phase 3: User Story 1 (MVP)    Phase 4: User Story 2           Phase 5: User Story 3
(T017 - T030)                  (T031 - T043)                   (T044 - T056)
   │                               │                               │
   └───────────────────────────────┼───────────────────────────────┘
                                   ▼
                       Phase 6: User Story 4 (T057 - T068)
                                   │
                                   ▼
                       Phase 7: Polish (T069 - T075)
```

---

## Parallel Opportunities

- **Phase 1 (Setup)**: T003, T004, T005, T006 can run concurrently.
- **Phase 2 (Foundational)**: T009, T010, T011, T012, T013 can run concurrently.
- **Phase 3 (User Story 1)**: T017, T018, T019 (tests) in parallel; T020, T021, T023 (services) in parallel; T026, T027, T028 (UI components) in parallel.
- **Phase 4 (User Story 2)**: T031, T032, T033 (tests) in parallel; T037, T038, T039, T040 (UI components) in parallel.
- **Phase 5 (User Story 3)**: T044, T045, T046 (tests) in parallel; T050, T051, T052, T053, T054 (UI components) in parallel.
- **Phase 6 (User Story 4)**: T057, T058 (tests) in parallel; T060, T062, T063 (components/services) in parallel.

---

## Completion & Execution Summary

* **Total Task Count**: 75 tasks
* **Setup Phase**: 7 tasks (T001 - T007)
* **Foundational Phase**: 9 tasks (T008 - T016)
* **User Story 1 (P1 - MVP)**: 14 tasks (T017 - T030)
* **User Story 2 (P2)**: 13 tasks (T031 - T043)
* **User Story 3 (P3)**: 13 tasks (T044 - T056)
* **User Story 4 (P4)**: 12 tasks (T057 - T068)
* **Polish Phase**: 7 tasks (T069 - T075)
* **Parallel Opportunities**: 42 tasks marked `[P]`
* **Suggested MVP Scope**: Phase 1 + Phase 2 + Phase 3 (User Story 1)

> [!NOTE]
> No application code was written. Tasks are ready for step-by-step execution (`/speckit-implement`).
