import type {
  Course,
  DashboardStats,
  Department,
  Insights,
  PaperList,
  PaperStatusResponse,
  PaperSummary,
  Report,
  UploadAccepted,
  User,
} from "./types";

// Requests go to the Next.js origin and are proxied to FastAPI (see next.config.mjs).
const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const AUTH_ENDPOINTS = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"];

let refreshInFlight: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  // Concurrent 401s share a single refresh request.
  refreshInFlight ??= fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

function redirectToLogin() {
  if (typeof window === "undefined" || window.location.pathname.startsWith("/login")) return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.assign(`/login?next=${next}`);
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    // non-JSON error body (e.g. proxy error page)
  }
  if (res.status >= 500) return "The server encountered an error. Please try again.";
  return `Request failed (${res.status})`;
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { credentials: "same-origin", ...init });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and that the backend is running.", 0);
  }

  if (res.status === 401 && !AUTH_ENDPOINTS.includes(path)) {
    if (retry && (await refreshSession())) return request<T>(path, init, false);
    redirectToLogin();
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function json(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

function query(params: Record<string, string | number | undefined | null>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export interface PaperListParams {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
  sort?: string;
  order?: "asc" | "desc";
}

export interface UploadFields {
  file: File;
  courseCode: string;
  departmentCode: string;
  academicYear: string;
  term: string;
  examType: string;
  totalMarks: number;
  previousPaperId?: string | null;
  isHistoricalArchive?: boolean;
}

export const api = {
  // auth
  login: (email: string, password: string) => request<User>("/auth/login", json("POST", { email, password })),
  register: (data: { email: string; full_name: string; password: string; department_code?: string | null }) =>
    request<User>("/auth/register", json("POST", data)),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),

  // catalog
  departments: () => request<Department[]>("/departments"),
  courses: (departmentCode?: string) => request<Course[]>(`/courses${query({ department_code: departmentCode })}`),

  // papers
  papers: (params: PaperListParams = {}) => request<PaperList>(`/papers${query({ ...params })}`),
  paper: (id: string) => request<PaperSummary>(`/papers/${id}`),
  paperStatus: (id: string) => request<PaperStatusResponse>(`/papers/${id}/status`),
  uploadPaper: (f: UploadFields) => {
    const form = new FormData();
    form.append("file", f.file);
    form.append("course_code", f.courseCode);
    form.append("department_code", f.departmentCode);
    form.append("academic_year", f.academicYear);
    form.append("term", f.term);
    form.append("exam_type", f.examType);
    form.append("total_marks", String(f.totalMarks));
    if (f.previousPaperId) form.append("previous_paper_id", f.previousPaperId);
    if (f.isHistoricalArchive) form.append("is_historical_archive", "true");
    return request<UploadAccepted>("/papers/upload", { method: "POST", body: form });
  },
  reanalyzePaper: (id: string) => request<PaperStatusResponse>(`/papers/${id}/reanalyze`, { method: "POST" }),
  approvePaper: (id: string) => request<PaperSummary>(`/papers/${id}/approve`, { method: "POST" }),
  deletePaper: (id: string) => request<void>(`/papers/${id}`, { method: "DELETE" }),
  paperFileUrl: (id: string) => `${API_BASE}/papers/${id}/file`,

  // reports & dashboard
  report: (id: string) => request<Report>(`/reports/${id}`),
  insights: (id: string) => request<Insights>(`/reports/${id}/insights`),
  dashboardStats: () => request<DashboardStats>("/dashboard/stats"),
};

export function errorText(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong.";
}
