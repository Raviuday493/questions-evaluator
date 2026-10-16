# Product Requirements Document: ScholarityPrep

**Faculty Question Paper Originality & Preparation Intelligence Platform**

| | |
|---|---|
| **Doc Owner** | Product/Engineering |
| **Status** | Draft v1.0 |
| **Last Updated** | September 2, 2026 |

---

## 1. Overview

ScholarityPrep is a web platform that helps faculty check the originality of a question paper **before** it is finalized and forwarded to the library/exam-cell for archival. Rather than being a punitive plagiarism-catcher, its core value is *formative*: it surfaces which questions overlap with prior years, flags conceptual gaps/overused topics, and gives faculty actionable insight to write a **better, more original next paper** — reducing repetition across academic years and improving question bank health over time.

## 2. Problem Statement

- Faculty repeatedly recycle questions across years, often unintentionally, because there's no easy way to check a new paper against the historical archive.
- Departments have no visibility into origination trends — which topics are over-tested, which are neglected.
- Manual cross-checking against years of archived papers is impractical at scale.
- There is no structured feedback loop from "paper submitted" to "paper improved next cycle."

## 3. Goals & Non-Goals

**Goals**
1. Let faculty upload a draft question paper and get an originality score against the historical archive.
2. Show exactly which questions matched, with source paper, year, and similarity %.
3. Give department-level dashboards (submission volume, avg originality %, flagged papers).
4. Generate forward-looking **Preparation Insights**: proposed draft freshness, conceptual gaps, overused topics trend (over N years) — to guide the *next* paper.
5. Preserve faculty authorship privacy and institutional data confidentiality end-to-end.

**Non-Goals (v1)**
- Not a public/student-facing plagiarism tool.
- Not a full LMS or exam-conduction system.
- Not intended to auto-reject papers — it informs human decision-making only.

## 4. Personas

- **Faculty (primary user)**: uploads paper, views originality report, adjusts before archival submission.
- **Department Head / Dean (dashboard viewer)**: monitors dept.-wide submission and originality trends.
- **Library/Archival Admin**: receives finalized papers, may view audit trail.
- **System Admin**: manages users, roles, retention, security policies.

## 5. Core Features (mapped to screens)

### 5.1 Upload & Analyze
- Drag-and-drop or file-picker upload (PDF/DOCX).
- Paper metadata form: academic year, department, subject, course code, primary examiner.
- Client-side file validation (type, size, malware pre-check) before submission.
- Real-time analysis status (queued → parsing → matching → scoring → complete).

### 5.2 Faculty Dashboard
- KPI tiles: total submissions, avg. originality %.
- Recent submissions table: title, subject, date, originality %, status badge.
- Quick access to drag-and-drop for new uploads.

### 5.3 Originality Report
- Overall originality score (radial gauge, e.g., 88%).
- Count of matched questions with severity breakdown.
- Side-by-side matched-question viewer: submitted question vs. archived source (paper, year, question number).
- Per-question similarity score and match type (exact / paraphrased / conceptual).
- Export report (PDF) for department records.

### 5.4 Preparation Insights (forward-looking, the differentiator)
- **Proposed Draft Freshness** score — how novel a next-cycle draft would be given topic history.
- **Conceptual Gaps** — topics/subtopics under-represented in past papers (opportunity areas).
- **Overused Topics (5-Year Trend)** — bar chart highlighting topics repeated too often (flagged bars in red), guiding faculty to diversify next year's paper.
- Suggested topic rebalancing recommendations.

## 6. Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | System shall accept PDF/DOCX uploads up to 25MB. |
| FR-2 | System shall extract and parse individual questions from unstructured paper layouts (OCR fallback for scanned PDFs). |
| FR-3 | System shall compute similarity against the full historical archive using semantic + lexical matching. |
| FR-4 | System shall generate an originality score (0–100%) per paper and per question. |
| FR-5 | System shall persist every submission, its report, and final faculty decision (approve/revise) in an immutable audit trail. |
| FR-6 | System shall generate topic-trend analytics scoped by department/subject/course over configurable year ranges. |
| FR-7 | System shall support RBAC: Faculty (own papers only), Dept Head (dept-wide read), Admin (full). |
| FR-8 | System shall notify faculty via email/in-app when analysis completes. |
| FR-9 | System shall allow export of the Originality Report as a signed PDF. |

## 7. Non-Functional Requirements

- **Availability:** 99.5% uptime for core upload/analysis path.
- **Performance:** Analysis of a 50-question paper completes in <90s (p95).
- **Scalability:** Support concurrent analysis jobs via async task queue; horizontally scalable workers.
- **Data Residency:** All archived papers and reports stored within institution-approved region (configurable, important for education-sector data governance).
- **Auditability:** Every access to a paper or report is logged (who, when, what).

