"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ArrowUpDown, CalendarDays, CloudUpload, Download, FileText, RotateCw, Search, Trash2, X } from "lucide-react";
import { DashboardMetrics, DashboardSnapshot, DashboardWelcome } from "@/components/dashboard/DashboardOverview";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { exportPapersCsv } from "@/components/dashboard/exportPapersCsv";
import { EmptyState, ErrorState, LoadingState } from "@/components/layout/StateViews";
import { api, errorText } from "@/lib/api";
import { STATUS_LABELS, formatDate, formatPercent, isInProgress, statusBadgeClass } from "@/lib/format";
import type { PaperSummary } from "@/lib/types";

const PAGE_SIZE = 8;
const STATUS_FILTERS = [
  { value: "", label: "All statuses" },
  { value: "COMPLETED,APPROVED", label: "Analyzed" },
  { value: "QUEUED,PARSING,EMBEDDING,MATCHING", label: "In progress" },
  { value: "APPROVED", label: "Approved" },
  { value: "FAILED", label: "Failed" },
];

function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [sortValue, setSortValue] = useState("created_at:desc");
  const [notice, setNotice] = useState("");
  const [today, setToday] = useState("");
  const { data: user } = useCurrentUser();
  const [sort, order] = sortValue.split(":") as [string, "asc" | "desc"];
  useEffect(() => setToday(new Date().toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })), []);
  const [actionError, setActionError] = useState<string | null>(null);
  const debouncedSearch = useDebounced(search.trim());

  useEffect(() => setPage(1), [debouncedSearch, statusFilter, sortValue]);

  const stats = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: api.dashboardStats,
    refetchInterval: (q) => (q.state.data?.in_progress ? 3000 : 15000),
  });
  const papers = useQuery({
    queryKey: ["papers", { page, limit: PAGE_SIZE, search: debouncedSearch, status: statusFilter, sort, order }],
    queryFn: () => api.papers({ page, limit: PAGE_SIZE, search: debouncedSearch, status: statusFilter, sort, order }),
    placeholderData: keepPreviousData,
    // Keep polling while any listed paper is still being analysed.
    refetchInterval: (q) => (q.state.data?.items.some((p) => isInProgress(p.status)) ? 3000 : 15000),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["papers"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
  };
  const retry = useMutation({ mutationFn: api.reanalyzePaper, onSuccess: invalidate, onError: (e) => setActionError(errorText(e)) });
  const remove = useMutation({ mutationFn: api.deletePaper, onSuccess: invalidate, onError: (e) => setActionError(errorText(e)) });

  const onDelete = (p: PaperSummary) => {
    setActionError(null);
    if (window.confirm(`Delete ${p.course_code} ${p.exam_type} (${p.original_filename})? This cannot be undone.`)) {
      remove.mutate(p.id);
    }
  };

  useEffect(() => {
    if (papers.data && !papers.isPlaceholderData && page > papers.data.pages) setPage(papers.data.pages);
  }, [papers.data, papers.isPlaceholderData, page]);
  const applyStatus = (status: string) => {
    setStatusFilter(status);
    setSearch("");
    setPage(1);
    document.getElementById("submissions")?.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  };

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-500">Your teaching workspace</p>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px]">Welcome back{user?.full_name ? `, ${user.full_name.trim()}` : ""} <span aria-hidden="true" className="text-amber-500">✦</span></h1>
          <p className="mt-2 text-sm text-slate-500">Here&apos;s the big picture of your question papers.</p>
        </div>
        {today && <span className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs text-slate-600 sm:flex"><CalendarDays size={15} className="text-violet-500" />{today}</span>}
      </header>
      <DashboardWelcome />
      {stats.isError && <ErrorState message={errorText(stats.error)} onRetry={() => stats.refetch()} />}
      <DashboardMetrics stats={stats.data} onFilter={applyStatus} />
      <DashboardSnapshot stats={stats.data} onFilter={applyStatus} />

      <section id="submissions" aria-labelledby="library-title" className="qpi-card min-w-0 scroll-mt-6 p-4 sm:p-6 flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3"><span className="rounded-xl bg-violet-50 p-2.5 text-violet-600"><FileText size={20} /></span><div><h2 id="library-title" className="text-base font-semibold text-slate-900">Paper library <span className="ml-1 text-xs text-slate-400">{papers.data?.total ?? ""}</span></h2><p className="mt-0.5 text-xs text-slate-500">Your submissions, reports, and next steps.</p></div></div>
          <div className="flex items-center gap-2">
            <button type="button" aria-label="Refresh dashboard" title="Refresh dashboard" onClick={invalidate} disabled={papers.isFetching || stats.isFetching} className="qpi-icon-button"><RotateCw size={15} className={papers.isFetching ? "animate-spin" : ""} /></button>
            <button type="button" className="qpi-button-secondary" disabled={!papers.data?.items.length || papers.isPlaceholderData || papers.isError} onClick={() => { if (papers.data) { exportPapersCsv(papers.data.items); setNotice(`Exported ${papers.data.items.length} papers from this page.`); } }}><Download size={14} />Export page</button>
            <Link href="/upload" className="qpi-button-primary"><CloudUpload size={16} /><span className="hidden sm:inline">New paper</span><span className="sr-only sm:hidden">New paper</span></Link>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-1 rounded-xl bg-[#f5f4fa] p-1">{STATUS_FILTERS.map((filter) => <button key={filter.value} type="button" aria-pressed={statusFilter === filter.value} onClick={() => { setPage(1); setStatusFilter(filter.value); }} className={`rounded-lg px-3 py-2 text-xs font-medium transition ${statusFilter === filter.value ? "bg-white text-violet-700 shadow-sm" : "text-slate-500 hover:text-violet-700"}`}>{filter.value === "" ? "All papers" : filter.label}</button>)}{statusFilter === "COMPLETED" && <span className="rounded-lg bg-white px-3 py-2 text-xs font-medium text-violet-700 shadow-sm">Ready to review</span>}</div>
          <span className="flex items-center gap-1.5 text-[10px] text-slate-500"><span className={`h-1.5 w-1.5 rounded-full ${papers.isError ? "bg-rose-400" : "bg-emerald-400"}`} />{papers.isError ? "Connection interrupted" : "Auto-refresh enabled"}</span>
        </div>
        <div className="flex flex-wrap gap-3">
          <label className="relative min-w-[180px] flex-1"><span className="sr-only">Search papers</span><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><input value={search} maxLength={100} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search course, filename, or year…" className="qpi-input pl-9" /></label>
          <label className="relative"><span className="sr-only">Sort papers</span><ArrowUpDown size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><select value={sortValue} onChange={(e) => { setSortValue(e.target.value); setPage(1); }} className="qpi-input w-auto pl-9"><option value="created_at:desc">Newest first</option><option value="created_at:asc">Oldest first</option><option value="originality_score:desc">Highest originality</option><option value="course_code:asc">Course A–Z</option></select></label>
          {(search || statusFilter) && <button type="button" onClick={() => { setSearch(""); setStatusFilter(""); setPage(1); }} className="flex items-center gap-1 text-xs font-medium text-violet-600"><X size={13} />Clear filters</button>}
        </div>
        <div role="status" className={notice ? "rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-800" : "sr-only"}>{notice}</div>
        {!!papers.data?.items.length && <p className="text-[10px] text-slate-400 md:hidden">Swipe the table to see statuses, originality, and actions.</p>}

        {actionError && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3 py-2" role="alert">
            {actionError}
          </div>
        )}

        {papers.isLoading ? (
          <LoadingState label="Loading submissions..." />
        ) : papers.isError ? (
          <ErrorState message={errorText(papers.error)} onRetry={() => papers.refetch()} />
        ) : papers.data && papers.data.items.length === 0 ? (
          <EmptyState title={debouncedSearch || statusFilter ? "No papers match your filters" : "Your next great paper starts here"}>
            {!debouncedSearch && !statusFilter && (
              <Link href="/upload" className="text-accent font-semibold hover:underline">Upload your first draft</Link>
            )}
          </EmptyState>
        ) : (
          <div className={`overflow-x-auto -mx-2 transition-opacity ${papers.isPlaceholderData ? "opacity-50" : ""}`} aria-busy={papers.isFetching}>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-slate-500 border-y border-slate-100 bg-[#faf9fc]">
                  <th className="px-2 py-2 font-semibold">Paper</th>
                  <th className="px-2 py-2 font-semibold">Term</th>
                  <th className="px-2 py-2 font-semibold">Uploaded</th>
                  <th className="px-2 py-2 font-semibold">Status</th>
                  <th className="px-2 py-2 font-semibold text-right">Originality</th>
                  <th className="px-2 py-2 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {papers.data?.items.map((p) => (
                  <tr key={p.id} className="border-b border-slate-100/70 last:border-0 align-middle transition hover:bg-violet-50/30">
                    <td className="px-3 py-4">
                      <div className="font-semibold text-slate-800">
                        {p.course_code} · {p.exam_type}
                        {p.is_historical_archive && (
                          <span className="ml-2 text-[10px] font-semibold uppercase text-slate-500 border border-slate-200 rounded px-1.5 py-0.5">
                            Archive
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-slate-400 truncate max-w-[240px]" title={p.original_filename}>
                        {p.original_filename}
                        {!p.is_owner && ` · ${p.uploader_name}`}
                      </div>
                    </td>
                    <td className="px-2 py-3 text-slate-600 whitespace-nowrap">{p.term} {p.academic_year}</td>
                    <td className="px-2 py-3 text-slate-600 whitespace-nowrap">{formatDate(p.created_at)}</td>
                    <td className="px-3 py-4">
                      <span className={`text-[11px] font-semibold inline-flex items-center whitespace-nowrap px-2.5 py-1 rounded-full border ${statusBadgeClass(p.status)}`}>
                        {STATUS_LABELS[p.status]}
                        {isInProgress(p.status) && ` · ${p.progress_percent}%`}
                      </span>
                      {p.status === "FAILED" && p.error_message && (
                        <div className="text-xs text-red-600 mt-1 max-w-[240px]">{p.error_message}</div>
                      )}
                    </td>
                    <td className="px-3 py-4 text-right">
                      <span className={`text-xs font-semibold ${p.originality_score === null ? "text-slate-400" : p.originality_score >= 80 ? "text-emerald-700" : p.originality_score >= 60 ? "text-amber-700" : "text-rose-600"}`}>{formatPercent(p.originality_score)}</span>
                      {p.originality_score !== null && <div className="ml-auto mt-2 h-1 w-16 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${p.originality_score >= 80 ? "bg-emerald-400" : p.originality_score >= 60 ? "bg-amber-400" : "bg-rose-400"}`} style={{ width: `${Math.max(0, Math.min(100, p.originality_score))}%` }} /></div>}
                    </td>
                    <td className="px-3 py-4">
                      <div className="flex justify-end items-center gap-1">
                        {p.report_id && !isInProgress(p.status) && p.status !== "FAILED" && (
                          <Link href={`/reports/${p.report_id}`}
                            className="inline-flex items-center gap-1 whitespace-nowrap text-[11px] font-semibold text-violet-700 px-3 py-2 rounded-lg bg-violet-50 hover:bg-violet-100">
                            View report <ArrowRight size={12} />
                          </Link>
                        )}
                        {p.status === "FAILED" && p.is_owner && (
                          <button type="button" onClick={() => { setActionError(null); retry.mutate(p.id); }}
                            disabled={retry.isPending}
                            className="text-xs font-semibold text-slate-700 px-3 py-1.5 rounded-full hover:bg-slate-100 flex items-center gap-1">
                            <RotateCw size={13} /> Retry
                          </button>
                        )}
                        <a href={api.paperFileUrl(p.id)} aria-label={`Download ${p.original_filename}`} title="Download original" className="qpi-icon-button !border-transparent"><Download size={14} /></a>
                        {p.is_owner && p.status !== "APPROVED" && !isInProgress(p.status) && (
                          <button type="button" aria-label={`Delete ${p.original_filename}`} onClick={() => onDelete(p)}
                            disabled={remove.isPending}
                            className="p-1.5 rounded-full text-slate-400 hover:text-red-600 hover:bg-red-50">
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {papers.data && papers.data.total > 0 && !papers.isError && (
          <div className="flex items-center justify-between text-sm text-slate-500 pt-2">
            <span>
              Page {papers.data.page} of {papers.data.pages} · {papers.data.total} papers
            </span>
            <div className="flex gap-2">
              <button type="button" disabled={page <= 1 || papers.isPlaceholderData} onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 rounded-full border border-slate-200 disabled:opacity-40 hover:bg-slate-50">
                Previous
              </button>
              <button type="button" disabled={page >= papers.data.pages || papers.isPlaceholderData} onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded-full border border-slate-200 disabled:opacity-40 hover:bg-slate-50">
                Next
              </button>
            </div>
          </div>
        )}
      </section>
      <footer className="flex flex-wrap justify-between gap-2 px-1 text-[10px] text-slate-400"><span>Thoughtful papers. Meaningful learning.</span><span>Question Paper Intelligence · Your academic companion</span></footer>
    </div>
  );
}
