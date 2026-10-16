"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, OctagonX, RotateCcw, Trash2 } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { BarList } from "@/components/charts/Bars";
import { OriginalityValue, PageHeader, PaperStatusBadge, StatCard, Tabs } from "@/components/ui/common";
import { ErrorState, useConfirm, useToast } from "@/components/ui/feedback";
import { Badge, Button, Card, DetailList, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { formatBytes, formatDateTime, formatNumber, humanize } from "@/utils/format";

const TIER_TONE: Record<string, "red" | "orange" | "amber"> = { EXACT: "red", PARAPHRASED: "orange", CONCEPTUAL: "amber" };

function numericEntries(obj: Record<string, unknown> | undefined): [string, number][] {
  return Object.entries(obj ?? {}).filter((e): e is [string, number] => typeof e[1] === "number");
}

/** Distributions are stored as {total, counts: {...}, percentages: {...}}. */
function counts(dist: Record<string, unknown> | undefined): [string, number][] {
  const inner = dist?.counts;
  return numericEntries(inner && typeof inner === "object" ? (inner as Record<string, unknown>) : dist).filter(([, v]) => v > 0);
}

interface UnitCoverage { unit_number: number; title: string; status: string; actual_percent: number; target_percent: number; question_count: number }

function unitRows(coverage: unknown): UnitCoverage[] {
  const units = (coverage as { units?: unknown })?.units;
  return Array.isArray(units) ? (units as UnitCoverage[]) : [];
}

function PaperDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const [tab, setTab] = useState<"questions" | "report" | "details">("questions");
  const [downloading, setDownloading] = useState(false);
  const q = useQuery({
    queryKey: ["paper", id],
    queryFn: () => adminApi.papers.get(id),
    refetchInterval: (query) => (query.state.data && ["QUEUED", "PARSING", "EMBEDDING", "MATCHING"].includes(query.state.data.status) && !query.state.data.is_stuck ? 3000 : false),
  });

  const act = (fn: () => Promise<unknown>, success: string) => async () => {
    try {
      await fn();
      toast.success(success);
      client.invalidateQueries({ queryKey: ["paper", id] });
      client.invalidateQueries({ queryKey: ["papers"] });
      client.invalidateQueries({ queryKey: ["dashboard"] });
    } catch (e) {
      toast.error(e);
      throw e;
    }
  };

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-64" /></div>;
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>;
  const p = q.data;
  const report = p.report;

  return (
    <>
      <PageHeader
        back={{ href: "/papers", label: "Question papers" }}
        title={`${p.course?.code ?? "Paper"} · ${p.exam_type}`}
        description={<span className="inline-flex flex-wrap items-center gap-2">{p.term} {p.academic_year} <PaperStatusBadge status={p.status} stuck={p.is_stuck} />{p.is_historical_archive && <Badge>Historical archive</Badge>}</span>}
        actions={
          <>
            {can("papers.download") && (
              <Button icon={<Download size={14} />} loading={downloading} onClick={async () => {
                setDownloading(true);
                try {
                  await adminApi.papers.download(p.id, p.original_filename);
                } catch (e) {
                  toast.error(e, "Download failed");
                } finally {
                  setDownloading(false);
                }
              }}>Original file</Button>
            )}
            {can("papers.manage") && p.can_reanalyze && (
              <Button icon={<RotateCcw size={14} />} onClick={() => ask({
                title: "Re-analyse this paper?",
                message: "The paper is re-queued and its current report is replaced when the analysis finishes.",
                confirmLabel: "Re-analyse",
              }, act(() => adminApi.papers.reanalyze(p.id), "Paper queued for analysis."))}>Re-analyse</Button>
            )}
            {can("papers.manage") && p.can_approve && (
              <Button variant="primary" icon={<CheckCircle2 size={14} />} onClick={() => ask({
                title: "Approve for the exam archive?",
                message: "Approved papers join the historical archive that future drafts are compared against, and faculty can no longer delete them.",
                confirmLabel: "Approve",
              }, act(() => adminApi.papers.approve(p.id), "Paper approved."))}>Approve</Button>
            )}
            {can("papers.manage") && p.can_mark_failed && (
              <Button icon={<OctagonX size={14} />} onClick={() => ask({
                title: "Mark this analysis as failed?",
                message: "Use this for jobs that are stuck. The uploader can then retry the analysis.",
                confirmLabel: "Mark as failed",
                danger: true,
                reasonLabel: "Message shown to the uploader",
              }, (reason) => act(() => adminApi.papers.markFailed(p.id, reason.trim().length >= 3 ? reason.trim() : "Marked as failed by an administrator."), "Analysis marked as failed.")())}>Mark failed</Button>
            )}
            {can("papers.delete") && p.can_delete && (
              <Button variant="danger" icon={<Trash2 size={14} />} onClick={() => ask({
                title: "Delete this paper permanently?",
                message: (
                  <>
                    <p>The paper, its {p.questions.length} questions, report and stored file are removed.</p>
                    {p.times_matched_by_other_drafts > 0 && (
                      <p className="mt-2 font-medium text-red-700">Other drafts&apos; reports reference this paper {p.times_matched_by_other_drafts} time(s); those matches will be removed.</p>
                    )}
                  </>
                ),
                confirmLabel: "Delete paper",
                danger: true,
                typeToConfirm: p.course?.code ?? "DELETE",
              }, async () => {
                try {
                  await adminApi.papers.remove(p.id);
                  toast.success("Paper deleted.");
                  client.invalidateQueries({ queryKey: ["papers"] });
                  router.replace("/papers");
                } catch (e) {
                  toast.error(e, "Could not delete paper");
                  throw e;
                }
              })}>Delete</Button>
            )}
          </>
        }
      />

      {p.status === "FAILED" && p.error_message && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert"><strong>Analysis failed:</strong> {p.error_message}</div>
      )}
      {["QUEUED", "PARSING", "EMBEDDING", "MATCHING"].includes(p.status) && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          {p.current_step ?? "In progress"} — {p.progress_percent}%{p.is_stuck && " · no progress for a while; consider marking it as failed."}
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Originality" value={<OriginalityValue value={report?.originality_score} />} />
        <StatCard label="Questions" value={formatNumber(report?.total_questions ?? p.questions.length)} />
        <StatCard label="Matched questions" value={report ? formatNumber(report.matched_questions_count) : "—"} />
        <StatCard label={p.is_historical_archive ? "Times matched by drafts" : "Processing time"} value={p.is_historical_archive ? formatNumber(p.times_matched_by_other_drafts) : report?.processing_seconds ? `${report.processing_seconds.toFixed(1)} s` : "—"} />
      </div>

      <Tabs value={tab} onChange={setTab} tabs={[{ value: "questions", label: `Questions (${p.questions.length})` }, { value: "report", label: "Report" }, { value: "details", label: "Details" }]} />

      {tab === "questions" && (
        <Card padded={false}>
          {!p.questions.length ? <p className="p-6 text-center text-sm text-ink-muted">No questions extracted{p.status === "FAILED" ? " (the analysis failed)" : " yet"}.</p> : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-ink-muted">
                  <tr><th className="px-3 py-2 font-medium">#</th><th className="px-3 py-2 font-medium">Question</th><th className="px-3 py-2 font-medium">Marks</th><th className="px-3 py-2 font-medium">Classification</th><th className="px-3 py-2 font-medium">Best match</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {p.questions.map((question) => (
                    <tr key={question.id} className="align-top">
                      <td className="whitespace-nowrap px-3 py-2.5 font-medium text-ink">{question.question_number}</td>
                      <td className="max-w-[520px] px-3 py-2.5 text-ink-soft">{question.section_name && <span className="mb-0.5 block text-xs text-ink-faint">{question.section_name}</span>}{question.text}</td>
                      <td className="px-3 py-2.5 tabular-nums">{question.marks}</td>
                      <td className="px-3 py-2.5 text-xs text-ink-muted">
                        {humanize(question.question_type)}<br />{humanize(question.blooms_level)}
                        {question.unit && <><br />Unit {question.unit.unit_number}: {question.unit.title}</>}
                      </td>
                      <td className="px-3 py-2.5">
                        {question.best_match ? (
                          <div className="space-y-1">
                            <Badge tone={TIER_TONE[question.best_match.match_tier] ?? "neutral"}>{humanize(question.best_match.match_tier)} · {(question.best_match.composite_score * 100).toFixed(0)}%</Badge>
                            <Link href={`/papers/${question.best_match.source_paper_id}`} className="block text-xs text-brand-600 hover:underline">{question.best_match.source_label}</Link>
                          </div>
                        ) : <span className="text-xs text-ink-faint">Original</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === "report" && (!report ? <Card><p className="py-6 text-center text-sm text-ink-muted">No report yet.</p></Card> : (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card title="Match severity">
            <BarList emptyText="No repeated questions found" items={numericEntries(report.severity_breakdown).filter(([, v]) => v > 0).map(([k, v]) => ({ label: humanize(k), value: v }))} />
          </Card>
          <Card title="Bloom's taxonomy">
            <BarList items={counts(report.blooms_distribution).map(([k, v]) => ({ label: humanize(k), value: v }))} />
          </Card>
          <Card title="Question formats">
            <BarList items={counts(report.question_types).map(([k, v]) => ({ label: humanize(k), value: v }))} />
          </Card>
          <Card title="Syllabus unit coverage" className="lg:col-span-3" padded={false}>
            {!unitRows(report.unit_coverage).length ? <p className="p-4 text-sm text-ink-muted">This course has no syllabus units, so coverage was not computed.</p> : (
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-ink-muted">
                  <tr><th className="px-4 py-2 font-medium">Unit</th><th className="px-4 py-2 text-right font-medium">Questions</th><th className="px-4 py-2 text-right font-medium">Target</th><th className="px-4 py-2 text-right font-medium">Actual</th><th className="px-4 py-2 font-medium">Status</th></tr>
                </thead>
                <tbody className="divide-y divide-line tabular-nums">
                  {unitRows(report.unit_coverage).map((u) => (
                    <tr key={u.unit_number}>
                      <td className="px-4 py-2">{u.unit_number}. {u.title}</td>
                      <td className="px-4 py-2 text-right">{u.question_count}</td>
                      <td className="px-4 py-2 text-right">{u.target_percent.toFixed(0)}%</td>
                      <td className="px-4 py-2 text-right">{u.actual_percent.toFixed(1)}%</td>
                      <td className="px-4 py-2"><Badge tone={u.status === "BALANCED" ? "green" : "amber"}>{humanize(u.status)}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <Card title="Recommendations" className="lg:col-span-2">
            {!report.recommendations.length ? <p className="text-sm text-ink-muted">No recommendations.</p> : (
              <ol className="space-y-3 text-sm">
                {report.recommendations.map((r) => (
                  <li key={r.priority} className="flex gap-3">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">{r.priority}</span>
                    <div><p className="font-medium text-ink">{r.action_text}</p><p className="text-ink-muted">{r.rationale}</p><Badge className="mt-1">{humanize(r.category)}</Badge></div>
                  </li>
                ))}
              </ol>
            )}
          </Card>
          <Card title="Scan">
            <DetailList items={Object.entries(report.scan).filter(([, v]) => typeof v !== "object" || v === null).map(([k, v]) => ({ label: humanize(k), value: String(v ?? "—") }))} />
            <p className="mt-3 text-xs text-ink-faint">Generated {formatDateTime(report.generated_at)}</p>
          </Card>
        </div>
      ))}

      {tab === "details" && (
        <Card>
          <DetailList items={[
            { label: "Course", value: p.course ? <Link className="text-brand-600 hover:underline" href={`/courses/${p.course.id}`}>{p.course.code} · {p.course.title}</Link> : "—" },
            { label: "Department", value: p.department ? `${p.department.code} · ${p.department.name}` : "—" },
            { label: "Uploaded by", value: p.uploader ? <Link className="text-brand-600 hover:underline" href={`/users/${p.uploader.id}`}>{p.uploader.full_name} ({p.uploader.email})</Link> : "—" },
            { label: "Uploaded", value: formatDateTime(p.created_at) },
            { label: "Last updated", value: formatDateTime(p.updated_at) },
            { label: "Total marks", value: p.total_marks },
            { label: "File", value: `${p.original_filename} · ${p.file_mime_type.includes("pdf") ? "PDF" : "DOCX"} · ${formatBytes(p.file_size_bytes)}` },
            { label: "Approved", value: p.approved_at ? `${formatDateTime(p.approved_at)}${p.approved_by ? ` by ${p.approved_by.full_name}` : " (by an administrator)"}` : "—" },
            { label: "Revision of", value: p.previous_paper_id ? <Link className="text-brand-600 hover:underline" href={`/papers/${p.previous_paper_id}`}>Previous draft</Link> : "—" },
            { label: "Revisions", value: p.revisions.length ? p.revisions.map((r, i) => <Link key={r.id} className="mr-2 text-brand-600 hover:underline" href={`/papers/${r.id}`}>Revision {i + 1}</Link>) : "—" },
            { label: "Paper ID", value: <code className="text-xs text-ink-muted">{p.id}</code> },
            ...(can("audit.view") ? [{ label: "History", value: <Link className="text-brand-600 hover:underline" href={`/audit-logs?entity_id=${p.id}`}>View audit trail</Link> }] : []),
          ]} />
        </Card>
      )}
      {dialog}
    </>
  );
}

export default function PaperDetailPage() {
  return <RequirePermission permission="papers.view"><PaperDetail /></RequirePermission>;
}
