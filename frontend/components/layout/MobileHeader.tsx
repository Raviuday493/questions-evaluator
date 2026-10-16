"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Bell, BookOpenCheck, ChevronRight, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { STATUS_LABELS, formatDate, statusBadgeClass } from "@/lib/format";
import { useLogout } from "@/hooks/useCurrentUser";

export default function MobileHeader() {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const logout = useLogout();
  const pathname = usePathname();
  const pageTitle = pathname.startsWith("/upload") ? "Upload & Analyze" : pathname.startsWith("/insights") ? "Preparation Insights" : pathname.startsWith("/reports") ? "Analysis Report" : "Dashboard";
  // Recent activity: the latest papers and their analysis status.
  const recent = useQuery({
    queryKey: ["papers", { limit: 5, sort: "created_at" }],
    queryFn: () => api.papers({ limit: 5 }),
    enabled: open,
  });

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); menuRef.current?.querySelector<HTMLButtonElement>("button")?.focus(); }
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <header className="relative bg-white/90 text-primary w-full border-b border-slate-200/70 z-30">
      <div className="flex justify-between items-center w-full px-4 md:px-7 xl:px-9 py-3 max-w-[1440px] mx-auto">
        <div className="flex items-center gap-3 md:hidden">
          <div className="w-8 h-8 rounded-lg bg-violet-500 text-white flex items-center justify-center">
            <BookOpenCheck size={20} />
          </div>
          <span className="font-semibold text-slate-900 text-base">QPI<span className="text-violet-500">.</span></span>
        </div>
        <div className="hidden md:flex items-center gap-3 text-xs"><span className="text-slate-400">Workspace</span><ChevronRight size={12} className="text-slate-300" /><span className="font-medium text-slate-700">{pageTitle}</span></div>
        <div className="flex items-center gap-1" ref={menuRef}>
          <button
            type="button"
            aria-label="Recent activity"
            aria-expanded={open}
            aria-controls="recent-activity"
            onClick={() => setOpen((o) => !o)}
            className="inline-flex items-center text-slate-500 hover:bg-slate-100 p-2 rounded-full transition-colors"
          >
            <Bell size={18} /><span className="hidden md:inline ml-2 text-xs">Activity</span>
          </button>
          <button
            type="button"
            aria-label="Sign out"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            className="md:hidden text-slate-500 hover:bg-slate-100 p-2 rounded-full transition-colors"
          >
            <LogOut size={18} />
          </button>

          {open && (
            <div id="recent-activity" className="absolute right-3 top-14 w-[calc(100vw-24px)] max-w-sm qpi-card p-3 shadow-card z-50">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1 pb-2">
                Recent activity
              </div>
              {recent.isLoading && <div className="text-sm text-slate-500 px-1 py-3">Loading...</div>}
              {recent.isError && <div className="text-sm text-red-600 px-1 py-3">Could not load activity.</div>}
              {recent.data && recent.data.items.length === 0 && (
                <div className="text-sm text-slate-500 px-1 py-3">No papers uploaded yet.</div>
              )}
              <ul className="flex flex-col">
                {recent.data?.items.map((p) => (
                  <li key={p.id}>
                    <Link
                      href={p.report_id ? `/reports/${p.report_id}` : "/dashboard"}
                      onClick={() => setOpen(false)}
                      className="flex items-center justify-between gap-2 px-1 py-2 rounded-lg hover:bg-slate-50"
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-slate-900 truncate">
                          {p.course_code} · {p.exam_type}
                        </div>
                        <div className="text-xs text-slate-500">{formatDate(p.created_at)}</div>
                      </div>
                      <span className={`shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full border ${statusBadgeClass(p.status)}`}>
                        {STATUS_LABELS[p.status]}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
