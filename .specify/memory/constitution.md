<!--
Sync Impact Report:
- Version change: Uninitialized -> 1.0.0
- Added sections: Core Principles (5 Principles), Governance & Compliance
- Added principles:
  1. Formative Assessment & Next-Paper Intelligence
  2. Stitch Design Fidelity with QPI Domain Adaptation
  3. Hybrid Question Similarity & Scalable Vector Search
  4. Deterministic-First Engineering & Targeted AI Reasoning
  5. Strict Institutional Data Confidentiality & Auditability
-->
# Question Paper Intelligence (QPI) Constitution

## Core Principles

### I. Formative Assessment & Next-Paper Intelligence
The platform's primary mandate is formative: empowering faculty to prepare their NEXT exam question paper by surfacing historical question repetitions, unit/topic coverage gaps, Bloom's taxonomy difficulty distribution, and question-type balance. It is NOT primarily a punitive plagiarism tool or passive archive.

### II. Stitch Design Fidelity with QPI Domain Adaptation
UI implementations MUST faithfully preserve the "Academic Precision" design system from Stitch (Oxford Blue palette, Inter typography, 1px low-contrast outlines, Bento layout grids, responsive desktop/mobile rails). However, all manuscript/publication mock concepts (e.g. "student author", "literature gaps", "publication potential") MUST be adapted to question paper domain entities (Examiner, Course Code, Exam Term, Unit Representation, Bloom's Balance).

### III. Hybrid Question Similarity & Scalable Vector Search
Question similarity matching MUST combine semantic dense vector embeddings (`Sentence-Transformers` with `pgvector` HNSW indexing) and lexical keyword matching (`BM25`) at the atomic question level. Paper analysis MUST complete in <90 seconds for a 50-question paper (p95).

### IV. Deterministic-First Engineering & Targeted AI Reasoning
Mathematical aggregations, topic frequency metrics, unit coverage percentages, and database lookups MUST use fast, deterministic SQL/Python code. Google ADK Agents MUST be reserved strictly for unstructured reasoning tasks where LLMs genuinely add value: layout parsing fallbacks, topic/Bloom's taxonomy classification, and synthesizing actionable narrative paper recommendations.

### V. Strict Institutional Data Confidentiality & Auditability
Question paper drafts and historical question banks are sensitive institutional assets. System architecture MUST enforce zero standing developer access, AES-256 field-level encryption at rest, TLS 1.3 in transit, institutional SSO authentication, strict multi-tenant RBAC, and append-only immutable audit logging.

## Governance & Compliance

- **Constitution Supremacy**: This constitution defines non-negotiable architectural, domain, and design standards for all QPI feature specifications (`/spec`) and implementations.
- **Specification Compliance**: All feature proposals generated via Spec Kit (`/speckit-specify`, `/speckit-plan`) MUST explicitly verify alignment with these core principles.
- **Amendment Procedure**: Proposed modifications to core principles require a semantic version bump, explicit rationale, and update to the Sync Impact Report.

**Version**: 1.0.0 | **Ratified**: 2026-09-02 | **Last Amended**: 2026-09-02
