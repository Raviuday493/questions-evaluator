"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Archive, CheckCircle2, Database, FileStack, Gauge, Loader2, UserPlus, Users } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { BarList, DateRangeControl } from "@/components/charts/Bars";
import { TrendChart } from "@/components/charts/Charts";
import { ChangeHint, PageHeader, PaperStatusBadge, StatCard } from "@/components/ui/common";
import { ErrorState } from "@/components/ui/feedback";
import { Card, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useUrlState } from "@/hooks/useUrlState";
import { STATUS_LABELS, formatBytes, formatNumber, formatPercent, formatRelative, humanize } from "@/utils/format";
import type { PaperStatus } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  APPROVED: "#0ca30c", COMPLETED: "#2a78d6", FAILED: "#d03b3b", QUEUED: "#fab219", PARSING: "#1baf7a", EMBEDDING: "#1baf7a", MATCHING: "#1baf7a",
};
const TIER_COLORS: Record<string, string> = { EXACT: "#d03b3b", PARAPHRASED: "#ec835a", CONCEPTUAL: "#fab219" };

function Kpis() {
  const q = useQuery({ queryKey: ["dashboard", "summary"], queryFn: adminApi.dashboard.summary, refetchInterval: 60_000 });
  if (q.isLoading) {
    return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)}</div>;
  }
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} compact /></Card>;
  const { users, papers, content } = q.data;
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard label="Total users" value={formatNumber(users.total)} icon={<Users size={16} />} href="/users"
        hint={`${formatNumber(users.active)} active · ${formatNumber(users.signed_in_30d)} signed in (30d)`} />
      <StatCard label="New users (30 days)" value={formatNumber(users.new_30d)} icon={<UserPlus size={16} />}
        hint={<ChangeHint value={users.new_30d_change_percent} label="vs previous 30 days" />} />
      <StatCard label="Draft uploads (30 days)" value={formatNumber(papers.uploads_30d)} icon={<FileStack size={16} />} href="/papers?archive=false"
        hint={<ChangeHint value={papers.uploads_30d_change_percent} label="vs previous 30 days" />} />
      <StatCard label="Average originality" value={formatPercent(papers.avg_originality)} icon={<Gauge size={16} />}
        hint={`${formatNumber(papers.analyzed)} analysed drafts`} />
      <StatCard label="Approved for archive" value={formatNumber(papers.approved)} icon={<CheckCircle2 size={16} />} href="/papers?status=APPROVED"
        hint={`${formatNumber(papers.drafts_total)} drafts in total`} />
      <StatCard label="Historical archive" value={formatNumber(papers.archive_total)} icon={<Archive size={16} />} href="/papers?archive=true"
        hint={`${formatNumber(content.questions)} questions · ${formatNumber(content.matches)} matches`} />
      <StatCard label="Analyses in progress" value={formatNumber(papers.in_progress)} icon={<Loader2 size={16} />} href="/papers?status=QUEUED,PARSING,EMBEDDING,MATCHING"
        tone={papers.stuck ? "warn" : "default"} hint={papers.stuck ? `${papers.stuck} stuck — needs attention` : "No stuck jobs"} />
      <StatCard label="Failed analyses" value={formatNumber(papers.failed)} icon={<AlertTriangle size={16} />} href="/papers?status=FAILED"
        tone={papers.failed_7d ? "danger" : "default"} hint={`${formatNumber(papers.failed_7d)} in the last 7 days · storage ${formatBytes(content.storage_bytes)}`} />
    </div>
  );
}

function Trends() {
  const [state, setState] = useUrlState({ range: "30d", from: "", to: "" });
  const ready = state.range !== "custom" || Boolean(state.from && state.to && state.from <= state.to);
  const params = state.range === "custom" ? state : { range: state.range };
  const q = useQuery({ queryKey: ["dashboard", "ts", params], queryFn: () => adminApi.dashboard.timeseries(params), enabled: ready });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Activity over time</h2>
        <DateRangeControl range={state.range} from={state.from} to={state.to} onChange={(n) => setState(n)} />
      </div>
      {!ready ? (
        <Card><p className="py-6 text-center text-sm text-ink-muted">Choose a valid start and end date.</p></Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title="Paper analyses">
            {q.isLoading ? <Skeleton className="h-[290px]" /> : q.isError || !q.data ? <ErrorState error={q.error} onRetry={() => q.refetch()} compact /> : (
              <TrendChart labels={q.data.labels} bucket={q.data.bucket} data={q.data.series}
                series={[{ key: "uploads", label: "Draft uploads" }, { key: "approvals", label: "Approvals" }, { key: "failed", label: "Failures" }]} />
            )}
          </Card>
          <Card title="Accounts">
            {q.isLoading ? <Skeleton className="h-[290px]" /> : q.isError || !q.data ? <ErrorState error={q.error} onRetry={() => q.refetch()} compact /> : (
              <TrendChart labels={q.data.labels} bucket={q.data.bucket} data={q.data.series}
                series={[{ key: "logins", label: "User sign-ins" }, { key: "signups", label: "New users" }]} />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

function Distributions() {
  const q = useQuery({ queryKey: ["dashboard", "distribution"], queryFn: adminApi.dashboard.distribution });
  if (q.isError) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} compact /></Card>;
  const d = q.data;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card title="Papers by status">
        {!d ? <Skeleton className="h-40" /> : (
          <BarList items={Object.entries(d.paper_status).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: STATUS_LABELS[k as PaperStatus] ?? k, value: v, color: STATUS_COLORS[k] }))} />
        )}
      </Card>
      <Card title="Papers by department">
        {!d ? <Skeleton className="h-40" /> : (
          <BarList items={d.papers_by_department.map((x) => ({ label: `${x.code} · ${x.name}`, value: x.count }))} />
        )}
      </Card>
      <Card title="Similarity matches by tier">
        {!d ? <Skeleton className="h-40" /> : (
          <BarList emptyText="No matches recorded yet"
            items={["EXACT", "PARAPHRASED", "CONCEPTUAL"].filter((t) => d.match_tiers[t]).map((t) => ({ label: humanize(t), value: d.match_tiers[t], color: TIER_COLORS[t] }))} />
        )}
      </Card>
    </div>
  );
}

