"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, Clock, Loader2, Search, XCircle } from "lucide-react";
import type { PaperStatus, UserRole } from "@/types";
import { ROLE_LABELS, STATUS_LABELS, cn } from "@/utils/format";
import { Badge, Input } from "./primitives";

export function PageHeader({ title, description, actions, back }: { title: string; description?: ReactNode; actions?: ReactNode; back?: { href: string; label: string } }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {back && (
          <Link href={back.href} className="mb-1 inline-block text-xs font-medium text-brand-600 hover:underline">
            ← {back.label}
          </Link>
        )}
        <h1 className="truncate text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder, label }: { value: string; onChange: (v: string) => void; placeholder: string; label: string }) {
  return (
    <div className="relative w-full sm:w-64">
      <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden />
      <Input type="search" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="h-8 pl-8" maxLength={100} />
    </div>
  );
}

// Status is shown with an icon + label, never colour alone.
const STATUS_TONE: Record<PaperStatus, { tone: "green" | "blue" | "amber" | "red" | "violet"; icon: ReactNode }> = {
  QUEUED: { tone: "amber", icon: <Clock size={12} aria-hidden /> },
  PARSING: { tone: "blue", icon: <Loader2 size={12} className="animate-spin" aria-hidden /> },
  EMBEDDING: { tone: "blue", icon: <Loader2 size={12} className="animate-spin" aria-hidden /> },
  MATCHING: { tone: "blue", icon: <Loader2 size={12} className="animate-spin" aria-hidden /> },
  COMPLETED: { tone: "violet", icon: <CheckCircle2 size={12} aria-hidden /> },
  APPROVED: { tone: "green", icon: <CheckCircle2 size={12} aria-hidden /> },
  FAILED: { tone: "red", icon: <XCircle size={12} aria-hidden /> },
};

export function PaperStatusBadge({ status, stuck }: { status: PaperStatus; stuck?: boolean }) {
  const s = STATUS_TONE[status];
  return (
    <span className="inline-flex items-center gap-1">
      <Badge tone={s.tone} icon={s.icon}>{STATUS_LABELS[status]}</Badge>
      {stuck && <Badge tone="orange" icon={<AlertCircle size={12} aria-hidden />}>Stuck</Badge>}
    </span>
  );
}

export function ActiveBadge({ active, activeLabel = "Active", inactiveLabel = "Inactive" }: { active: boolean; activeLabel?: string; inactiveLabel?: string }) {
  return active ? (
    <Badge tone="green" icon={<CheckCircle2 size={12} aria-hidden />}>{activeLabel}</Badge>
  ) : (
    <Badge tone="neutral" icon={<XCircle size={12} aria-hidden />}>{inactiveLabel}</Badge>
  );
}

export function RoleBadge({ role }: { role: UserRole }) {
  const tone = role === "SYSTEM_ADMIN" ? "red" : role === "ARCHIVAL_ADMIN" ? "orange" : role === "DEPT_HEAD" ? "blue" : "neutral";
  return <Badge tone={tone}>{ROLE_LABELS[role]}</Badge>;
}

export function OriginalityValue({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="text-ink-faint">—</span>;
  const tone = value >= 80 ? "text-emerald-700" : value >= 60 ? "text-amber-700" : "text-red-700";
  return <span className={cn("font-medium tabular-nums", tone)}>{value.toFixed(1)}%</span>;
}

export function StatCard({ label, value, hint, icon, tone, href }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: "default" | "warn" | "danger"; href?: string }) {
  const body = (
    <div className={cn(
      "flex h-full flex-col gap-1 rounded-lg border bg-white p-4 shadow-card transition-colors",
      tone === "danger" ? "border-red-200" : tone === "warn" ? "border-amber-200" : "border-line",
      href && "hover:border-brand-500/50",
    )}>
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-ink-muted">
        <span>{label}</span>
        {icon && <span className="text-ink-faint">{icon}</span>}
      </div>
      <div className="text-2xl font-semibold tracking-tight text-ink">{value}</div>
      {hint && <div className="text-xs text-ink-muted">{hint}</div>}
    </div>
  );
  return href ? <Link href={href} className="block">{body}</Link> : body;
}

export function ChangeHint({ value, label }: { value: number | null; label: string }) {
  if (value === null) return <span>No data for the previous period</span>;
  const up = value >= 0;
  return (
    <span className={up ? "text-emerald-700" : "text-red-700"}>
      {up ? "▲" : "▼"} {Math.abs(value).toFixed(1)}% <span className="text-ink-muted">{label}</span>
    </span>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="mb-4 flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          type="button"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium",
            value === t.value ? "border-brand-600 text-brand-700" : "border-transparent text-ink-muted hover:text-ink",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
