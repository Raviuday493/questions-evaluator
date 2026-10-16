import type { MatchTier, PaperStatus, UserRole } from "./types";

export const ROLE_LABELS: Record<UserRole, string> = {
  FACULTY: "Faculty",
  DEPT_HEAD: "Department Head",
  ARCHIVAL_ADMIN: "Archival Administrator",
  SYSTEM_ADMIN: "System Administrator",
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

export const IN_PROGRESS: PaperStatus[] = ["QUEUED", "PARSING", "EMBEDDING", "MATCHING"];

export function isInProgress(status: PaperStatus): boolean {
  return IN_PROGRESS.includes(status);
}

export function statusBadgeClass(status: PaperStatus): string {
  switch (status) {
    case "COMPLETED":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "APPROVED":
      return "bg-blue-50 text-accent border-blue-200";
    case "FAILED":
      return "bg-red-50 text-red-700 border-red-200";
    default:
      return "bg-amber-50 text-amber-700 border-amber-200";
  }
}

export const TIER_LABELS: Record<MatchTier, string> = {
  EXACT: "Exact",
  PARAPHRASED: "Paraphrased",
  CONCEPTUAL: "Conceptual",
};

export function tierClasses(tier: MatchTier | null | undefined): string {
  if (tier === "EXACT" || tier === "PARAPHRASED") return "bg-red-50 text-red-700 border-red-200";
  if (tier === "CONCEPTUAL") return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-slate-50 text-slate-500 border-slate-200";
}

export function originalityBand(score: number): { label: string; classes: string; border: string } {
  if (score >= 80) return { label: "High Originality", classes: "bg-emerald-50 text-emerald-700", border: "border-t-emerald-500" };
  if (score >= 60) return { label: "Moderate Originality", classes: "bg-amber-50 text-amber-700", border: "border-t-amber-500" };
  return { label: "Low Originality", classes: "bg-red-50 text-red-700", border: "border-t-red-500" };
}

export function titleCase(value: string): string {
  if (value === "MCQ") return value;
  return value
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}%`;
}

/** Academic years like "2026-2027": the current one (starting in August) and the three before it. */
export function academicYearOptions(now = new Date()): string[] {
  const start = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1;
  return [0, 1, 2, 3].map((i) => `${start - i}-${start - i + 1}`);
}
