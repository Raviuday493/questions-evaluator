"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bell,
  BookOpen,
  Building2,
  ChevronDown,
  FileStack,
  FileText,
  FolderOpen,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  UserCog,
  Users,
  X,
} from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { useAdmin, useLogout } from "@/hooks/useAdmin";
import { useDebounced } from "@/hooks/useUrlState";
import { ErrorState } from "@/components/ui/feedback";
import { Spinner } from "@/components/ui/primitives";
import { cn, initials } from "@/utils/format";
import type { SearchResults } from "@/types";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Users;
  permission: string;
}

const NAV: { heading: string; items: NavItem[] }[] = [
  { heading: "Overview", items: [
    { href: "/", label: "Dashboard", icon: LayoutDashboard, permission: "dashboard.view" },
    { href: "/reports", label: "Reports", icon: FileText, permission: "reports.view" },
  ] },
  { heading: "Application data", items: [
    { href: "/users", label: "Users", icon: Users, permission: "users.view" },
    { href: "/papers", label: "Question papers", icon: FileStack, permission: "papers.view" },
    { href: "/files", label: "Files", icon: FolderOpen, permission: "papers.view" },
    { href: "/departments", label: "Departments", icon: Building2, permission: "catalog.view" },
    { href: "/courses", label: "Courses & syllabi", icon: BookOpen, permission: "catalog.view" },
  ] },
  { heading: "Operations", items: [
    { href: "/audit-logs", label: "Audit log", icon: ScrollText, permission: "audit.view" },
    { href: "/system", label: "System health", icon: Activity, permission: "system.view" },
    { href: "/settings", label: "Settings", icon: Settings, permission: "settings.view" },
  ] },
  { heading: "Administration", items: [
    { href: "/admins", label: "Administrators", icon: UserCog, permission: "admins.view" },
    { href: "/roles", label: "Roles & permissions", icon: KeyRound, permission: "admins.view" },
  ] },
];

const TITLES: [string, string][] = NAV.flatMap((g) => g.items.map((i) => [i.href, i.label] as [string, string]));

function titleFor(pathname: string): string {
  if (pathname === "/profile") return "My profile";
  const match = TITLES.filter(([href]) => href !== "/" && pathname.startsWith(href)).sort((a, b) => b[0].length - a[0].length)[0];
  return match ? match[1] : "Dashboard";
}

