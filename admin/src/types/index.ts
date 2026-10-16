// Shapes returned by the backend admin API (/api/v1/admin).

export interface Paginated<T> {
  items: T[];
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export type UserRole = "FACULTY" | "DEPT_HEAD" | "ARCHIVAL_ADMIN" | "SYSTEM_ADMIN";
export type PaperStatus = "QUEUED" | "PARSING" | "EMBEDDING" | "MATCHING" | "COMPLETED" | "APPROVED" | "FAILED";

export interface AdminSessionInfo {
  id: string;
  expires_at: string;
  absolute_expires_at: string;
  idle_timeout_minutes: number;
}

export interface AdminProfile {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_super_admin: boolean;
  role: { id: string; key: string; name: string } | null;
  permissions: string[];
  last_login_at: string | null;
  created_at: string;
  session?: AdminSessionInfo;
}

export interface DepartmentRef {
  id: string;
  code: string;
  name: string;
}

export interface AppUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department: DepartmentRef | null;
  is_active: boolean;
  last_login_at: string | null;
  sessions_invalidated_at: string | null;
  created_at: string;
  updated_at: string;
  paper_count: number;
}

export interface ActivityEntry {
  id: string;
  action: string;
  resource_id?: string;
  details: Record<string, unknown>;
  created_at: string;
  admin_name?: string | null;
}

export interface AppUserDetail extends AppUser {
  stats: {
    papers_total: number;
    papers_by_status: Record<string, number>;
    approved: number;
    failed: number;
    avg_originality: number | null;
    last_activity_at: string | null;
  };
  recent_papers: {
    id: string;
    course_code: string;
    academic_year: string;
    term: string;
    exam_type: string;
    status: PaperStatus;
    is_historical_archive: boolean;
    originality_score: number | null;
    created_at: string;
  }[];
  recent_activity: ActivityEntry[];
  admin_actions: ActivityEntry[];
}

