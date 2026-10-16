"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowUpRight, BookOpenCheck, CloudUpload, LayoutDashboard, Lightbulb, LogOut, Sparkles } from "lucide-react";
import { useCurrentUser, useLogout } from "@/hooks/useCurrentUser";
import { ROLE_LABELS } from "@/lib/format";

export default function SidebarNav() {
  const pathname = usePathname();
  const { data: user, isLoading } = useCurrentUser();
  const logout = useLogout();

  const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/upload", label: "Upload & Analyze", icon: CloudUpload },
    { href: "/insights", label: "Insights", icon: Lightbulb },
  ];

  return (
    <nav aria-label="Main navigation" className="hidden md:flex flex-col gap-1 p-5 bg-[#252039] text-white h-dvh w-[240px] fixed left-0 top-0 z-40 overflow-y-auto">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:rounded-lg focus:bg-violet-600 focus:p-3">Skip to content</a>
      <div className="flex items-center gap-3 mb-8 mt-3 px-1">
        <div className="w-10 h-10 rounded-xl bg-[#aa87f0] text-white flex items-center justify-center shadow-sm -rotate-6">
          <BookOpenCheck size={24} strokeWidth={1.7} />
        </div>
        <div>
          <div className="text-xl font-semibold tracking-tight text-white">QPI<span className="text-violet-300">.</span></div>
          <div className="text-[10px] text-[#aaa2bd]">Question Paper Intelligence</div>
        </div>
      </div>

      <div className="px-3 py-3 mb-6 rounded-xl bg-white/[0.04] border border-white/[0.08] min-h-[70px]">
        {isLoading ? (
          <div className="animate-pulse flex flex-col gap-1.5">
            <div className="h-3.5 w-32 rounded bg-slate-200" />
            <div className="h-3 w-20 rounded bg-slate-200" />
          </div>
        ) : user ? (
          <>
            <div className="font-medium text-violet-50 text-sm truncate" title={user.email}>{user.full_name}</div>
            <div className="text-violet-300 text-[11px] mt-1">{ROLE_LABELS[user.role]}</div>
            <div className="text-[#aaa2bd] text-[10px] mt-1 truncate">{user.department?.name ?? "Academic workspace"}</div>
          </>
        ) : null}
      </div>

      <div className="px-3 pb-3 text-[9px] font-semibold uppercase tracking-[0.2em] text-[#9387ae]">Workspace</div>
      <div className="flex flex-col gap-2 flex-grow">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={`flex items-center gap-3 px-3 py-3 rounded-xl text-[13px] font-medium transition-all ${
                isActive
                  ? "bg-[#a78be0] text-[#241a3d] shadow-sm"
                  : "text-[#bbb3cb] hover:bg-white/[0.06] hover:text-white"
              }`}
            >
              <Icon size={18} strokeWidth={isActive ? 2.4 : 2} />
              <span>{item.label}</span>
              {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#4e3574]" />}
            </Link>
          );
        })}
      </div>

      <div className="mb-5 mt-10 rounded-2xl border border-white/10 bg-gradient-to-br from-[#423358] to-[#30273f] p-4">
        <span className="inline-flex rounded-xl bg-amber-300/10 p-2 text-amber-200"><Sparkles size={18} /></span>
        <p className="mt-3 text-sm font-medium text-violet-50">A fresh perspective</p>
        <p className="mt-2 text-[11px] leading-relaxed text-[#bdb0d0]">Small improvements make a big difference. Discover what your next paper could be.</p>
        <Link href="/insights" className="mt-4 flex items-center justify-between text-xs font-medium text-violet-200">Explore insights <ArrowUpRight size={14} /></Link>
      </div>
      <button
        type="button"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
        className="flex items-center gap-3 px-3 py-3 rounded-xl text-xs font-medium text-[#bbb3cb] hover:bg-white/5 hover:text-white disabled:opacity-60"
      >
        <LogOut size={18} />
        <span>{logout.isPending ? "Signing out..." : "Sign out"}</span>
      </button>
    </nav>
  );
}