function Sidebar({ can, open, onClose }: { can: (p: string) => boolean; open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" onClick={onClose} aria-hidden />}
      <nav
        aria-label="Admin navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-60 flex-col bg-brand-900 text-slate-200 transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center gap-2.5 border-b border-white/10 px-4">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-500 text-white"><ShieldCheck size={18} aria-hidden /></span>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-white">QPI Admin</div>
            <div className="text-[11px] text-slate-400">Question Paper Intelligence</div>
          </div>
          <button type="button" className="ml-auto rounded p-1 text-slate-400 hover:text-white lg:hidden" aria-label="Close menu" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-2.5 py-3">
          {NAV.map((group) => {
            const items = group.items.filter((i) => can(i.permission));
            if (!items.length) return null;
            return (
              <div key={group.heading} className="mb-4">
                <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">{group.heading}</div>
                {items.map((item) => {
                  const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onClose}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "mb-0.5 flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm",
                        active ? "bg-white/10 font-medium text-white" : "text-slate-300 hover:bg-white/5 hover:text-white",
                      )}
                    >
                      <Icon size={16} aria-hidden />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </div>
      </nav>
    </>
  );
}

const SEARCH_GROUPS: { key: keyof SearchResults; label: string; href: (id: string) => string }[] = [
  { key: "users", label: "Users", href: (id) => `/users/${id}` },
  { key: "papers", label: "Papers", href: (id) => `/papers/${id}` },
  { key: "courses", label: "Courses", href: (id) => `/courses/${id}` },
  { key: "departments", label: "Departments", href: () => `/departments` },
  { key: "admins", label: "Administrators", href: (id) => `/admins/${id}` },
];

function GlobalSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const term = useDebounced(q.trim(), 250);
  const results = useQuery({ queryKey: ["search", term], queryFn: () => adminApi.search(term), enabled: term.length >= 2 });
  useEffect(() => {
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const groups = SEARCH_GROUPS.map((g) => ({ ...g, hits: results.data?.[g.key] ?? [] })).filter((g) => g.hits.length);
  const go = (href: string) => {
    setOpen(false);
    setQ("");
    router.push(href);
  };
  return (
    <div ref={box} className="relative w-full max-w-md">
      <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden />
      <input
        type="search"
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        placeholder="Search users, papers, courses…"
        aria-label="Global search"
        maxLength={100}
        className="h-9 w-full rounded-md border border-line bg-slate-50 pl-8 pr-3 text-sm placeholder:text-ink-faint focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100"
      />
      {open && term.length >= 2 && (
        <div className="absolute left-0 right-0 z-30 mt-1 max-h-[70vh] overflow-y-auto rounded-md border border-line bg-white py-1 shadow-lg">
          {results.isLoading ? (
            <div className="px-3 py-3"><Spinner label="Searching" /></div>
          ) : results.isError ? (
            <ErrorState error={results.error} compact />
          ) : !groups.length ? (
            <p className="px-3 py-3 text-sm text-ink-muted">No matches for “{term}”.</p>
          ) : (
            groups.map((g) => (
              <div key={g.key} className="py-1">
                <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{g.label}</div>
                {g.hits.map((h) => (
                  <button key={h.id} type="button" onClick={() => go(g.href(h.id))} className="block w-full px-3 py-1.5 text-left hover:bg-slate-50">
                    <div className="truncate text-sm text-ink">{h.title}</div>
                    <div className="truncate text-xs text-ink-muted">{h.subtitle}</div>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function Alerts() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: adminApi.dashboard.alerts, refetchInterval: 60_000 });
  useEffect(() => {
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const count = alerts.data?.count ?? 0;
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-label={`Alerts (${count})`} aria-expanded={open} onClick={() => setOpen((v) => !v)} className="relative rounded-md p-2 text-ink-soft hover:bg-slate-100">
        <Bell size={18} />
        {count > 0 && <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">{count}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-1 w-80 rounded-md border border-line bg-white shadow-lg">
          <div className="border-b border-line px-3 py-2 text-sm font-semibold text-ink">Needs attention</div>
          {alerts.isError ? (
            <ErrorState error={alerts.error} compact onRetry={() => alerts.refetch()} />
          ) : !alerts.data?.items.length ? (
            <p className="px-3 py-4 text-sm text-ink-muted">All clear — nothing needs attention.</p>
          ) : (
            alerts.data.items.map((a) => (
              <Link key={a.key} href={a.link} onClick={() => setOpen(false)} className="flex gap-2 border-b border-line px-3 py-2.5 text-sm last:border-0 hover:bg-slate-50">
                <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", a.severity === "error" ? "bg-status-critical" : "bg-status-warning")} aria-hidden />
                <span className="text-ink">{a.message}</span>
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function ProfileMenu() {
  const { admin } = useAdmin();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  if (!admin) return null;
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)} className="flex items-center gap-2 rounded-md py-1 pl-1 pr-2 hover:bg-slate-100">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">{initials(admin.full_name)}</span>
        <span className="hidden text-left leading-tight md:block">
          <span className="block max-w-[160px] truncate text-sm font-medium text-ink">{admin.full_name}</span>
          <span className="block text-[11px] text-ink-muted">{admin.role?.name}</span>
        </span>
        <ChevronDown size={14} className="text-ink-faint" />
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-1 w-56 rounded-md border border-line bg-white py-1 shadow-lg">
          <div className="border-b border-line px-3 py-2">
            <div className="truncate text-sm font-medium text-ink">{admin.email}</div>
            <div className="text-xs text-ink-muted">{admin.role?.name}</div>
          </div>
          <Link href="/profile" onClick={() => setOpen(false)} className="block px-3 py-2 text-sm text-ink hover:bg-slate-50">Profile & security</Link>
          <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50">
            <LogOut size={14} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { admin, isLoading, error, refetch, can } = useAdmin();
  const [menuOpen, setMenuOpen] = useState(false);
  const title = titleFor(pathname);

  useEffect(() => {
    document.title = `${title} · QPI Admin`;
  }, [title]);

  if (isLoading) {
    return <div className="flex min-h-dvh items-center justify-center"><Spinner label="Loading admin console" /></div>;
  }
  if (!admin) {
    // 401s redirect to /login from the API client; anything else (backend down) is shown here.
    return (
      <div className="flex min-h-dvh items-center justify-center p-6">
        <div className="max-w-md rounded-lg border border-line bg-white shadow-card"><ErrorState error={error} onRetry={() => refetch()} /></div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <Sidebar can={can} open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-white/95 px-4 backdrop-blur">
          <button type="button" className="rounded p-1.5 text-ink-soft hover:bg-slate-100 lg:hidden" aria-label="Open menu" onClick={() => setMenuOpen(true)}>
            <Menu size={20} />
          </button>
          <span className="hidden text-sm font-semibold text-ink xl:block xl:w-44 xl:truncate">{title}</span>
          <div className="flex flex-1 justify-center"><GlobalSearch /></div>
          <div className="flex items-center gap-1">
            {can("dashboard.view") && <Alerts />}
            <ProfileMenu />
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}

/** Wrap a page body: shows a permission notice instead of the page when the admin lacks `permission`. */
export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAdmin();
  if (!can(permission)) {
    return (
      <div className="rounded-lg border border-line bg-white shadow-card">
        <ErrorState error={new ApiError(`Your role does not include the “${permission}” permission.`, 403)} />
      </div>
    );
  }
  return <>{children}</>;
}
