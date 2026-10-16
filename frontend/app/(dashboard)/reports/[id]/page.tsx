"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, Download, GitBranch, Lightbulb, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import { EmptyState, ErrorState, LoadingState } from "@/components/layout/StateViews";
import { ApiError, api, errorText } from "@/lib/api";
import { TIER_LABELS, formatDate, originalityBand, tierClasses, titleCase } from "@/lib/format";
import type { MatchedQuestion, Report } from "@/lib/types";

function scopeDescription(report: Report): string {
  const scan = report.scan;
  if (scan.scope === "NONE" || !scan.historical_papers_searched) {
    return `First paper for ${report.paper.course_code}: no historical papers are archived yet, so nothing could be repeated.`;
  }
  const range = scan.archive_year_range ? ` (${scan.archive_year_range})` : "";
  const where = scan.scope === "DEPARTMENT" ? "department-wide question bank" : "historical course archives";
  return `Questions matched from ${where}${range}`;
}

function MatchCard({ match, selected, onSelect }: { match: MatchedQuestion; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left rounded-xl border p-4 transition-all ${
        selected ? "border-accent ring-4 ring-accent/10 bg-blue-50/40" : "border-slate-200 hover:border-slate-300 bg-white"
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-semibold text-slate-900 text-sm">Q{match.question_number}</span>
        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${tierClasses(match.match_tier)}`}>
          {Math.round(match.composite_score * 100)}% · {TIER_LABELS[match.match_tier]}
        </span>
      </div>
      <p className="text-sm text-slate-700 line-clamp-2">{match.draft_text}</p>
      <div className="mt-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">
          {match.source.course_code} · {match.source_paper} · Q{match.source.question_number}
        </div>
        <p className="text-sm text-slate-600 line-clamp-3">{match.source.text}</p>
      </div>
      {match.other_matches.length > 0 && (
        <p className="text-xs text-slate-500 mt-2">
          Also similar to: {match.other_matches.map((m) => `${m.source_paper} Q${m.source.question_number}`).join(", ")}
        </p>
      )}
    </button>
  );
}

export default function ReportPage({ params }: { params: { id: string } }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const questionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const report = useQuery({ queryKey: ["report", params.id], queryFn: () => api.report(params.id) });
  const approve = useMutation({
    mutationFn: api.approvePaper,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report", params.id] });
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });

  const selectQuestion = (questionId: string) => {
    setSelectedId(questionId);
    questionRefs.current[questionId]?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  if (report.isLoading) return <LoadingState label="Loading report..." />;
  if (report.isError) {
    const notFound = report.error instanceof ApiError && report.error.status === 404;
    return (
      <div className="flex flex-col gap-4">
        <Link href="/dashboard" className="text-sm text-accent font-semibold flex items-center gap-1">
          <ArrowLeft size={16} /> Back to dashboard
        </Link>
        <ErrorState
          message={notFound ? "This report does not exist or you do not have access to it." : errorText(report.error)}
          onRetry={notFound ? undefined : () => report.refetch()}
        />
      </div>
    );
  }

  const data = report.data!;
  const paper = data.paper;
  const band = originalityBand(data.originality_score);
  const delta = data.previous_report ? data.originality_score - data.previous_report.originality_score : null;
  const canRevise = paper.can_manage && !paper.is_historical_archive;

  const onApprove = () => {
    if (window.confirm("Approve this paper for the exam archive? Approved papers become part of the comparison pool and can no longer be deleted.")) {
      approve.mutate(paper.id);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" aria-label="Back to dashboard" className="p-2 rounded-full hover:bg-white text-slate-500">
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Originality & Match Report</h1>
            <p className="text-xs text-slate-500">
              {paper.course_code} {paper.exam_type} {paper.is_historical_archive ? "(Archive)" : "Draft"} · {paper.term}{" "}
              {paper.academic_year} · Report ID: {data.report_id}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={api.paperFileUrl(paper.id)}
            className="text-sm font-semibold px-4 py-2 rounded-full border border-slate-200 bg-white hover:bg-slate-50 flex items-center gap-2">
            <Download size={15} /> Original file
          </a>
          <Link href={`/insights?report=${data.report_id}`}
            className="text-sm font-semibold px-4 py-2 rounded-full border border-slate-200 bg-white hover:bg-slate-50 flex items-center gap-2">
            <Lightbulb size={15} /> Preparation insights
          </Link>
          {canRevise && paper.status !== "APPROVED" && (
            <Link href={`/upload?revisionOf=${paper.id}`}
              className="text-sm font-semibold px-4 py-2 rounded-full border border-slate-200 bg-white hover:bg-slate-50 flex items-center gap-2">
              <GitBranch size={15} /> Re-analyze revised draft
            </Link>
          )}
          {paper.status === "APPROVED" ? (
            <span className="text-sm font-semibold px-4 py-2 rounded-full bg-blue-50 text-accent flex items-center gap-2">
              <BadgeCheck size={15} /> Approved{paper.approved_at ? ` · ${formatDate(paper.approved_at)}` : ""}
            </span>
          ) : (
            paper.can_approve && paper.status === "COMPLETED" && !paper.is_historical_archive && (
              <button type="button" onClick={onApprove} disabled={approve.isPending}
                className="text-sm font-semibold px-4 py-2 rounded-full bg-accent text-white hover:bg-primary disabled:opacity-60 flex items-center gap-2">
                <BadgeCheck size={15} /> {approve.isPending ? "Approving..." : "Approve for Exam Archive"}
              </button>
            )
          )}
        </div>
      </header>

      {approve.isError && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3" role="alert">
          {errorText(approve.error)}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className={`qpi-card p-6 text-center border-t-4 ${band.border}`}>
          <h3 className="text-sm font-semibold text-slate-700 mb-2">Originality Score</h3>
          <div className="text-5xl font-bold text-slate-900 my-4">{Math.round(data.originality_score)}%</div>
          <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold ${band.classes}`}>
            <ShieldCheck size={14} /> {band.label}
          </span>
          {delta !== null && data.previous_report && (
            <Link href={`/reports/${data.previous_report.report_id}`}
              className={`mt-3 text-xs font-medium flex items-center justify-center gap-1 hover:underline ${delta >= 0 ? "text-emerald-600" : "text-red-600"}`}>
              {delta >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
              {delta >= 0 ? "+" : ""}{delta.toFixed(0)} pts vs previous draft ({Math.round(data.previous_report.originality_score)}%)
            </Link>
          )}
        </div>

        <div className="lg:col-span-2 qpi-card p-6 flex flex-col justify-between gap-3">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Identified Repetitions</h3>
          <div className={`text-5xl font-bold my-2 ${data.matched_questions_count ? "text-red-600" : "text-emerald-600"}`}>
            {data.matched_questions_count}
          </div>
          <p className="text-sm text-slate-500">{scopeDescription(data)}</p>
          <div className="flex flex-wrap gap-2 text-xs">
            {(["EXACT", "PARAPHRASED", "CONCEPTUAL"] as const).map((tier) => (
              <span key={tier} className={`px-2.5 py-1 rounded-full border font-semibold ${tierClasses(tier)}`}>
                {TIER_LABELS[tier]}: {data.severity_breakdown[tier] ?? 0}
              </span>
            ))}
          </div>
          <p className="text-xs text-slate-400">
            {data.total_questions} questions analysed · {data.scan.historical_papers_searched ?? 0} archived papers (
            {data.scan.historical_questions_searched ?? 0} questions) searched
            {data.processing_seconds !== null && ` · ${data.processing_seconds.toFixed(1)}s`}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <section className="qpi-card p-5 flex flex-col gap-3 lg:max-h-[75vh] lg:overflow-y-auto">
          <h2 className="text-base font-semibold text-slate-900">Matched Questions</h2>
          {data.matched_questions.length === 0 ? (
            <EmptyState title="No repeated questions found">
              Every question in this draft is original relative to the searched archive.
            </EmptyState>
          ) : (
            data.matched_questions.map((m) => (
              <MatchCard key={m.question_id} match={m} selected={selectedId === m.question_id}
                onSelect={() => selectQuestion(m.question_id)} />
            ))
          )}
        </section>

        <section className="qpi-card p-5 flex flex-col gap-2 lg:max-h-[75vh] lg:overflow-y-auto">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">Draft Paper</h2>
            <span className="text-xs text-slate-500 truncate max-w-[50%]" title={paper.original_filename}>{paper.original_filename}</span>
          </div>
          <div className="flex gap-3 text-[11px] text-slate-500">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-red-200" /> Exact / paraphrased</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-amber-200" /> Conceptual</span>
          </div>
          {data.questions.map((q, i) => {
            const prevSection = i > 0 ? data.questions[i - 1].section_name : null;
            const highlight =
              q.match_tier === "EXACT" || q.match_tier === "PARAPHRASED"
                ? "bg-red-50 border-red-200"
                : q.match_tier === "CONCEPTUAL"
                ? "bg-amber-50 border-amber-200"
                : "border-transparent";
            return (
              <div key={q.id}>
                {q.section_name && q.section_name !== prevSection && (
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mt-3 mb-1">{q.section_name}</div>
                )}
                <div
                  ref={(el) => {
                    questionRefs.current[q.id] = el;
                  }}
                  onClick={() => q.match_tier && setSelectedId(q.id)}
                  className={`rounded-lg border px-3 py-2 text-sm transition-all ${highlight} ${q.is_sub_question ? "ml-6" : ""} ${
                    selectedId === q.id ? "ring-4 ring-accent/20" : ""
                  } ${q.match_tier ? "cursor-pointer" : ""}`}
                >
                  <div className="flex justify-between gap-3">
                    <p className="text-slate-800">
                      <span className="font-semibold mr-1">{q.is_sub_question ? q.question_number.replace(/^\d+/, "") : `${q.question_number}.`}</span>
                      {q.text}
                    </p>
                    {q.marks > 0 && <span className="text-xs text-slate-500 whitespace-nowrap">[{q.marks}]</span>}
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {q.unit && <span className="px-1.5 py-0.5 rounded bg-slate-100">Unit {q.unit.unit_number}: {q.unit.title}</span>}
                    {q.blooms_level && <span className="px-1.5 py-0.5 rounded bg-slate-100">{titleCase(q.blooms_level)}</span>}
                    {q.question_type && <span className="px-1.5 py-0.5 rounded bg-slate-100">{titleCase(q.question_type)}</span>}
                    {q.match_tier && q.composite_score !== null && (
                      <span className={`px-1.5 py-0.5 rounded border ${tierClasses(q.match_tier)}`}>
                        {Math.round(q.composite_score * 100)}% {TIER_LABELS[q.match_tier]}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </div>
  );
}
