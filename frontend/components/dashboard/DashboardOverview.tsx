import Link from "next/link";
import { ArrowDownRight, ArrowRight, ArrowUpRight, BadgeCheck, Check, Clock3, FileCheck2, Files, Lightbulb, ScanLine, ShieldCheck, Sparkles, TriangleAlert, Upload } from "lucide-react";
import { formatPercent } from "@/lib/format";
import type { DashboardStats } from "@/lib/types";

export function DashboardWelcome() {
  return (
    <section className="dashboard-welcome relative isolate overflow-hidden rounded-3xl px-6 py-7 sm:px-8">
      <div className="relative z-10 max-w-lg">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-[11px] font-semibold tracking-wide text-violet-50"><Sparkles size={13} /> A LITTLE INTELLIGENCE. A LOT OF POSSIBILITY.</span>
        <h2 className="mt-4 text-2xl font-semibold leading-tight tracking-tight text-white sm:text-[30px]">Better questions.<br />Brighter possibilities.</h2>
        <p className="mt-3 max-w-sm text-sm leading-relaxed text-violet-100">Turn your next question paper into your best one. Check originality, discover gaps, and prepare with confidence.</p>
        <Link href="/upload" className="mt-5 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-violet-800 shadow-sm transition hover:bg-violet-50"><Upload size={16} /> Analyze a paper <ArrowRight size={15} className="ml-2" /></Link>
      </div>
      <div className="paper-art hidden lg:block" aria-hidden="true">
        <div className="paper-art-orbit" />
        <div className="paper-art-back" />
        <div className="paper-art-sheet">
          <div className="flex items-center justify-between"><span className="rounded-lg bg-violet-100 p-2 text-violet-600"><FileCheck2 size={23} /></span><Sparkles size={20} className="text-amber-400" /></div>
          <div className="mt-5 h-2 w-24 rounded bg-slate-700" /><div className="mt-3 h-1.5 w-full rounded bg-slate-100" /><div className="mt-2 h-1.5 w-4/5 rounded bg-slate-100" />
          <div className="mt-5 space-y-3">{["Originality", "Coverage", "Balance"].map((label, index) => <div key={label} className="flex items-center gap-2 text-[10px] text-slate-500"><span className="rounded-full bg-emerald-100 p-0.5 text-emerald-600"><Check size={9} /></span>{label}<span className={`ml-auto h-1.5 rounded-full ${index === 1 ? "w-8 bg-amber-300" : "w-12 bg-violet-300"}`} /></div>)}</div>
        </div>
        <div className="paper-art-badge"><ShieldCheck size={21} className="text-emerald-600" /><div><span className="block text-[10px] font-medium text-slate-500">Made for educators</span><span className="text-xs font-bold text-slate-800">Confidence in every paper</span></div></div>
        <span className="absolute right-3 top-9 rounded-2xl bg-amber-300 p-3 text-violet-900 rotate-12"><Lightbulb size={24} /></span>
      </div>
    </section>
  );
}

export function DashboardMetrics({ stats, onFilter }: { stats?: DashboardStats; onFilter: (status: string) => void }) {
  const change = stats?.analyzed_change_percent;
  const cards = [
    { label: "Papers analyzed", value: stats?.total_analyzed.toLocaleString(), icon: Files, tone: "metric-violet", filter: "COMPLETED,APPROVED", detail: change != null ? `${Math.abs(change)}% vs previous 30 days` : stats ? `${stats.analyzed_last_30_days} in the last 30 days` : "Your analyzed drafts", trend: change },
    { label: "Average originality", value: stats ? formatPercent(stats.avg_originality) : undefined, icon: ShieldCheck, tone: "metric-mint", detail: stats?.avg_originality == null ? "Available after your first analysis" : "Across analyzed drafts" },
    { label: "In progress", value: stats?.in_progress.toLocaleString(), icon: ScanLine, tone: "metric-peach", filter: "QUEUED,PARSING,EMBEDDING,MATCHING", detail: stats?.in_progress ? "Analysis updates automatically" : "Ready for your next paper" },
    { label: "Approved papers", value: stats?.approved.toLocaleString(), icon: BadgeCheck, tone: "metric-blue", filter: "APPROVED", detail: "Ready for the question archive" },
  ];
  return <section aria-label="Draft paper statistics" className="grid grid-cols-1 gap-4 min-[360px]:grid-cols-2 xl:grid-cols-4">{cards.map(({ label, value, icon: Icon, tone, filter, detail, trend }) => {
    const content = <><div className="flex items-center justify-between gap-2"><span className="text-[13px] font-medium">{label}</span><span className="metric-icon"><Icon size={19} strokeWidth={1.8} /></span></div><div className="mt-3 text-[32px] font-semibold leading-none tracking-tight tabular-nums">{value ?? "—"}</div><div className="mt-3 flex items-center gap-1 text-[11px] font-medium opacity-80">{trend != null && (trend >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />)}{detail}</div></>;
    return filter !== undefined ? <button key={label} type="button" onClick={() => onFilter(filter)} className={`metric-card ${tone} text-left transition hover:-translate-y-0.5`} aria-label={`${label}: ${value ?? "loading"}. Filter submissions.`}>{content}</button> : <div key={label} className={`metric-card ${tone}`}>{content}</div>;
  })}</section>;
}

