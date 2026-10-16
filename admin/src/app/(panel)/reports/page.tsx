"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { BarList, DateRangeControl } from "@/components/charts/Bars";
import { OriginalityValue, PageHeader } from "@/components/ui/common";
import { ErrorState, useToast } from "@/components/ui/feedback";
import { Button, Card, Select, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useUrlState } from "@/hooks/useUrlState";
import { STATUS_LABELS, formatDate, formatNumber, humanize } from "@/utils/format";
import type { PaperStatus } from "@/types";

const BLOOMS_ORDER = ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"];

function ExportButton({ kind, params, label }: { kind: string; params: Record<string, string>; label: string }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <Button size="sm" loading={busy} icon={<Download size={14} />} onClick={async () => {
      setBusy(true);
      try {
        await adminApi.reports.export(kind, params);
        toast.success(`${label} exported.`);
      } catch (e) {
        toast.error(e, "Export failed");
      } finally {
        setBusy(false);
      }
    }}>CSV</Button>
  );
}

function OriginalityTable({ rows, first, extra }: {
  rows: { key: string; label: React.ReactNode; papers: number; avg: number | null; min: number | null; max: number | null; matched: number; extra?: React.ReactNode }[];
  first: string;
  extra?: string;
}) {
  if (!rows.length) return <p className="p-4 text-sm text-ink-muted">No analysed draft papers in this period.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-ink-muted">
          <tr>
            <th className="px-4 py-2 font-medium">{first}</th>
            {extra && <th className="px-4 py-2 font-medium">{extra}</th>}
            <th className="px-4 py-2 text-right font-medium">Papers</th>
            <th className="px-4 py-2 text-right font-medium">Avg originality</th>
            <th className="px-4 py-2 text-right font-medium">Range</th>
            <th className="px-4 py-2 text-right font-medium">Matched Qs</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line tabular-nums">
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="px-4 py-2">{r.label}</td>
              {extra && <td className="px-4 py-2">{r.extra}</td>}
              <td className="px-4 py-2 text-right">{formatNumber(r.papers)}</td>
              <td className="px-4 py-2 text-right"><OriginalityValue value={r.avg} /></td>
              <td className="px-4 py-2 text-right text-ink-muted">{r.min === null ? "—" : `${r.min.toFixed(0)}–${r.max?.toFixed(0)}%`}</td>
              <td className="px-4 py-2 text-right">{formatNumber(r.matched)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Reports() {
  const { can } = useAdmin();
  const [state, setState] = useUrlState({ range: "90d", from: "", to: "", department_id: "" });
  const ready = state.range !== "custom" || Boolean(state.from && state.to && state.from <= state.to);
  const params: Record<string, string> = state.range === "custom" ? { ...state } : { range: state.range, department_id: state.department_id };
  const q = useQuery({ queryKey: ["reports", params], queryFn: () => adminApi.reports.overview(params), enabled: ready });
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => adminApi.departments.list(), enabled: can("catalog.view") });
  const d = q.data;
  const exportable = can("reports.export");

  return (
    <>
      <PageHeader title="Reports" description="Originality, repetition and question-design analytics aggregated from analysed papers."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <DateRangeControl range={state.range} from={state.from} to={state.to} onChange={(n) => setState(n)} />
            {departments.data && (
              <Select aria-label="Department" className="h-8 w-auto" value={state.department_id} onChange={(e) => setState({ department_id: e.target.value })}>
                <option value="">All departments</option>
                {departments.data.map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}
              </Select>
            )}
          </div>
        } />
      {!ready ? <Card><p className="py-6 text-center text-sm text-ink-muted">Choose a valid start and end date.</p></Card>
        : q.isError ? <Card><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>
        : !d ? <div className="grid gap-4 lg:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-56" />)}</div>
        : (
          <div className="space-y-4">
            <p className="text-xs text-ink-muted">Papers uploaded {formatDate(d.from)} – {formatDate(d.to)} (UTC). Originality covers analysed drafts only; the archive is excluded.</p>
            <div className="grid gap-4 lg:grid-cols-4">
              <Card title="Status of uploads">
                <BarList items={Object.entries(d.status_breakdown).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: STATUS_LABELS[k as PaperStatus] ?? k, value: v }))} />
              </Card>
              <Card title="Repeated-question tiers">
                <BarList emptyText="No matches in this period" items={["EXACT", "PARAPHRASED", "CONCEPTUAL"].filter((t) => d.match_tiers[t]).map((t) => ({ label: humanize(t), value: d.match_tiers[t] }))} />
              </Card>
              <Card title="Bloom's levels">
                <BarList items={BLOOMS_ORDER.filter((b) => d.blooms_levels[b]).map((b) => ({ label: humanize(b), value: d.blooms_levels[b] }))} />
              </Card>
              <Card title="Question formats">
                <BarList items={Object.entries(d.question_types).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: humanize(k), value: v }))} />
              </Card>
            </div>
            <Card title="Originality by department" padded={false} actions={exportable && <ExportButton kind="departments" params={params} label="Department report" />}>
              <OriginalityTable first="Department" rows={d.by_department.map((x) => ({
                key: x.code, label: <span><span className="font-medium">{x.code}</span> <span className="text-ink-muted">{x.name}</span></span>,
                papers: x.papers, avg: x.avg_originality, min: x.min_originality, max: x.max_originality, matched: x.matched_questions,
              }))} />
            </Card>
            <Card title="Originality by course" padded={false} actions={exportable && <ExportButton kind="courses" params={params} label="Course report" />}>
              <OriginalityTable first="Course" extra="Department" rows={d.by_course.map((x) => ({
                key: x.course_id, label: <Link href={`/courses/${x.course_id}`} className="hover:underline"><span className="font-medium">{x.code}</span> <span className="text-ink-muted">{x.title}</span></Link>,
                extra: x.department_code, papers: x.papers, avg: x.avg_originality, min: x.min_originality, max: x.max_originality, matched: x.matched_questions,
              }))} />
            </Card>
            <Card title="Most active uploaders" padded={false} actions={exportable && <ExportButton kind="uploaders" params={params} label="Uploader report" />}>
              {!d.top_uploaders.length ? <p className="p-4 text-sm text-ink-muted">No draft uploads in this period.</p> : (
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-ink-muted">
                    <tr><th className="px-4 py-2 font-medium">User</th><th className="px-4 py-2 text-right font-medium">Draft papers</th><th className="px-4 py-2 text-right font-medium">Avg originality</th></tr>
                  </thead>
                  <tbody className="divide-y divide-line tabular-nums">
                    {d.top_uploaders.map((u) => (
                      <tr key={u.user_id}>
                        <td className="px-4 py-2"><Link href={`/users/${u.user_id}`} className="hover:underline"><span className="font-medium">{u.full_name}</span> <span className="text-ink-muted">{u.email}</span></Link></td>
                        <td className="px-4 py-2 text-right">{u.papers}</td>
                        <td className="px-4 py-2 text-right"><OriginalityValue value={u.avg_originality} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>
        )}
    </>
  );
}

export default function ReportsPage() {
  return <RequirePermission permission="reports.view"><Reports /></RequirePermission>;
}