---

## 8. Security Requirements (Highest Priority)

Given this system stores institutional exam question banks — a highly sensitive, integrity-critical asset — security is treated as a first-class requirement, not an add-on.

### 8.1 Identity & Access
- **SSO via institutional IdP** (SAML 2.0 / OIDC) — integrate with campus Google Workspace/Microsoft Entra ID.
- **MFA enforced** for all faculty/admin accounts (TOTP or platform authenticator/WebAuthn).
- **RBAC + ABAC hybrid**: role defines base permissions (Faculty/Dept Head/Admin), attribute checks scope data to own department/subject.
- Session management: short-lived JWT access tokens (~15 min) + rotating refresh tokens, device-bound where possible.

### 8.2 Data Protection
- **Encryption at rest:** AES-256 for all stored documents and DB fields (question text, metadata).
- **Encryption in transit:** TLS 1.3 everywhere; HSTS enforced.
- **Field-level encryption** for sensitive fields (examiner identity, unpublished question content) using envelope encryption via a KMS (AWS KMS / HashiCorp Vault).
- **Zero standing access:** engineers/admins cannot read raw question content without a logged, time-boxed break-glass approval.

### 8.3 Application Security
- OWASP ASVS Level 2 baseline compliance.
- Input validation and strict file-type/content sniffing (not just extension checks) on all uploads.
- Antivirus/malware scanning of every uploaded file (ClamAV or cloud-native scanning) before it enters the pipeline.
- Content Security Policy, strict CORS allow-list, secure cookie flags (HttpOnly, Secure, SameSite=Strict).
- Rate limiting and bot protection (Cloudflare / AWS WAF) on all public endpoints.
- Dependency scanning (Snyk/Dependabot) and container image scanning (Trivy) in CI.
- SAST (Semgrep/CodeQL) and DAST (OWASP ZAP) in the pipeline before each release.
- Secrets management via Vault/AWS Secrets Manager — no secrets in code or env files.

### 8.4 Infrastructure Security
- VPC isolation with private subnets for DB/workers; only API gateway exposed publicly.
- Web Application Firewall + DDoS protection at edge (Cloudflare).
- Immutable infrastructure via IaC (Terraform) with policy-as-code (OPA/Sentinel) to prevent misconfigurations.
- Network segmentation between analysis workers, DB, and object storage.
- Regular automated vulnerability scans and quarterly penetration testing.

