"use client";

import { Suspense, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Circle, Flame } from "lucide-react";
import { EmptyState, ErrorState, LoadingState } from "@/components/layout/StateViews";
import { ApiError, api, errorText } from "@/lib/api";
import { formatPercent, originalityBand, titleCase } from "@/lib/format";
import type { Distribution, Insights, Recommendation } from "@/lib/types";

const BLOOMS_ORDER = ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"];
const TYPE_ORDER = ["MCQ", "SHORT_ANSWER", "LONG_ESSAY", "NUMERICAL", "DERIVATION"];
const CATEGORY_LABELS: Record<Recommendation["category"], string> = {
  REPETITION_SWAP: "Replace repeated question",
  UNIT_REBALANCE: "Rebalance units",
  BLOOMS_ELEVATION: "Raise cognitive level",
  FORMAT_DIVERSIFICATION: "Diversify formats",
};

function freshnessSummary(insights: Insights): string {
  const scan = insights.scan;
  if (!scan.historical_papers_searched) {
    return "No historical papers are archived for this course yet, so the draft could not repeat earlier questions.";
  }
  const range = scan.archive_year_range ? ` from ${scan.archive_year_range}` : "";
  const pool = scan.scope === "DEPARTMENT" ? "department" : "course";
  const level =
    insights.draft_freshness_score >= 80 ? "high novelty" : insights.draft_freshness_score >= 60 ? "moderate novelty" : "substantial repetition";
  return `Your current draft indicates ${level} compared to ${scan.historical_papers_searched} archived ${pool} papers${range}.`;
}

