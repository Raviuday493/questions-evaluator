// Single HTTP client for the admin API. Requests go to this site's own origin and are proxied to the
// backend's /api/v1/admin namespace (see next.config.mjs), so the session cookie is first-party.

export const API_BASE = "/api/v1/admin";
const TIMEOUT_MS = 20_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fieldErrors: { field: string; message: string }[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type Query = Record<string, string | number | boolean | undefined | null>;

export function toQuery(params: Query = {}): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

let redirecting = false;
function handleUnauthorized() {
  if (typeof window === "undefined" || redirecting || window.location.pathname === "/login") return;
  redirecting = true;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.assign(`/login?next=${next}&expired=1`);
}

async function parseError(res: Response): Promise<ApiError> {
  let message = "";
  let fieldErrors: { field: string; message: string }[] = [];
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") message = body.detail;
    else if (Array.isArray(body?.detail)) message = body.detail.map((d: { msg?: string }) => d.msg).join("; ");
    if (Array.isArray(body?.errors)) fieldErrors = body.errors;
  } catch {
    // non-JSON body (proxy error page etc.)
  }
  if (!message) {
    if (res.status === 403) message = "You do not have permission to do this.";
    else if (res.status === 404) message = "Not found.";
    else if ([502, 503, 504].includes(res.status)) message = "The backend API is unavailable. Check that it is running.";
    else if (res.status >= 500) message = "The server encountered an error. Please try again.";
    else message = `Request failed (${res.status})`;
  }
  return new ApiError(message, res.status, fieldErrors);
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const headers = new Headers(init.headers);
  // Required by the backend on state-changing requests (CSRF defence for cookie sessions).
  headers.set("X-Admin-Request", "1");
  try {
    return await fetch(`${API_BASE}${path}`, { credentials: "same-origin", ...init, headers, signal: controller.signal });
  } catch (err) {
    if ((err as Error)?.name === "AbortError") throw new ApiError("The request timed out. Please try again.", 0);
    throw new ApiError("Cannot reach the server. Check your connection and that the backend is running.", 0);
  } finally {
    clearTimeout(timer);
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await send(path, init);
  if (res.status === 401 && path !== "/auth/login") {
    handleUnauthorized();
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function jsonBody(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

/** Download an authenticated file (CSV export, original upload) through fetch so errors are reported. */
export async function download(path: string, fallbackName: string): Promise<void> {
  const res = await send(path);
  if (res.status === 401) {
    handleUnauthorized();
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/.exec(disposition);
  const name = match ? decodeURIComponent(match[1] ?? match[2]) : fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function errorText(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
