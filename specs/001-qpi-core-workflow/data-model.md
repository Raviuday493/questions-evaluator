# Data Model & Database Schema: Question Paper Intelligence (QPI)

**Feature**: Question Paper Analysis & Next-Paper Preparation (`001-qpi-core-workflow`)  
**Database**: PostgreSQL 16 with `pgvector` extension  

---

## 1. Entity-Relationship Summary

```
[User] 1 ──── N [QuestionPaperDraft] 1 ──── N [Question] 1 ──── N [SimilarityMatch]
   │                      │                     │
   ▼                      ▼                     ▼
[Department]           [Course]              [TopicTag]
                          │
                          ▼
                 [SyllabusUnit]
```

---

## 2. Table Definitions

### 2.1 `users`
Stores faculty members, department heads, and system administrators.
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('FACULTY', 'DEPT_HEAD', 'ARCHIVAL_ADMIN', 'SYSTEM_ADMIN')),
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    mfa_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 `departments`
Stores academic departments.
```sql
CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'CS', 'PHY'
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 2.3 `courses`
Stores university courses and syllabus configurations.
```sql
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL, -- e.g., 'CS-101'
    title VARCHAR(255) NOT NULL,
    academic_year VARCHAR(20) NOT NULL, -- e.g., '2025-2026'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (department_id, code)
);
```

### 2.4 `syllabus_units`
Stores syllabus unit/module weightages for a course.
```sql
CREATE TABLE syllabus_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    unit_number INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    target_weightage_percent NUMERIC(5,2) NOT NULL, -- e.g. 20.00%
    keywords TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 2.5 `question_paper_drafts`
Stores uploaded question papers (both draft papers and historical archived papers).
```sql
CREATE TABLE question_paper_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploader_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    academic_year VARCHAR(20) NOT NULL, -- e.g., '2025-2026'
    term VARCHAR(50) NOT NULL, -- e.g., 'Fall', 'Spring'
    exam_type VARCHAR(50) NOT NULL, -- e.g., 'Midterm', 'Final', 'Quiz'
    total_marks INT NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_mime_type VARCHAR(100) NOT NULL,
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 for duplicate detection
    is_historical_archive BOOLEAN DEFAULT FALSE, -- True if ingested in past archive
    status VARCHAR(50) NOT NULL DEFAULT 'QUEUED' 
        CHECK (status IN ('QUEUED', 'PARSING', 'EMBEDDING', 'MATCHING', 'COMPLETED', 'APPROVED', 'FAILED')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 2.6 `questions`
Stores individual parsed questions and vector embeddings.
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID NOT NULL REFERENCES question_paper_drafts(id) ON DELETE CASCADE,
    section_name VARCHAR(100), -- e.g., 'Section A'
    question_number VARCHAR(20) NOT NULL, -- e.g., '1', '4(a)'
    parent_question_id UUID REFERENCES questions(id) ON DELETE CASCADE, -- For sub-questions
    raw_text TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    marks INT DEFAULT 0,
    question_type VARCHAR(50) CHECK (question_type IN ('MCQ', 'SHORT_ANSWER', 'LONG_ESSAY', 'NUMERICAL', 'DERIVATION')),
    blooms_level VARCHAR(50) CHECK (blooms_level IN ('REMEMBER', 'UNDERSTAND', 'APPLY', 'ANALYZE', 'EVALUATE', 'CREATE')),
    unit_id UUID REFERENCES syllabus_units(id) ON DELETE SET NULL,
    embedding vector(768), -- 768d vector from all-mpnet-base-v2
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- HNSW Vector Index for fast cosine similarity lookup
CREATE INDEX idx_questions_embedding_hnsw 
ON questions USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### 2.7 `similarity_matches`
Stores similarity matches between draft questions and historical questions.
```sql
CREATE TABLE similarity_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    historical_question_id UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    semantic_score NUMERIC(5,4) NOT NULL, -- 0.0000 to 1.0000
    lexical_score NUMERIC(5,4) NOT NULL,  -- 0.0000 to 1.0000
    composite_score NUMERIC(5,4) NOT NULL, -- Weighted hybrid score
    match_tier VARCHAR(50) NOT NULL CHECK (match_tier IN ('EXACT', 'PARAPHRASED', 'CONCEPTUAL')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (draft_question_id, historical_question_id)
);
```

### 2.8 `qpi_reports`
Stores generated paper-level intelligence reports.
```sql
CREATE TABLE qpi_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID UNIQUE NOT NULL REFERENCES question_paper_drafts(id) ON DELETE CASCADE,
    originality_score NUMERIC(5,2) NOT NULL, -- 0.00 to 100.00%
    total_questions INT NOT NULL,
    matched_questions_count INT NOT NULL,
    unit_coverage_json JSONB NOT NULL, -- Unit representation map
    blooms_distribution_json JSONB NOT NULL, -- Bloom's breakdown map
    question_type_json JSONB NOT NULL, -- Question format breakdown map
    overused_topics_json JSONB NOT NULL, -- 5-year trend data
    generated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 2.9 `next_paper_recommendations`
Stores actionable improvement suggestions generated for the paper.
```sql
CREATE TABLE next_paper_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES qpi_reports(id) ON DELETE CASCADE,
    priority INT NOT NULL, -- 1 = Highest
    category VARCHAR(50) NOT NULL CHECK (category IN ('REPETITION_SWAP', 'UNIT_REBALANCE', 'BLOOMS_ELEVATION', 'FORMAT_DIVERSIFICATION')),
    target_question_id UUID REFERENCES questions(id) ON DELETE SET NULL,
    action_text TEXT NOT NULL,
    rationale TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 2.10 `audit_logs`
Stores immutable security and data access events.
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL, -- e.g., 'PAPER_UPLOAD', 'REPORT_VIEW', 'PAPER_APPROVE'
    resource_id UUID NOT NULL,
    details JSONB DEFAULT '{}',
    ip_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Index for security audit queries
CREATE INDEX idx_audit_logs_actor_timestamp ON audit_logs(actor_id, created_at DESC);
```
