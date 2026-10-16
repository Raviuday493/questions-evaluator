# Technical Research & Architecture Decisions: Question Paper Intelligence (QPI)

**Feature**: Question Paper Analysis & Next-Paper Preparation (`001-qpi-core-workflow`)  
**Created**: 2026-09-02  
**Status**: Resolved  

---

## 1. Document Extraction & Question Parsing
* **Decision**: Hybrid `PyMuPDF` (`fitz`) layout-aware bounding box parser with `Tesseract OCR` fallback and Google ADK `QuestionParserAgent` fallback.
* **Rationale**: 85% of exam papers follow semi-standard layout patterns (numbered questions, section headers). PyMuPDF extracts text elements with font metrics and spatial $(x, y)$ coordinates in $<0.5$ seconds per page. Tesseract OCR is triggered when native text is missing (<50 characters). For irregular/multi-column layouts where regex/spatial heuristics fail, the request is delegated to the ADK `QuestionParserAgent`.
* **Alternatives Considered**:
  * *Pure LLM Vision Parsing (Gemini Multimodal for all pages)*: Rejected due to latency ($>15$s per page) and unnecessary cost for standard digital PDFs.
  * *Unstructured.io / Apache Tika*: Rejected due to heavy Java/C++ runtime overhead and lower precision on multi-part exam question structures (e.g. 1a, 1b).

---

## 2. Embedding Model & Vector Storage
* **Decision**: `sentence-transformers/all-mpnet-base-v2` (768-dimensional dense embeddings) hosted locally via ONNX Runtime / PyTorch CPU, stored in `PostgreSQL 16` using the `pgvector` HNSW index.
* **Rationale**: `all-mpnet-base-v2` delivers top-tier semantic retrieval performance for academic text and STEM questions. Hosting locally via ONNX Runtime ensures zero third-party data leakage, $<20$ms per question embedding generation on CPU, and zero cloud API dependency. `pgvector` with HNSW (`m=16`, `ef_construction=64`) handles $100,000+$ question vectors with $<10$ms query latency inside PostgreSQL.
* **Alternatives Considered**:
  * *OpenAI text-embedding-3-small*: Rejected due to cloud privacy constraints (PRD security rules) and network dependency.
  * *Dedicated Pinecone / Qdrant cluster*: Rejected because `pgvector` keeps relational paper metadata, user RBAC, and vector indices within a single ACID-compliant PostgreSQL database, eliminating multi-database sync complexity.

---

## 3. Hybrid Similarity Search & Scoring Formula
* **Decision**: Reciprocal Rank Fusion (RRF) + Linear Weighted Hybrid Scoring combining `pgvector` Cosine Distance and PostgreSQL Full-Text Search / `rank-bm25`.
* **Formula**:
  $$\text{Composite Similarity Score} = \alpha \cdot \text{CosineSimilarity}(\vec{v}_{draft}, \vec{v}_{hist}) + (1 - \alpha) \cdot \text{BM25Normalized}(q_{draft}, q_{hist})$$
  *(Default $\alpha = 0.70$ semantic, $0.30$ lexical)*.
* **Match Tier Boundaries**:
  * **Exact Match ($\ge 90\%$)**: Verbatim or near-identical question repetition.
  * **Paraphrased Match ($75\% - 89\%$)**: Same core question prompt with rephrased terminology or parameter value changes.
  * **Conceptual Match ($60\% - 74\%$)**: Shared underlying concept or theorem from the same syllabus sub-topic.
* **Rationale**: Pure vector search can miss exact keyword/numerical substitutions, while pure BM25 misses semantic paraphrasing. Hybrid scoring captures both verbatim recycling and conceptual duplication.

---

## 4. Question Classification Strategy (Deterministic vs. Agent Boundaries)
* **Decision**: Two-pass classification:
  1. *Pass 1 (Deterministic)*: Keyword/Pattern matcher for Question Type (MCQ, Short, Long, Numerical) based on mark allocation and regex rules; Topic lookup via syllabus keyword dictionary.
  2. *Pass 2 (ADK Classifier Agent)*: Delegated to `ClassifierAgent` for Bloom's Taxonomy categorization (Remember, Understand, Apply, Analyze, Evaluate, Create) and ambiguous topic disambiguation.
* **Rationale**: Question format and mark allocation are 100% deterministic (e.g., 1 mark = MCQ, 2–3 marks = Short, 10+ marks = Long). Bloom's Taxonomy cognitive depth requires semantic understanding, where an LLM agent excels.

---

## 5. Next-Paper Recommendation Engine
* **Decision**: Deterministic Metric Aggregator + ADK `RecommendationAgent`.
* **Rationale**: SQL queries aggregate topic frequency stats, unit weightage imbalances, and repeated question counts into a structured JSON payload. The `RecommendationAgent` consumes this structured diagnostic context to synthesize 3–5 actionable, human-friendly recommendations for the faculty member's NEXT draft paper.

---

## 6. Background Job Architecture
* **Decision**: `FastAPI` + `Redis` + `Celery` worker pool with task state tracking.
* **Rationale**: Paper parsing, embedding generation, vector matching, and report generation take 10–30 seconds. Celery async tasks allow instant upload response ($<500$ms) with real-time SSE / WebSocket or HTTP polling updates on the `/upload` status screen.
