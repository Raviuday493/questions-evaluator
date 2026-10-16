export type UserRole = "FACULTY" | "DEPT_HEAD" | "ARCHIVAL_ADMIN" | "SYSTEM_ADMIN";

export type PaperStatus =
  | "QUEUED"
  | "PARSING"
  | "EMBEDDING"
  | "MATCHING"
  | "COMPLETED"
  | "APPROVED"
  | "FAILED";

export type MatchTier = "EXACT" | "PARAPHRASED" | "CONCEPTUAL";

export interface Department {
  id: string;
  code: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department: Department | null;
  created_at: string;
}

export interface Course {
  id: string;
  code: string;
  title: string;
  department: Department;
}

export interface PaperSummary {
  id: string;
  course_code: string;
  course_title: string;
  department: string | null;
  department_code: string | null;
  academic_year: string;
  term: string;
  exam_type: string;
  total_marks: number;
  original_filename: string;
  status: PaperStatus;
  progress_percent: number;
  current_step: string | null;
  error_message: string | null;
  is_historical_archive: boolean;
  previous_paper_id: string | null;
  report_id: string | null;
  originality_score: number | null;
  matched_questions_count: number | null;
  uploader_name: string;
  is_owner: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaperList {
  items: PaperSummary[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface UploadAccepted {
  paper_id: string;
  status: PaperStatus;
  status_url: string;
}

export interface PaperStatusResponse {
  paper_id: string;
  status: PaperStatus;
  progress_percent: number;
  current_step: string | null;
  error_message: string | null;
  report_id: string | null;
}

export interface DashboardStats {
  total_analyzed: number;
  analyzed_last_30_days: number;
  analyzed_change_percent: number | null;
  avg_originality: number | null;
  in_progress: number;
  failed: number;
  approved: number;
  total_matches: number;
}

export interface ReportPaper {
  id: string;
  course_code: string;
  course_title: string;
  department: string | null;
  academic_year: string;
  term: string;
  exam_type: string;
  total_marks: number;
  original_filename: string;
  status: PaperStatus;
  is_historical_archive: boolean;
  uploader_name: string | null;
  uploaded_at: string;
  approved_at: string | null;
  previous_paper_id: string | null;
  can_approve: boolean;
  can_manage: boolean;
}

export interface MatchSource {
  paper_id: string;
  course_code: string;
  academic_year: string;
  term: string;
  exam_type: string;
  question_number: string;
  text: string;
}

export interface MatchDetail {
  match_tier: MatchTier;
  composite_score: number;
  semantic_score: number;
  lexical_score: number;
  source_paper: string;
  source: MatchSource;
}

export interface MatchedQuestion extends MatchDetail {
  question_id: string;
  question_number: string;
  draft_text: string;
  marks: number;
  other_matches: MatchDetail[];
}

export interface ReportQuestion {
  id: string;
  question_number: string;
  section_name: string | null;
  text: string;
  marks: number;
  question_type: string | null;
  blooms_level: string | null;
  unit: { unit_number: number; title: string } | null;
  is_sub_question: boolean;
  match_tier: MatchTier | null;
  composite_score: number | null;
}

export interface ScanMetadata {
  scope?: "COURSE" | "DEPARTMENT" | "NONE";
  historical_papers_searched?: number;
  historical_questions_searched?: number;
  archive_year_range?: string | null;
  embedding_model?: string;
}

export interface Report {
  report_id: string;
  paper_id: string;
  paper: ReportPaper;
  originality_score: number;
  total_questions: number;
  matched_questions_count: number;
  severity_breakdown: Partial<Record<MatchTier, number>>;
  scan: ScanMetadata;
  processing_seconds: number | null;
  generated_at: string;
  previous_report: { paper_id: string; report_id: string; originality_score: number } | null;
  matched_questions: MatchedQuestion[];
  questions: ReportQuestion[];
}

export interface UnitCoverage {
  unit_id: string;
  unit_number: number;
  title: string;
  target_percent: number;
  actual_percent: number;
  question_count: number;
  status: "OVER" | "UNDER" | "BALANCED";
}

export interface ConceptualGap extends UnitCoverage {
  last_covered: string | null;
}

export interface Distribution {
  total: number;
  counts: Record<string, number>;
  percentages: Record<string, number>;
  higher_order_percent?: number;
}

export interface OverusedTopic {
  unit_id: string;
  unit_number: number;
  title: string;
  cycles_tested: number;
  cycles_total: number;
  saturated: boolean;
  draft_percent: number;
}

export interface Recommendation {
  priority: number;
  category: "REPETITION_SWAP" | "UNIT_REBALANCE" | "BLOOMS_ELEVATION" | "FORMAT_DIVERSIFICATION";
  action_text: string;
  rationale: string;
  target_question_number: string | null;
}

export interface Insights {
  report_id: string;
  paper: ReportPaper;
  draft_freshness_score: number;
  has_syllabus: boolean;
  unit_coverage: { units: UnitCoverage[]; unassigned_percent: number };
  conceptual_gaps: ConceptualGap[];
  blooms_distribution: Distribution;
  question_types: Distribution;
  overused_topics: OverusedTopic[];
  recommendations: Recommendation[];
  scan: ScanMetadata;
}