export interface Paper {
  id: string;
  course: { id: string; code: string; title: string } | null;
  department: DepartmentRef | null;
  uploader: { id: string; full_name: string; email: string } | null;
  academic_year: string;
  term: string;
  exam_type: string;
  total_marks: number;
  original_filename: string;
  file_mime_type: string;
  file_size_bytes: number;
  is_historical_archive: boolean;
  status: PaperStatus;
  progress_percent: number;
  current_step: string | null;
  error_message: string | null;
  is_stuck: boolean;
  previous_paper_id: string | null;
  report_id: string | null;
  originality_score: number | null;
  total_questions: number | null;
  matched_questions_count: number | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaperQuestion {
  id: string;
  question_number: string;
  section_name: string | null;
  text: string;
  marks: number;
  question_type: string | null;
  blooms_level: string | null;
  unit: { unit_number: number; title: string } | null;
  is_sub_question: boolean;
  best_match: { match_tier: string; composite_score: number; source_paper_id: string; source_label: string } | null;
}

export interface PaperDetail extends Paper {
  approved_by: { id: string; full_name: string } | null;
  report: {
    id: string;
    originality_score: number;
    total_questions: number;
    matched_questions_count: number;
    severity_breakdown: Record<string, number>;
    scan: Record<string, unknown>;
    blooms_distribution: Record<string, unknown>;
    question_types: Record<string, unknown>;
    unit_coverage: unknown;
    processing_seconds: number | null;
    generated_at: string;
    recommendations: { priority: number; category: string; action_text: string; rationale: string }[];
  } | null;
  questions: PaperQuestion[];
  revisions: { id: string; status: PaperStatus; created_at: string }[];
  times_matched_by_other_drafts: number;
  can_reanalyze: boolean;
  can_approve: boolean;
  can_delete: boolean;
  can_mark_failed: boolean;
}

export interface FilesPage extends Paginated<Paper> {
  summary: {
    total_files: number;
    total_bytes: number;
    by_type: { mime_type: string; count: number; bytes: number }[];
    storage_type: string;
  };
}

export interface Department extends DepartmentRef {
  created_at: string;
  user_count: number;
  course_count: number;
  paper_count: number;
}

export interface Course {
  id: string;
  code: string;
  title: string;
  academic_year: string;
  department: DepartmentRef | null;
  created_at: string;
  paper_count: number;
  unit_count: number | null;
}

export interface SyllabusUnit {
  id?: string;
  unit_number: number;
  title: string;
  target_weightage_percent: number;
  keywords: string[];
}

export interface CourseDetail extends Course {
  syllabus: SyllabusUnit[];
  stats: { analyzed_drafts: number; avg_originality: number | null; archive_papers: number };
}

export interface AuditEntry {
  id: string;
  action: string;
  entity_type: string | null;
  entity_id: string;
  actor: { type: "admin" | "user" | "system"; id: string | null; name: string; email: string | null };
  details: Record<string, unknown>;
  ip_hash: string;
  user_agent: string | null;
  created_at: string;
}

export interface AdminRole {
  id: string;
  key: string;
  name: string;
  description: string;
  permissions: string[];
  is_wildcard: boolean;
  is_system: boolean;
  admin_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminAccount {
  id: string;
  email: string;
  full_name: string;
  role: { id: string; key: string; name: string } | null;
  is_super_admin: boolean;
  is_active: boolean;
  is_locked: boolean;
  locked_until: string | null;
  last_login_at: string | null;
  password_changed_at: string | null;
  active_sessions: number;
  created_at: string;
}

export interface SessionRow {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  revoked_at: string | null;
  user_agent: string | null;
  is_active: boolean;
  is_current: boolean;
}

export interface AdminAccountDetail extends AdminAccount {
  permissions: string[];
  sessions: SessionRow[];
  recent_actions: { id: string; action: string; entity_type: string | null; entity_id: string; created_at: string }[];
}

export interface Permission {
  key: string;
  group: string;
  description: string;
}

export interface SettingItem {
  key: string;
  label: string;
  group: string;
  type: "bool" | "int" | "float";
  description: string;
  value: boolean | number;
  default: boolean | number;
  min: number | null;
  max: number | null;
  is_overridden: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

export interface DashboardSummary {
  users: { total: number; active: number; inactive: number; new_30d: number; new_30d_change_percent: number | null; signed_in_30d: number };
  papers: {
    drafts_total: number;
    archive_total: number;
    uploads_30d: number;
    uploads_30d_change_percent: number | null;
    analyzed: number;
    approved: number;
    in_progress: number;
    stuck: number;
    failed: number;
    failed_7d: number;
    avg_originality: number | null;
  };
  content: { questions: number; matches: number; departments: number; courses: number; storage_bytes: number };
  activity: { events_today: number; user_logins_today: number; admin_actions_today: number };
  generated_at: string;
}

export interface TimeSeries {
  range: string;
  from: string;
  to: string;
  bucket: "day" | "week" | "month";
  labels: string[];
  series: Record<"uploads" | "archive_ingests" | "failed" | "approvals" | "signups" | "logins", number[]>;
}

export interface Distribution {
  paper_status: Record<string, number>;
  match_tiers: Record<string, number>;
  user_roles: Record<string, number>;
  papers_by_department: { code: string; name: string; count: number }[];
}

export interface DashboardActivity {
  recent_signups: { id: string; full_name: string; email: string; role: UserRole; created_at: string }[];
  recent_uploads: { id: string; course_code: string; status: PaperStatus; is_historical_archive: boolean; uploader_name: string | null; created_at: string }[];
  recent_failures: { id: string; course_code: string; error_message: string | null; updated_at: string }[];
  recent_admin_actions: { id: string; action: string; entity_type: string | null; entity_id: string; admin_name: string; created_at: string }[];
}

export interface AlertItem {
  key: string;
  severity: "warning" | "error";
  count: number;
  message: string;
  link: string;
}

export interface ReportOverview {
  from: string;
  to: string;
  status_breakdown: Record<string, number>;
  match_tiers: Record<string, number>;
  blooms_levels: Record<string, number>;
  question_types: Record<string, number>;
  by_department: { code: string; name: string; papers: number; avg_originality: number | null; min_originality: number | null; max_originality: number | null; matched_questions: number }[];
  by_course: { course_id: string; code: string; title: string; department_code: string; papers: number; avg_originality: number | null; min_originality: number | null; max_originality: number | null; matched_questions: number }[];
  top_uploaders: { user_id: string; full_name: string; email: string; papers: number; avg_originality: number | null }[];
}

export interface SystemHealth {
  status: string;
  version: string;
  environment: string;
  database: { status: string; dialect: string; migration: string | null };
  task_queue: { backend: string; in_progress: number; stuck: number; stuck_after_minutes: number };
  embeddings: { provider: string; model: string; dimension: number };
  storage: { type: string };
  security: Record<string, unknown>;
  checked_at: string;
}

export interface SearchHit {
  id: string;
  title: string;
  subtitle: string;
}

export type SearchResults = Partial<Record<"users" | "papers" | "courses" | "departments" | "admins", SearchHit[]>>;