function RecentActivity() {
  const { can } = useAdmin();
  const q = useQuery({ queryKey: ["dashboard", "activity"], queryFn: adminApi.dashboard.activity, refetchInterval: 60_000 });
  if (q.isError) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} compact /></Card>;
  const d = q.data;
  const row = "flex items-start justify-between gap-3 py-2 text-sm";
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {can("papers.view") && (
        <Card title="Recent uploads" actions={<Link href="/papers" className="text-xs font-medium text-brand-600 hover:underline">View all</Link>}>
          {!d ? <Skeleton className="h-40" /> : !d.recent_uploads.length ? <p className="text-sm text-ink-muted">No uploads yet.</p> : (
            <ul className="divide-y divide-line">
              {d.recent_uploads.map((p) => (
                <li key={p.id} className={row}>
                  <Link href={`/papers/${p.id}`} className="min-w-0 hover:underline">
                    <span className="font-medium text-ink">{p.course_code}</span>
                    <span className="text-ink-muted"> · {p.is_historical_archive ? "archive" : "draft"} by {p.uploader_name ?? "unknown"}</span>
                  </Link>
                  <span className="flex shrink-0 items-center gap-2"><PaperStatusBadge status={p.status} /><span className="text-xs text-ink-faint">{formatRelative(p.created_at)}</span></span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {can("papers.view") && (
        <Card title="Recent failures" actions={<Link href="/papers?status=FAILED" className="text-xs font-medium text-brand-600 hover:underline">View all</Link>}>
          {!d ? <Skeleton className="h-40" /> : !d.recent_failures.length ? <p className="text-sm text-ink-muted">No failed analyses. 🎉</p> : (
            <ul className="divide-y divide-line">
              {d.recent_failures.map((p) => (
                <li key={p.id} className={row}>
                  <Link href={`/papers/${p.id}`} className="min-w-0 hover:underline">
                    <span className="font-medium text-ink">{p.course_code}</span>
                    <span className="block truncate text-xs text-ink-muted">{p.error_message ?? "No error message"}</span>
                  </Link>
                  <span className="shrink-0 text-xs text-ink-faint">{formatRelative(p.updated_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {can("users.view") && (
        <Card title="New users" actions={<Link href="/users" className="text-xs font-medium text-brand-600 hover:underline">View all</Link>}>
          {!d ? <Skeleton className="h-40" /> : !d.recent_signups.length ? <p className="text-sm text-ink-muted">No users yet.</p> : (
            <ul className="divide-y divide-line">
              {d.recent_signups.map((u) => (
                <li key={u.id} className={row}>
                  <Link href={`/users/${u.id}`} className="min-w-0 hover:underline">
                    <span className="font-medium text-ink">{u.full_name}</span>
                    <span className="block truncate text-xs text-ink-muted">{u.email}</span>
                  </Link>
                  <span className="shrink-0 text-xs text-ink-faint">{formatRelative(u.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {can("audit.view") && (
        <Card title="Recent admin actions" actions={<Link href="/audit-logs?actor_type=admin" className="text-xs font-medium text-brand-600 hover:underline">Audit log</Link>}>
          {!d ? <Skeleton className="h-40" /> : !d.recent_admin_actions.length ? <p className="text-sm text-ink-muted">No admin actions recorded.</p> : (
            <ul className="divide-y divide-line">
              {d.recent_admin_actions.map((a) => (
                <li key={a.id} className={row}>
                  <span className="min-w-0"><span className="font-medium text-ink">{humanize(a.action)}</span><span className="text-ink-muted"> · {a.admin_name}</span></span>
                  <span className="shrink-0 text-xs text-ink-faint">{formatRelative(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequirePermission permission="dashboard.view">
      <PageHeader title="Dashboard" description="Live overview of accounts, paper analyses and the historical archive." />
      <div className="space-y-6">
        <Kpis />
        <Trends />
        <Distributions />
        <RecentActivity />
        <p className="flex items-center gap-1.5 text-xs text-ink-faint"><Database size={12} aria-hidden /> All figures are computed live from the application database.</p>
      </div>
    </RequirePermission>
  );
}