function DistributionBars({ dist, order, highlight }: { dist: Distribution; order: string[]; highlight?: string[] }) {
  if (!dist.total) return <p className="text-sm text-slate-500">No questions classified.</p>;
  return (
    <ul className="flex flex-col gap-2.5">
      {order.map((key) => {
        const pct = dist.percentages[key] ?? 0;
        return (
          <li key={key}>
            <div className="flex justify-between text-xs mb-1">
              <span className="font-medium text-slate-700">{titleCase(key)}</span>
              <span className="text-slate-500">
                {dist.counts[key] ?? 0} · {pct.toFixed(0)}%
              </span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${highlight?.includes(key) ? "bg-emerald-500" : "bg-accent"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function InsightsView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const reportParam = params.get("report");

  const papers = useQuery({
    queryKey: ["papers", { status: "COMPLETED,APPROVED", limit: 50 }],
    queryFn: () => api.papers({ status: "COMPLETED,APPROVED", limit: 50 }),
  });
  const withReports = papers.data?.items.filter((p) => p.report_id) ?? [];
  const reportId = reportParam ?? withReports[0]?.report_id ?? null;

  // Keep the URL in sync so the selected paper survives a refresh.
  useEffect(() => {
    if (!reportParam && reportId) router.replace(`${pathname}?report=${reportId}`);
  }, [reportParam, reportId, pathname, router]);

  const insights = useQuery({
    queryKey: ["insights", reportId],
    queryFn: () => api.insights(reportId!),
    enabled: !!reportId,
  });

  const label = (p: { course_code: string; exam_type: string; term: string; academic_year: string; original_filename: string }) =>
    `${p.course_code} · ${p.exam_type} · ${p.term} ${p.academic_year} (${p.original_filename})`;
  const selectorOptions = withReports.map((p) => ({ reportId: p.report_id!, label: label(p) }));
  // A report opened via link (e.g. an archive paper) may not be in the user's own list.
  if (insights.data && !selectorOptions.some((o) => o.reportId === insights.data.report_id)) {
    selectorOptions.unshift({ reportId: insights.data.report_id, label: label(insights.data.paper) });
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap justify-between items-end gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Preparation Insights</h1>
          <p className="text-sm text-slate-500 mt-1">
            Analyze historical course data to optimize your upcoming question paper.
          </p>
        </div>
        {selectorOptions.length > 0 && (
          <label className="flex flex-col gap-1.5">
            <span className="qpi-label">Paper</span>
            <select
              value={reportId ?? ""}
              onChange={(e) => router.replace(`${pathname}?report=${e.target.value}`)}
              className="qpi-input min-w-[280px]"
            >
              {selectorOptions.map((o) => (
                <option key={o.reportId} value={o.reportId}>{o.label}</option>
              ))}
            </select>
          </label>
        )}
      </header>

      {papers.isLoading && !reportParam ? (
        <LoadingState label="Loading your papers..." />
      ) : papers.isError && !reportParam ? (
        <ErrorState message={errorText(papers.error)} onRetry={() => papers.refetch()} />
      ) : !reportId ? (
        <div className="qpi-card p-6">
          <EmptyState title="No analysed papers yet">
            <Link href="/upload" className="text-accent font-semibold hover:underline">Upload a draft</Link> to see syllabus
            balance, Bloom&apos;s taxonomy and next-paper recommendations.
          </EmptyState>
        </div>
      ) : insights.isLoading ? (
        <LoadingState label="Computing insights..." />
      ) : insights.isError ? (
        <ErrorState
          message={
            insights.error instanceof ApiError && insights.error.status === 404
              ? "These insights do not exist or you do not have access to them."
              : errorText(insights.error)
          }
          onRetry={() => insights.refetch()}
        />
      ) : (
        insights.data && <InsightsContent insights={insights.data} />
      )}
    </div>
  );
}

function InsightsContent({ insights }: { insights: Insights }) {
  const band = originalityBand(insights.draft_freshness_score);
  const units = insights.unit_coverage.units;
  const saturated = insights.overused_topics.filter((t) => t.saturated);

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        <div className="md:col-span-8 qpi-card p-6">
          <h3 className="text-base font-bold text-slate-900 mb-2">Proposed Draft Freshness</h3>
          <p className="text-sm text-slate-500 mb-4">{freshnessSummary(insights)}</p>
          <div className="flex items-end gap-4 flex-wrap">
            <div className="text-5xl font-bold text-slate-900">{Math.round(insights.draft_freshness_score)}%</div>
            <span className={`mb-2 px-3 py-1 rounded-full text-xs font-semibold ${band.classes}`}>{band.label}</span>
            <Link href={`/reports/${insights.report_id}`} className="mb-2 text-sm text-accent font-semibold hover:underline">
              View match report
            </Link>
          </div>
        </div>

        <div className="md:col-span-4 qpi-card p-6 border-t-4 border-t-accent">
          <h3 className="text-base font-bold text-slate-900 mb-3">Conceptual Gaps</h3>
          {!insights.has_syllabus ? (
            <p className="text-sm text-slate-500">
              No syllabus units are configured for {insights.paper.course_code}, so unit gaps cannot be computed.
            </p>
          ) : insights.conceptual_gaps.length === 0 ? (
            <p className="text-sm text-slate-500">Every syllabus unit has at least 10% of the marks.</p>
          ) : (
            <ul className="space-y-3 text-sm">
              {insights.conceptual_gaps.map((g) => (
                <li key={g.unit_id} className="flex items-start gap-2">
                  <Circle className="text-accent mt-0.5 shrink-0" size={14} />
                  <div>
                    <p className="font-semibold text-slate-900">Unit {g.unit_number}: {g.title}</p>
                    <p className="text-slate-500 text-xs">
                      {g.actual_percent}% of marks (target {g.target_percent}%) ·{" "}
                      {g.last_covered ? `Last covered: ${g.last_covered}` : "Not examined in the archive"}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <section className="qpi-card p-6">
        <h3 className="text-base font-bold text-slate-900 mb-1">Next-Paper Recommendations</h3>
        <p className="text-sm text-slate-500 mb-4">Prioritised actions for your next draft.</p>
        {insights.recommendations.length === 0 ? (
          <p className="text-sm text-slate-500">No changes recommended — this draft is well balanced and original.</p>
        ) : (
          <ol className="flex flex-col gap-3">
            {insights.recommendations.map((r) => (
              <li key={r.priority} className="flex gap-3 p-3 rounded-xl border border-slate-100 bg-slate-50/60">
                <span className="qpi-step shrink-0">{r.priority}</span>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-accent">{CATEGORY_LABELS[r.category]}</div>
                  <p className="font-semibold text-slate-900 text-sm">{r.action_text}</p>
                  <p className="text-sm text-slate-500">{r.rationale}</p>
                </div>
              </li>
            ))}
          </ol>
        )}
        {insights.paper.can_manage && !insights.paper.is_historical_archive && insights.paper.status !== "APPROVED" && (
          <Link href={`/upload?revisionOf=${insights.paper.id}`}
            className="inline-block mt-4 text-sm font-semibold text-accent hover:underline">
            Upload a revised draft for re-analysis →
          </Link>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="qpi-card p-6">
          <h3 className="text-base font-bold text-slate-900 mb-1">Unit / Topic Representation</h3>
          <p className="text-sm text-slate-500 mb-4">Share of marks per syllabus unit against its target weightage.</p>
          {units.length === 0 ? (
            <p className="text-sm text-slate-500">No syllabus units configured for this course.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {units.map((u) => (
                <li key={u.unit_id}>
                  <div className="flex justify-between text-xs mb-1 gap-2">
                    <span className="font-medium text-slate-700">Unit {u.unit_number}: {u.title}</span>
                    <span className={u.status === "OVER" ? "text-red-600 font-semibold" : u.status === "UNDER" ? "text-amber-600 font-semibold" : "text-slate-500"}>
                      {formatPercent(u.actual_percent)} / {formatPercent(u.target_percent)}
                      {u.status !== "BALANCED" && ` · ${u.status === "OVER" ? "Over" : "Under"}`}
                    </span>
                  </div>
                  <div className="relative h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${u.status === "OVER" ? "bg-red-500" : u.status === "UNDER" ? "bg-amber-400" : "bg-accent"}`}
                      style={{ width: `${Math.min(100, u.actual_percent)}%` }}
                    />
                    <div className="absolute top-0 h-full w-0.5 bg-slate-500" style={{ left: `${Math.min(100, u.target_percent)}%` }} title="Target" />
                  </div>
                </li>
              ))}
              {insights.unit_coverage.unassigned_percent > 0 && (
                <li className="text-xs text-slate-500">
                  {insights.unit_coverage.unassigned_percent}% of marks could not be mapped to a unit.
                </li>
              )}
            </ul>
          )}
        </section>

        <section className="qpi-card p-6">
          <h3 className="text-base font-bold text-slate-900 mb-1">5-Year Topic Saturation</h3>
          <p className="text-sm text-slate-500 mb-4">How often each unit appeared in recent archived exam terms.</p>
          {insights.overused_topics.length === 0 ? (
            <p className="text-sm text-slate-500">Not enough archived papers for this course to compute trends.</p>
          ) : (
            <>
              {saturated.length > 0 && (
                <div className="flex items-start gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-xl p-3 mb-4">
                  <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                  <span>
                    Saturated: {saturated.map((t) => `${t.title} (${t.cycles_tested} of last ${t.cycles_total} terms)`).join(", ")}
                  </span>
                </div>
              )}
              <ul className="flex flex-col gap-3">
                {insights.overused_topics.map((t) => (
                  <li key={t.unit_id}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-medium text-slate-700 flex items-center gap-1">
                        {t.saturated && <Flame size={12} className="text-red-500" />}
                        Unit {t.unit_number}: {t.title}
                      </span>
                      <span className="text-slate-500">{t.cycles_tested}/{t.cycles_total} terms</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${t.saturated ? "bg-red-500" : "bg-accent"}`}
                        style={{ width: `${(100 * t.cycles_tested) / t.cycles_total}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="qpi-card p-6">
          <h3 className="text-base font-bold text-slate-900 mb-1">Bloom&apos;s Taxonomy Balance</h3>
          <p className="text-sm text-slate-500 mb-4">
            {insights.blooms_distribution.total
              ? `${formatPercent(insights.blooms_distribution.higher_order_percent)} of questions test higher-order thinking (Apply and above).`
              : "Cognitive level of each question."}
          </p>
          <DistributionBars dist={insights.blooms_distribution} order={BLOOMS_ORDER}
            highlight={["APPLY", "ANALYZE", "EVALUATE", "CREATE"]} />
        </section>

        <section className="qpi-card p-6">
          <h3 className="text-base font-bold text-slate-900 mb-1">Question Format Breakdown</h3>
          <p className="text-sm text-slate-500 mb-4">Structural format of each question.</p>
          <DistributionBars dist={insights.question_types} order={TYPE_ORDER} />
        </section>
      </div>
    </>
  );
}

export default function InsightsPage() {
  return (
    <Suspense>
      <InsightsView />
    </Suspense>
  );
}
