# Quickstart & Verification Guide: Question Paper Intelligence (QPI)

**Feature**: Question Paper Analysis & Next-Paper Preparation (`001-qpi-core-workflow`)  
**Target Audience**: Developers, QA Engineers, and System Architects  

---

## 1. Prerequisites

- **Python**: 3.12+
- **Node.js**: 20+ (with `npm` or `pnpm`)
- **Database**: PostgreSQL 16+ with `pgvector` extension installed (`apt install postgresql-16-pgvector` or Docker container)
- **Redis**: 7.0+ (for Celery background task queue)
- **System Dependencies**: Tesseract OCR (`tesseract-ocr`), Poppler utilities (`poppler-utils` for PDF rendering)

---

## 2. Local Environment Setup

### 2.1 Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run Database Migrations
alembic upgrade head

# Start Celery Worker
celery -A app.tasks worker --loglevel=info

# Start FastAPI Server
uvicorn app.main:app --reload --port 8000
```

### 2.2 Frontend Setup
```bash
cd frontend
npm install
npm run dev  # Starts Next.js dev server on http://localhost:3000
```

---

## 3. End-to-End Verification Scenario

### Scenario 1: Upload Question Paper Draft
1. Open browser to `http://localhost:3000/upload`.
2. Select Course `Physics 201 (PHY-201)`, Academic Term `Fall 2025`, Exam Type `Final Examination`.
3. Drag and drop sample question paper file `sample_physics_draft.pdf` (25MB max).
4. Click **Begin Analysis**.
5. **Expected Result**: Page redirects to upload progress state showing progress bar ("Parsing layout" → "Generating vector embeddings" → "Scanning historical archive...").

### Scenario 2: View Originality & Match Report
1. After processing completes, page automatically redirects to `/reports/[report_id]`.
2. **Expected Result**:
   - Originality Score radial gauge displays score (e.g. `88%`).
   - Split-pane document viewer loads draft paper on the right.
   - Question 4 is highlighted in red (`95% Match: 2021 Final Exam`).
   - Clicking Question 4 card on the left panel auto-scrolls the paper viewer to Question 4.

### Scenario 3: View QPI Preparation Insights
1. Click **Preparation Insights** tab.
2. **Expected Result**:
   - Proposed Draft Freshness gauge displays `85%`.
   - Conceptual Gaps list displays under-tested topics (e.g., `Quantum Fluid Dynamics - Last covered: Spring 2021`).
   - 5-Year Overused Topics bar chart displays topic frequency with saturation warnings.
   - Recommendation panel presents actionable advice: `"Replace Q4 to reduce 2021 overlap; add 1 Application-level question from Unit 3"`.

---

## 4. API Endpoint Verification Commands

### Check Health & Vector Extension
```bash
curl -X GET http://localhost:8000/health
```

### Test Paper Upload API
```bash
curl -X POST "http://localhost:8000/api/v1/papers/upload" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "file=@sample_physics_draft.pdf" \
  -F "course_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "academic_year=2025-2026" \
  -F "term=Fall" \
  -F "exam_type=Final" \
  -F "total_marks=100"
```