### 8.5 Compliance & Governance
- Audit logging of every read/write/export action (immutable, append-only log store — e.g., write-once S3 + hash chaining).
- Data retention & right-to-erasure policies configurable per institution.
- Compliance alignment: relevant national data-protection law (e.g., India's DPDP Act 2023) and, if applicable, institutional education-records regulations (FERPA-equivalent).
- Regular third-party security audits and SOC 2 Type II readiness as the platform scales.

---

## 9. Proposed Tech Stack

### 9.1 Frontend
| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 15 (React 19, App Router)** | SSR/ISR for dashboards, great DX, aligns with your existing stack preference |
| Language | **TypeScript** | Type safety across a data-heavy UI |
| Styling | **Tailwind CSS + shadcn/ui** | Fast, consistent, accessible components; matches the clean dark-mode aesthetic in your mockups |
| Charts | **Recharts / D3** | Originality gauges, trend bar charts |
| State/Data | **TanStack Query** | Caching, background refetch for dashboard data |
| Forms | **React Hook Form + Zod** | Metadata form validation |
| File Upload | **Uppy** or native drag-and-drop + resumable upload (tus protocol) | Large PDF/DOCX uploads with resilience |
| Auth (client) | **NextAuth.js / Auth.js with OIDC provider** | SSO integration |

### 9.2 Backend
| Layer | Choice | Why |
|---|---|---|
| API Framework | **FastAPI (Python 3.12)** | Async, matches your preferred stack, great for ML-adjacent services |
| Task Queue | **Celery + Redis** (or **Dramatiq**) | Async paper parsing/matching pipeline |
| API Gateway | **Kong / AWS API Gateway** | Rate limiting, auth enforcement, routing |
| Auth Service | **Keycloak** (self-hosted IdP/broker) or Auth0/Entra ID | Central SSO, MFA, RBAC |
| Document Parsing | **PyMuPDF / pdfplumber**, **python-docx**, **Tesseract OCR** (scanned PDFs) | Extract raw + structured question text |
| NLP / Similarity Engine | **Sentence-Transformers (e.g., all-mpnet / multilingual-e5)** for semantic embeddings + **BM25/TF-IDF (rank-bm25)** for lexical matching, hybrid re-ranking | Detect exact, paraphrased, and conceptual overlap |
| Vector Search | **pgvector (Postgres extension)** or **Qdrant/Weaviate** | Store & query question embeddings against historical archive at scale |
| Primary Database | **PostgreSQL 16** | Relational data: users, papers, metadata, audit logs |
| Object Storage | **AWS S3 / MinIO (self-hosted)** with server-side encryption | Raw paper files |
| Cache | **Redis** | Session cache, job status, rate-limit counters |
| Search/Analytics | **OpenSearch** (optional) | Full-text search across archive for admin tooling |

### 9.3 ML/AI Pipeline
- Embedding generation microservice (FastAPI + sentence-transformers, GPU-optional, CPU-viable via ONNX runtime for cost efficiency).
- Hybrid scoring: cosine similarity (semantic) + Jaccard/BM25 (lexical) → weighted originality score.
- Topic modeling for "Conceptual Gaps"/"Overused Topics" — **BERTopic** or LDA over historical corpus, refreshed on a scheduled batch job.
- Model versioning via **MLflow**; reproducible pipelines via **DVC** for the question corpus.

### 9.4 Infrastructure & DevOps
| Layer | Choice |
|---|---|
| Cloud | AWS (or institution-approved sovereign cloud) |
| Containers | Docker, orchestrated via **Kubernetes (EKS)** or lighter **ECS Fargate** for a smaller launch |
| IaC | Terraform |
| CI/CD | GitHub Actions → build, test, SAST/DAST, deploy |
| Observability | **OpenTelemetry** + **Grafana/Loki/Tempo** (or Datadog) for logs, metrics, traces |
| Error Tracking | Sentry |
| Secrets | AWS Secrets Manager / HashiCorp Vault |
| CDN/Edge/WAF | Cloudflare |

### 9.5 Security Tooling Summary
- **SAST:** Semgrep / CodeQL
- **DAST:** OWASP ZAP
- **Dependency/Container scanning:** Snyk, Trivy
- **Secrets scanning:** Gitleaks
- **WAF/DDoS:** Cloudflare
- **KMS:** AWS KMS / Vault Transit
- **Malware scanning:** ClamAV
- **Pen testing:** Quarterly third-party engagement

---

## 10. High-Level Architecture

```
[Next.js Frontend] --TLS 1.3--> [API Gateway/WAF]
                                     |
                          [FastAPI Backend Services]
                          /        |         \
              [Auth: Keycloak]  [Celery Workers]  [Postgres + pgvector]
                                     |
                     [Parsing -> Embedding -> Matching Pipeline]
                                     |
                          [S3/MinIO Encrypted Storage]
                                     |
                        [Immutable Audit Log Store]
```

## 11. Data Model (Core Entities)

- **User** (id, role, department, institution_id, mfa_enabled)
- **Paper** (id, uploader_id, dept, subject, course_code, academic_year, file_ref, status)
- **Question** (id, paper_id, text, embedding_vector, topic_tags)
- **MatchResult** (id, question_id, matched_question_id, similarity_score, match_type)
- **OriginalityReport** (id, paper_id, overall_score, generated_at, pdf_export_ref)
- **PreparationInsight** (id, dept, subject, freshness_score, gaps[], overused_topics[], year_range)
- **AuditLog** (id, actor_id, action, resource_id, timestamp, ip_hash)

## 12. Success Metrics

- % reduction in repeated/near-duplicate questions year-over-year.
- Faculty adoption rate (papers submitted through platform vs. total papers set).
- Average time from upload to actionable report (<2 min target).
- Faculty satisfaction / report usefulness rating.
- Zero critical security incidents.

## 13. Rollout Plan (Suggested Phases)

1. **Phase 0 (4 wks):** Auth, upload pipeline, basic parsing, secure storage.
2. **Phase 1 (6 wks):** Similarity engine + Originality Report UI.
3. **Phase 2 (4 wks):** Faculty Dashboard, audit logging, RBAC hardening.
4. **Phase 3 (6 wks):** Preparation Insights (topic modeling, trend charts), PDF export.
5. **Phase 4 (ongoing):** Security hardening — pen test, SOC2 readiness, load testing.

## 14. Open Questions

- Which institutional IdP is available for SSO integration?
- Data residency constraints — self-hosted vs. cloud?
- Historical archive volume (paper count/years) to size the vector index and embedding infra?
- Is multi-institution/multi-tenant support needed, or single-campus deployment?

---

*End of PRD.*
