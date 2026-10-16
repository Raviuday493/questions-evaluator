import type { PaperStatus, UserRole } from "@/types";

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

const dateFmt = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
});
const numberFmt = new Intl.NumberFormat();

export function formatDate(value: string | null | undefined): string {
  return value ? dateFmt.format(new Date(value)) : "—";
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTimeFmt.format(new Date(value)) : "—";
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return "Never";
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const units: [number, string][] = [[60, "minute"], [3600, "hour"], [86400, "day"], [2592000, "month"], [31536000, "year"]];
  for (let i = units.length - 1; i >= 0; i--) {
    const [size, unit] = units[i];
    if (Math.abs(seconds) >= size) {
      const n = Math.round(seconds / size);
      return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
}

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : numberFmt.format(value);
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}%`;
}

export const ROLE_LABELS: Record<UserRole, string> = {
  FACULTY: "Faculty",
  DEPT_HEAD: "Department Head",
  ARCHIVAL_ADMIN: "Archival Admin",
  SYSTEM_ADMIN: "System Admin",
};

export const STATUS_LABELS: Record<PaperStatus, string> = {
  QUEUED: "Queued",
  PARSING: "Parsing",
  EMBEDDING: "Embedding",
  MATCHING: "Matching",
  COMPLETED: "Completed",
  APPROVED: "Approved",
  FAILED: "Failed",
};

export const PAPER_STATUSES = Object.keys(STATUS_LABELS) as PaperStatus[];
export const USER_ROLES = Object.keys(ROLE_LABELS) as UserRole[];

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .toLowerCase()
    .split(/[_\s]+/)
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter((p) => /[A-Za-z]/.test(p[0] ?? ""))
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("") || "?";
}
