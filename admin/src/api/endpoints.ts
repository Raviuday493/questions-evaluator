import { download, jsonBody, request, toQuery, type Query } from "./client";
import type {
  AdminAccount,
  AdminAccountDetail,
  AdminProfile,
  AdminRole,
  AlertItem,
  AppUser,
  AppUserDetail,
  AuditEntry,
  Course,
  CourseDetail,
  DashboardActivity,
  DashboardSummary,
  Department,
  Distribution,
  FilesPage,
  Paginated,
  Paper,
  PaperDetail,
  Permission,
  ReportOverview,
  SearchResults,
  SessionRow,
  SettingItem,
  SyllabusUnit,
  SystemHealth,
  TimeSeries,
} from "@/types";

const get = <T,>(path: string, params?: Query) => request<T>(`${path}${toQuery(params)}`);
const post = <T,>(path: string, body?: unknown) => request<T>(path, jsonBody("POST", body ?? {}));
const patch = <T,>(path: string, body: unknown) => request<T>(path, jsonBody("PATCH", body));
const put = <T,>(path: string, body: unknown) => request<T>(path, jsonBody("PUT", body));
const del = (path: string) => request<void>(path, { method: "DELETE" });

export const adminApi = {
  auth: {
    login: (email: string, password: string) => post<AdminProfile>("/auth/login", { email, password }),
    logout: () => post<void>("/auth/logout"),
    me: () => get<AdminProfile>("/auth/me"),
    changePassword: (current_password: string, new_password: string) =>
      post<void>("/auth/change-password", { current_password, new_password }),
    sessions: () => get<SessionRow[]>("/auth/sessions"),
    revokeSession: (id: string) => del(`/auth/sessions/${id}`),
  },
  dashboard: {
    summary: () => get<DashboardSummary>("/dashboard/summary"),
    timeseries: (params: Query) => get<TimeSeries>("/dashboard/timeseries", params),
    distribution: () => get<Distribution>("/dashboard/distribution"),
    activity: () => get<DashboardActivity>("/dashboard/activity"),
    alerts: () => get<{ items: AlertItem[]; count: number }>("/dashboard/alerts"),
  },
  users: {
    list: (params: Query) => get<Paginated<AppUser>>("/users", params),
    get: (id: string) => get<AppUserDetail>(`/users/${id}`),
    create: (body: unknown) => post<AppUser>("/users", body),
    update: (id: string, body: unknown) => patch<AppUser>(`/users/${id}`, body),
    activate: (id: string, reason?: string) => post<AppUser>(`/users/${id}/activate`, { reason }),
    deactivate: (id: string, reason?: string) => post<AppUser>(`/users/${id}/deactivate`, { reason }),
    revokeSessions: (id: string) => post<AppUser>(`/users/${id}/revoke-sessions`),
    resetPassword: (id: string, new_password: string) => post<void>(`/users/${id}/reset-password`, { new_password }),
    remove: (id: string) => del(`/users/${id}`),
    bulk: (ids: string[], action: "activate" | "deactivate" | "revoke_sessions") =>
      post<{ requested: number; found: number; changed: number }>("/users/bulk", { ids, action }),
    export: (params: Query) => download(`/users/export${toQuery(params)}`, "users.csv"),
  },
  papers: {
    list: (params: Query) => get<Paginated<Paper>>("/papers", params),
    get: (id: string) => get<PaperDetail>(`/papers/${id}`),
    reanalyze: (id: string) => post<Paper>(`/papers/${id}/reanalyze`),
    approve: (id: string) => post<Paper>(`/papers/${id}/approve`),
    markFailed: (id: string, reason: string) => post<Paper>(`/papers/${id}/mark-failed`, { reason }),
    remove: (id: string) => del(`/papers/${id}`),
    bulk: (ids: string[], action: "reanalyze" | "delete") =>
      post<{ done: string[]; skipped: { id: string; reason: string }[]; not_found: number }>("/papers/bulk", { ids, action }),
    download: (id: string, name: string) => download(`/papers/${id}/file`, name),
    export: (params: Query) => download(`/papers/export${toQuery(params)}`, "papers.csv"),
  },
  files: {
    list: (params: Query) => get<FilesPage>("/files", params),
  },
  departments: {
    list: (params?: Query) => get<Department[]>("/departments", params),
    create: (body: { code: string; name: string }) => post<Department>("/departments", body),
    update: (id: string, body: { code?: string; name?: string }) => patch<Department>(`/departments/${id}`, body),
    remove: (id: string) => del(`/departments/${id}`),
  },
  courses: {
    list: (params: Query) => get<Paginated<Course>>("/courses", params),
    get: (id: string) => get<CourseDetail>(`/courses/${id}`),
    create: (body: unknown) => post<Course>("/courses", body),
    update: (id: string, body: unknown) => patch<Course>(`/courses/${id}`, body),
    remove: (id: string) => del(`/courses/${id}`),
    saveSyllabus: (id: string, units: SyllabusUnit[]) => put<SyllabusUnit[]>(`/courses/${id}/syllabus`, { units }),
  },
  reports: {
    overview: (params: Query) => get<ReportOverview>("/reports/overview", params),
    export: (kind: string, params: Query) => download(`/reports/${kind}/export${toQuery(params)}`, `${kind}-report.csv`),
  },
  audit: {
    list: (params: Query) => get<Paginated<AuditEntry>>("/audit-logs", params),
    facets: () => get<{ actions: string[]; entity_types: string[] }>("/audit-logs/facets"),
    export: (params: Query) => download(`/audit-logs/export${toQuery(params)}`, "audit-log.csv"),
  },
  admins: {
    list: (params?: Query) => get<AdminAccount[]>("/admins", params),
    get: (id: string) => get<AdminAccountDetail>(`/admins/${id}`),
    create: (body: unknown) => post<AdminAccount>("/admins", body),
    update: (id: string, body: unknown) => patch<AdminAccount>(`/admins/${id}`, body),
    remove: (id: string) => del(`/admins/${id}`),
    revokeSessions: (id: string) => post<{ revoked: number }>(`/admins/${id}/revoke-sessions`),
    resetPassword: (id: string, new_password: string) => post<void>(`/admins/${id}/reset-password`, { new_password }),
    unlock: (id: string) => post<AdminAccount>(`/admins/${id}/unlock`),
  },
  roles: {
    list: () => get<AdminRole[]>("/roles"),
    permissions: () => get<Permission[]>("/permissions"),
    create: (body: unknown) => post<AdminRole>("/roles", body),
    update: (id: string, body: unknown) => patch<AdminRole>(`/roles/${id}`, body),
    remove: (id: string) => del(`/roles/${id}`),
  },
  settings: {
    list: () => get<SettingItem[]>("/settings"),
    update: (values: Record<string, unknown>) => put<SettingItem[]>("/settings", { values }),
  },
  system: {
    health: () => get<SystemHealth>("/system/health"),
  },
  search: (q: string) => get<SearchResults>("/search", { q }),
};