export function DashboardSnapshot({ stats, onFilter }: { stats?: DashboardStats; onFilter: (status: string) => void }) {
  const completed = Math.max(0, (stats?.total_analyzed ?? 0) - (stats?.approved ?? 0));
  const total = (stats?.total_analyzed ?? 0) + (stats?.in_progress ?? 0) + (stats?.failed ?? 0);
  const segments = [
    { label: "Analyzed", count: completed, color: "#8b5cf6", filter: "COMPLETED" },
    { label: "Approved", count: stats?.approved ?? 0, color: "#34b99a", filter: "APPROVED" },
    { label: "In progress", count: stats?.in_progress ?? 0, color: "#f6b756", filter: "QUEUED,PARSING,EMBEDDING,MATCHING" },
    { label: "Failed", count: stats?.failed ?? 0, color: "#f08091", filter: "FAILED" },
  ];
  let offset = 0;
  const stops = segments.map((segment) => { const start = offset; offset += total ? segment.count / total * 100 : 0; return `${segment.color} ${start}% ${offset}%`; });
  return <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
    <section className="qpi-card p-5 sm:p-6">
      <div className="flex items-start justify-between"><div><h2 className="text-[15px] font-semibold text-slate-900">Your workspace, at a glance</h2><p className="mt-1 text-xs text-slate-500">All draft papers · excludes historical uploads</p></div><span className="rounded-lg bg-violet-50 p-2 text-violet-500"><Files size={17} /></span></div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-7 sm:justify-start sm:gap-10">
        <div className="relative flex h-32 w-32 shrink-0 items-center justify-center rounded-full" style={{ background: total ? `conic-gradient(${stops.join(",")})` : "#eeedf5" }} role="img" aria-label={stats ? `${total} draft papers: ${segments.map((s) => `${s.count} ${s.label.toLowerCase()}`).join(", ")}` : "Loading draft statistics"}>
          <div className="flex h-[100px] w-[100px] flex-col items-center justify-center rounded-full bg-white"><span className="text-3xl font-semibold tracking-tight text-slate-800">{stats ? total : "—"}</span><span className="mt-1 text-[11px] text-slate-500">Total drafts</span></div>
        </div>
        <div className="min-w-[150px] flex-1 space-y-1">{segments.map((segment) => <button key={segment.label} type="button" onClick={() => onFilter(segment.filter)} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs transition hover:bg-slate-50"><span className="h-2.5 w-2.5 rounded-full" style={{ background: segment.color }} /><span className="text-slate-600">{segment.label}</span><span className="ml-auto font-semibold tabular-nums text-slate-800">{stats ? segment.count : "—"}</span><ArrowUpRight size={12} className="text-slate-400" /></button>)}</div>
      </div>
    </section>
    <section className="qpi-card p-5 sm:p-6">
      <div className="flex items-center gap-2"><span className="rounded-lg bg-amber-50 p-2 text-amber-600"><Lightbulb size={17} /></span><div><h2 className="text-[15px] font-semibold text-slate-900">Make your next move</h2><p className="mt-0.5 text-xs text-slate-500">A little direction for a productive day</p></div></div>
      <div className="mt-4 space-y-2">
        {stats && stats.failed > 0 ? <button type="button" onClick={() => onFilter("FAILED")} className="next-action bg-rose-50/70"><span className="action-icon bg-rose-100 text-rose-600"><TriangleAlert size={17} /></span><span className="flex-1"><strong>{stats.failed} {stats.failed === 1 ? "paper needs" : "papers need"} attention</strong><small>Review the error and retry analysis</small></span><ArrowRight size={15} /></button> : <Link href="/upload" className="next-action bg-violet-50/70"><span className="action-icon bg-violet-100 text-violet-600"><Upload size={17} /></span><span className="flex-1"><strong>Start with a fresh paper</strong><small>Upload a PDF or DOCX to begin</small></span><ArrowRight size={15} /></Link>}
        <button type="button" onClick={() => onFilter("COMPLETED")} className="next-action bg-sky-50/70"><span className="action-icon bg-sky-100 text-sky-600"><Clock3 size={17} /></span><span className="flex-1"><strong>{stats ? `${completed} ${completed === 1 ? "draft" : "drafts"} ready to review` : "Review your analyzed drafts"}</strong><small>Open a report and explore the findings</small></span><ArrowRight size={15} /></button>
        <Link href="/insights" className="next-action bg-amber-50/70"><span className="action-icon bg-amber-100 text-amber-700"><Sparkles size={17} /></span><span className="flex-1"><strong>Find room for a better question</strong><small>Explore topic coverage and recommendations</small></span><ArrowRight size={15} /></Link>
      </div>
    </section>
  </div>;
}
