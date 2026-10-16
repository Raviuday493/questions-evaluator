# Feature Specification: Question Paper Analysis & Next-Paper Preparation

**Feature Branch**: `001-qpi-core-workflow`  
**Created**: 2026-09-02  
**Status**: Draft  
**Input**: User description: "Create the initial product specification for the core QPI workflow: Question Paper Analysis & Next-Paper Preparation"

---

## 1. Executive Summary & Product Positioning

The Question Paper Intelligence (QPI) platform is a **formative decision-support and next-paper preparation tool** for university faculty. Its primary value is helping faculty construct balanced, high-quality, and non-repetitive **NEXT** question papers by analyzing draft papers against historical course question archives.

### Key Positioning Rules:
1. **Formative vs. Punitive**: QPI is NOT a plagiarism detector or punitive library scanner; it is a formative assistant guiding continuous improvement of assessment quality.
2. **Next-Paper Focus**: Insights focus on actionable changes for the upcoming exam cycle (identifying over-tested units, under-tested topics, Bloom's difficulty imbalances, and recycled questions).
3. **Stitch Visual Fidelity with Domain Adaptation**: The user interface inherits the visual hierarchy, Oxford Blue palette (`#000a1e`), Inter typography, 1px low-contrast borders, Bento grid layouts, and split-pane document viewer from the Stitch design reference. All manuscript/research terminology (e.g., "abstract", "literature gap", "publication potential", "student author") is strictly replaced with exam domain concepts (Examiner, Course Code, Semester, Unit Representation, Bloom's Taxonomy Balance).

---

## 2. User Scenarios & Testing *(mandatory)*

### User Story 1 – Draft Question Paper Upload & Multi-Tier Analysis (Priority: P1)
As a faculty member preparing a midterm or final exam, I want to upload my draft question paper (PDF or DOCX) with course metadata so that the system extracts questions and computes overlap against authorized past exam papers.

**Why this priority**: Core entry point for the QPI platform. Without file upload and question parsing, no analysis or insights are possible.

**Independent Test**: Upload a 20-question Physics exam draft in PDF format with Course Code `PHY-201`. The system parses 20 questions, completes hybrid vector/lexical matching against `PHY-201` historical archives, and displays a paper-level originality score and question match breakdown within 90 seconds.

**Acceptance Scenarios**:
1. **Given** a faculty user on the `/upload` workspace, **When** they drag and drop a valid PDF/DOCX file up to 25MB and select Course Code, Academic Year, Term, and Exam Type, **Then** the file is validated and queued for extraction.
2. **Given** a queued question paper file, **When** extraction begins, **Then** the system parses sections, main questions (Q1, Q2...), sub-questions (1a, 1b...), and text content, showing step-by-step progress ("Parsing layout" → "Generating vector embeddings" → "Scanning historical archive").
3. **Given** a scanned PDF with non-searchable text, **When** standard text extraction yields empty tokens, **Then** the system automatically applies OCR fallback to extract question text cleanly.

---

### User Story 2 – Explainable Originality & Question Match Report (Priority: P2)
As a faculty member, I want an explainable split-pane report showing exact, paraphrased, and conceptual matches between my draft questions and historical papers so that I can inspect repeated content in context.

**Why this priority**: Enables transparency and trust. Faculty must see *why* a question was flagged as repeated and compare it side-by-side with historical source papers.

**Independent Test**: Navigate to `/reports/[id]`. Click on Question 4 (flagged with 95% match). The right-hand digital paper viewer scrolls to Question 4 and highlights matched text in red/amber, while the left pane displays the matched 2021 Final Exam Question 2 snippet.

**Acceptance Scenarios**:
1. **Given** a completed paper analysis, **When** the faculty user views `/reports/[id]`, **Then** the screen renders an overall Paper Originality Score radial gauge (0–100%), total question match count, scan metadata (database searched, execution time), and severity breakdown.
2. **Given** the split-pane report view, **When** a user selects a matched question card from the left panel, **Then** the right panel digital paper viewer highlights the corresponding text in the draft paper with color-coded severity indicators (Red for >85% Exact/Paraphrase Match, Amber for 60–84% Conceptual Match).
3. **Given** a matched question, **When** inspecting details, **Then** the system displays the source paper metadata (Course Name, Academic Year, Term, Question Number, and Match Type: Exact, Paraphrased, or Conceptual).

---

### User Story 3 – QPI Preparation Insights & Syllabus Balance Analysis (Priority: P3)
As a faculty member, I want to view Unit/Topic representation, Bloom's Taxonomy difficulty distribution, and question-type breakdown so that I can identify overrepresented and underrepresented areas in my draft.

**Why this priority**: Delivers the core "Intelligence" value of QPI, empowering faculty to evaluate question paper quality beyond raw repetition.

**Independent Test**: View `/insights` for Course `CS-101`. The system displays a 5-Year Topic Frequency Bar Chart highlighting overused topics in red, a Conceptual/Unit Gap List showing un-tested syllabus modules, a Bloom's Taxonomy Radar/Pie Chart (Remember, Understand, Apply, Analyze, Evaluate, Create), and a Question Type Breakdown (MCQ, Short Answer, Long Essay, Numerical).

**Acceptance Scenarios**:
1. **Given** a draft question paper analysis, **When** viewing the Preparation Insights tab, **Then** the system computes and displays Unit/Topic Coverage % relative to syllabus weightage, identifying overrepresented units (>35% weightage) and underrepresented units (<10% weightage).
2. **Given** the difficulty distribution view, **When** analyzing questions, **Then** the system classifies each question into Bloom's Taxonomy levels and highlights skews (e.g., "70% Remember/Understand, only 10% Apply/Analyze").
3. **Given** topic history over the past 5 academic years, **When** viewing the 5-Year Overused Topic Chart, **Then** topics exceeding historical frequency thresholds are visually flagged with saturation alerts ("Warning: Saturated topic in 4 of last 5 terms").

---

### User Story 4 – Actionable Next-Paper Recommendations & Iterative Re-Analysis (Priority: P4)
As a faculty member preparing my final question paper draft, I want concrete recommendations on how to replace repeated questions and rebalance units, so that I can edit my draft and re-analyze it until it meets quality goals.

**Why this priority**: Closes the formative feedback loop, guiding faculty from "diagnostic insights" to "actionable next-paper construction".

**Independent Test**: Receive recommendation "Replace Q4 (95% match with 2021) with an Application-level question from Unit 3 (Quantum Fluid Dynamics)". Edit paper draft, click "Re-Analyze Draft", and observe updated originality score (e.g., from 72% to 91%) and refreshed insights.

**Acceptance Scenarios**:
1. **Given** an analysis report with flagged repetitions or unit imbalances, **When** the faculty user views the Recommendation Panel, **Then** the system presents 3–5 prioritize actionable suggestions (e.g., "Swap Q4 with Unit 3 topic", "Add 2 Higher-Order Thinking questions to Section B").
2. **Given** a faculty member who edits their draft paper based on recommendations, **When** they re-upload or submit the revised draft for re-analysis, **Then** the system executes a delta analysis, links the new analysis to the previous iteration in the audit trail, and updates the proposed draft freshness score.
3. **Given** a finalized paper draft meeting department quality criteria, **When** the faculty user clicks "Approve Paper for Exam Archive", **Then** the paper status updates to Approved, an audit record is logged, and a signed PDF QPI Summary Report is generated for department records.

---

## 3. Edge Cases & Boundary Conditions

- **EC-001 (Unstructured / Multi-Column Layouts)**: How does the system handle complex multi-column question papers with inline diagrams or mathematical formulas?  
  *Behavior*: The layout parser extracts text blocks sequentially using bounding-box spatial ordering. Mathematical expressions are preserved as plain text/LaTeX strings. If regex layout parsing fails, the system triggers the fallback Document Parsing Agent.
- **EC-002 (Sub-Question Granularity)**: How does the system handle nested sub-parts (e.g., Q1(a)(i), Q1(a)(ii))?  
  *Behavior*: Sub-questions are extracted as discrete sub-entities linked to parent Question 1. Similarity matching is performed at both the parent question level and individual sub-question level.
- **EC-003 (Empty Historical Archive)**: What happens if a newly introduced course has no historical exam papers in the archive?  
  *Behavior*: The system displays an Originality Score of 100% with a notification ("First paper for course CS-305. Originality score computed against department-wide question bank"). Unit coverage and Bloom's difficulty analysis function normally based on course syllabus metadata.
- **EC-004 (Corrupted or Password-Protected Files)**: How does the system handle unreadable files?  
  *Behavior*: The upload scanner rejects password-protected or corrupt files immediately during client-side validation with a user-friendly error message ("File is encrypted or unreadable. Please upload an unprotected PDF/DOCX").
- **EC-005 (Scanned PDF Low Resolution)**: What happens if OCR text extraction confidence is below 60%?  
  *Behavior*: The system flags the document with a warning badge ("Low OCR confidence detected. Please verify extracted question text in the preview pane before finalizing analysis").

---

## 4. Requirements *(mandatory)*

### Functional Requirements

#### Document Upload & Question Processing
- **FR-001**: System MUST accept PDF and DOCX file uploads up to 25MB.
- **FR-002**: System MUST validate file integrity, virus status, and MIME type before processing.
- **FR-003**: System MUST extract course metadata (Course Code, Subject Name, Department, Academic Year, Semester/Term, Exam Type, Total Marks, Primary Examiner).
- **FR-004**: System MUST parse raw paper text into discrete, ordered `Question` and `SubQuestion` entities, preserving question numbering, marks allocation, and section headers.
- **FR-005**: System MUST invoke automatic Tesseract OCR fallback when native PDF text extraction yields fewer than 50 text characters.

#### Historical Search & Similarity Matching
- **FR-006**: System MUST scope similarity searches to authorized historical question papers based on Department, Course Code, and configurable year ranges (default: past 5–10 years).
- **FR-007**: System MUST generate 768-dimensional dense vector embeddings for every extracted question.
- **FR-008**: System MUST perform hybrid similarity search combining semantic vector cosine distance (`pgvector`) and lexical keyword matching (`BM25`).
- **FR-009**: System MUST classify similarity matches into three explicit tiers:
  - **Exact Match**: $\ge 90\%$ combined similarity (verbatim or near-verbatim duplicate).
  - **Paraphrased Match**: $75\% - 89\%$ combined similarity (same core prompt with rephrased wording or numerical value swaps).
  - **Conceptual Match**: $60\% - 74\%$ combined similarity (shared underlying concept, topic, or sub-theorem).
- **FR-010**: System MUST compute a paper-level **Originality Score** (0–100%) calculated as the inverse weighted average of question-level match severities:
  $$\text{Paper Originality Score} = 100\% - \sum_{i=1}^{N} \left( w_i \times \text{MatchSeverity}_i \right)$$

#### QPI Preparation Insights & Analytics
- **FR-011**: System MUST classify each extracted question into a Unit/Module of the course syllabus and tag specific sub-topics.
- **FR-012**: System MUST analyze Unit/Topic representation and flag:
  - **Overrepresented Units**: Units accounting for $>35\%$ of total paper marks.
  - **Underrepresented Units / Conceptual Gaps**: Syllabus units accounting for $<10\%$ of marks or un-tested over past 3 exam cycles.
- **FR-013**: System MUST classify each question into a Bloom's Taxonomy cognitive level (Remember, Understand, Apply, Analyze, Evaluate, Create).
- **FR-014**: System MUST compute and visualize the difficulty distribution breakdown (Cognitive Depth Index).
- **FR-015**: System MUST categorize questions by structural format (Multiple Choice, Short Answer, Long Essay, Derivation/Proof, Numerical Problem).
- **FR-016**: System MUST track 5-year historical topic usage frequency and highlight saturated topics in the topic trend chart.

#### Explainable Report & Split-Pane Viewer
- **FR-017**: System MUST render an explainable Originality & Match Report incorporating Stitch design tokens (Oxford Blue `#000a1e` headers, Inter font, Bento grid cards, score gauge).
- **FR-018**: System MUST provide an interactive split-pane document viewer displaying the draft paper on the right with highlighted matching text spans and matched historical questions on the left.
- **FR-019**: System MUST color-code highlighted text spans in the draft paper based on match severity (Red for Exact/Paraphrase Match, Amber for Conceptual Match).
- **FR-020**: System MUST display source paper provenance for every matched question (Historical Paper Title, Academic Year, Term, Question Number, Course Code).

#### Actionable Recommendations & Workflow Iteration
- **FR-021**: System MUST generate 3–5 prioritized, human-readable recommendations for improving the NEXT question paper draft (e.g., "Replace Q4 to reduce 2021 overlap; add 1 Application-level question in Unit 3").
- **FR-022**: System MUST support iterative draft re-analysis, linking revised paper uploads to prior submission iterations in an audit history chain.
- **FR-023**: System MUST allow faculty to mark a paper draft as "Approved for Exam Archive" and export a signed PDF QPI Report.
- **FR-024**: System MUST enforce strict Role-Based Access Control (RBAC): Faculty access own papers only; Department Heads access department aggregate insights; Admins manage system settings.
- **FR-025**: System MUST log all document upload, analysis, view, edit, and export events in an immutable append-only audit trail.

---

## 5. Non-Functional Requirements

- **NFR-001 (Performance & Latency)**: Complete end-to-end processing (upload → question parsing → embedding generation → hybrid similarity search → insights computation) MUST finish in $<90$ seconds for a 50-question paper (p95).
- **NFR-002 (Accuracy & Recall)**: Question segmentation accuracy MUST achieve $\ge 95\%$ on standard exam PDF layouts. Similarity engine recall for exact/paraphrased question duplicates MUST exceed $92\%$.
- **NFR-003 (Security & Encryption)**: All stored question paper files and database text fields MUST be encrypted at rest using AES-256. All network traffic MUST use TLS 1.3.
- **NFR-004 (Availability & Resilience)**: Analysis service MUST maintain $99.5\%$ uptime during peak exam preparation windows. Worker queues MUST support horizontal auto-scaling under high upload volume.
- **NFR-005 (Data Governance)**: Question bank data MUST remain strictly within institution-designated storage boundaries with zero standing third-party access.

---

## 6. System Inputs & Outputs

```
+-----------------------------------------------------------------------+
| SYSTEM INPUTS                                                         |
| 1. Draft Question Paper File (PDF/DOCX, max 25MB)                    |
| 2. Paper Metadata: Course Code, Department, Year, Term, Exam Type    |
| 3. Historical Exam Paper Archive (Authorized DB records)             |
| 4. Course Syllabus Structure & Topic Map                             |
+-----------------------------------------------------------------------+
                                   │
                                   ▼
+-----------------------------------------------------------------------+
| QUESTION PAPER INTELLIGENCE (QPI) ENGINE                              |
| - Document Text & Layout Extraction (PyMuPDF / Tesseract OCR)         |
| - Question Segmentation & Sub-part Parsing                            |
| - Dense Embedding Generation (Sentence-Transformers 768d)             |
| - Hybrid Similarity Match Engine (pgvector HNSW + BM25 Lexical)       |
| - Deterministic Unit Coverage & Bloom's Taxonomy Aggregator           |
| - ADK Agent Reasoning (Topic Classification & Next-Paper Feedback)    |
+-----------------------------------------------------------------------+
                                   │
                                   ▼
+-----------------------------------------------------------------------+
| SYSTEM OUTPUTS                                                        |
| 1. Overall Paper Originality Score Radial Gauge (0-100%)              |
| 2. Interactive Split-Pane Match Viewer with Highlighted Spans         |
| 3. Question Repetition List with Source Paper Provenance              |
| 4. Unit/Topic Representation & Conceptual Gap Analysis                |
| 5. Bloom's Taxonomy & Difficulty Distribution Charts                  |
| 6. 5-Year Overused Topic Saturation Bar Chart                         |
| 7. Actionable Next-Question-Paper Improvement Recommendations         |
| 8. Signed Exportable PDF QPI Summary Report                           |
+-----------------------------------------------------------------------+
```

---

## 7. Key Entities *(include if feature involves data)*

- **FacultyUser**: Represents the faculty member / primary examiner (ID, Name, Email, Department, Role: Faculty/DeptHead/Admin).
- **Course**: Represents an academic course (Course Code, Title, Department, Syllabus Unit Map).
- **QuestionPaperDraft**: Represents an uploaded draft question paper (ID, Course ID, Academic Year, Term, Exam Type, Total Marks, File Reference, UploadedAt, Status: Queued/Analyzing/Completed/Approved).
- **Question**: Represents an extracted individual question or sub-question (ID, Paper ID, Section, Question Number, SubPart Identifier, Raw Text, Clean Text, Marks Allocation, Vector Embedding, Unit Tag, Topic Tag, Question Type, Bloom's Taxonomy Level).
- **SimilarityMatch**: Represents a detected match between a draft question and a historical question (ID, Draft Question ID, Historical Question ID, Historical Paper Metadata, Semantic Score, Lexical Score, Composite Score, Match Tier: Exact/Paraphrase/Conceptual).
- **QPIReport**: Represents the generated analysis report (ID, Paper ID, Originality Score, Total Questions, Matched Questions Count, Unit Coverage Map, Bloom's Distribution Map, GeneratedAt, PDF Export Ref).
- **NextPaperRecommendation**: Represents an actionable advice item generated for the NEXT paper (ID, Report ID, Recommendation Type, Severity, Action Text, Target Question ID).
- **AuditRecord**: Represents an append-only security log entry (ID, Actor ID, Action, Resource ID, Timestamp, IP Hash).

---

## 8. Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Faculty can upload a draft question paper and view a complete analysis report in under 90 seconds.
- **SC-002**: Question extraction parser correctly segments questions and sub-parts with $\ge 95\%$ accuracy on standard test papers.
- **SC-003**: 100% of UI screens adhere to the Stitch design system (Oxford Blue palette `#000a1e`, Inter typography, Bento grid layout, split-pane paper viewer).
- **SC-004**: 0% confusing or unadapted research/manuscript terminology (e.g. "student author", "literature gaps", "publication potential") appears in user-facing UI copy.
- **SC-005**: 85% or higher of surveyed faculty report that QPI recommendations helped them write a more balanced, less repetitive NEXT question paper.
- **SC-006**: System successfully processes concurrent analysis jobs for up to 50 faculty members simultaneously without processing failure or timeout.
- **SC-007**: 100% of paper uploads, report accesses, and paper approvals are logged in the immutable security audit store.

---

## 9. Assumptions

- **A-001**: Faculty users have access to stable web browsers (Chrome, Edge, Firefox, Safari) and standard broadband internet connectivity.
- **A-002**: Historical question papers for the course (past 3–10 years) have been digitized and ingested into the course question archive database.
- **A-003**: Course syllabi are structured into identifiable Units/Modules with topic keyword lists.
- **A-004**: Standard exam papers follow structured numbering conventions (e.g., Q1, Q2, Section A/B, sub-parts 1a, 1b).
- **A-005**: Authentication integration uses standard institutional Single Sign-On (OIDC / SAML 2.0).
