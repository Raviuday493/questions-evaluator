"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { DataTable, type Column } from "@/components/table/DataTable";
import { PageHeader, SearchInput } from "@/components/ui/common";
import { Modal, useToast } from "@/components/ui/feedback";
import { Badge, Button, DetailList, Input, Select } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useDebounced, useUrlState } from "@/hooks/useUrlState";
import { formatDateTime, humanize } from "@/utils/format";
import type { AuditEntry } from "@/types";

const DEFAULTS = { search: "", action: "", actor_type: "", entity_type: "", entity_id: "", admin_id: "", user_id: "", from: "", to: "", page: "1", limit: "50" };

const ENTITY_LINKS: Record<string, (id: string) => string> = {
  user: (id) => `/users/${id}`,
  paper: (id) => `/papers/${id}`,
  course: (id) => `/courses/${id}`,
  admin: (id) => `/admins/${id}`,
};

function entityLink(a: AuditEntry) {
  const type = a.entity_type ?? (a.action.startsWith("PAPER_") ? "paper" : a.action.startsWith("USER_") ? "user" : null);
  if (!type) return <span className="text-ink-faint">—</span>;
  const href = ENTITY_LINKS[type]?.(a.entity_id);
  const label = `${humanize(type)} ${a.entity_id.slice(0, 8)}`;
  return href && !a.action.endsWith("_DELETE") ? <Link href={href} className="text-brand-600 hover:underline">{label}</Link> : <span className="text-ink-soft">{label}</span>;
}

function AuditLog() {
  const { can } = useAdmin();
  const toast = useToast();
  const [state, setState] = useUrlState(DEFAULTS);
  const [search, setSearch] = useState(state.search);
  const debounced = useDebounced(search);
  const [exporting, setExporting] = useState(false);
  const [detail, setDetail] = useState<AuditEntry | null>(null);
  useEffect(() => {
    if (debounced !== state.search) setState({ search: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);
  const { page, limit, ...filters } = state;
  const q = useQuery({ queryKey: ["audit", state], queryFn: () => adminApi.audit.list(state), placeholderData: keepPreviousData });
  const facets = useQuery({ queryKey: ["audit", "facets"], queryFn: adminApi.audit.facets, staleTime: 60_000 });

  const columns: Column<AuditEntry>[] = [
    { key: "time", header: "Time", alwaysVisible: true, render: (a) => <span className="whitespace-nowrap tabular-nums">{formatDateTime(a.created_at)}</span> },
    { key: "action", header: "Action", render: (a) => <span className="font-medium text-ink">{humanize(a.action)}</span> },
    { key: "actor", header: "Actor", render: (a) => (
      <span className="flex items-center gap-1.5">
        <Badge tone={a.actor.type === "admin" ? "violet" : a.actor.type === "user" ? "blue" : "neutral"}>{humanize(a.actor.type)}</Badge>
        {a.actor.id && a.actor.type !== "system" ? (
          <Link href={a.actor.type === "admin" ? `/admins/${a.actor.id}` : `/users/${a.actor.id}`} className="hover:underline" title={a.actor.email ?? undefined}>{a.actor.name}</Link>
        ) : a.actor.name}
      </span>
    ) },
    { key: "entity", header: "Target", render: entityLink },
    { key: "details", header: "Details", render: (a) => {
      const keys = Object.keys(a.details ?? {});
      return keys.length ? <button type="button" className="text-xs text-brand-600 hover:underline" onClick={() => setDetail(a)}>{keys.slice(0, 3).join(", ")}{keys.length > 3 ? "…" : ""}</button> : <span className="text-ink-faint">—</span>;
    } },
    { key: "ip", header: "IP hash", defaultHidden: true, render: (a) => <code className="text-xs text-ink-muted">{a.ip_hash}</code> },
    { key: "ua", header: "User agent", defaultHidden: true, render: (a) => <span className="block max-w-[240px] truncate text-xs text-ink-muted" title={a.user_agent ?? undefined}>{a.user_agent ?? "—"}</span> },
  ];

  const scoped = state.entity_id || state.admin_id || state.user_id;

  return (
    <>
      <PageHeader title="Audit log" description="Append-only record of sign-ins, uploads, approvals and every administrative change. Entries cannot be edited or deleted." />
      {scoped && (
        <div className="mb-3 flex items-center gap-2">
          <Badge tone="violet">Filtered to one {state.entity_id ? "record" : state.admin_id ? "admin" : "user"}</Badge>
          <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => setState({ entity_id: "", admin_id: "", user_id: "" })}>Clear</Button>
        </div>
      )}
      <DataTable
        storageKey="audit"
        columns={columns}
        rows={q.data?.items}
        rowKey={(a) => a.id}
        loading={q.isLoading}
        fetching={q.isFetching}
        error={q.error}
        onRetry={() => q.refetch()}
        onRefresh={() => q.refetch()}
        exporting={exporting}
        onExport={can("reports.export") ? async () => {
          setExporting(true);
          try {
            await adminApi.audit.export(filters);
            toast.success("Audit log exported.");
          } catch (e) {
            toast.error(e, "Export failed");
          } finally {
            setExporting(false);
          }
        } : undefined}
        pagination={q.data && {
          page: q.data.page, limit: q.data.limit, total: q.data.total, totalPages: q.data.total_pages,
          onPage: (p) => setState({ page: String(p) }), onLimit: (l) => setState({ limit: String(l) }),
        }}
        emptyTitle="No audit entries match these filters"
        toolbar={
          <>
            <SearchInput value={search} onChange={setSearch} placeholder="Action, name or email" label="Search audit log" />
            <Select aria-label="Filter by action" className="h-8 w-auto max-w-[200px]" value={state.action} onChange={(e) => setState({ action: e.target.value })}>
              <option value="">All actions</option>
              {facets.data?.actions.map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
            </Select>
            <Select aria-label="Filter by actor" className="h-8 w-auto" value={state.actor_type} onChange={(e) => setState({ actor_type: e.target.value })}>
              <option value="">All actors</option>
              <option value="admin">Admins</option>
              <option value="user">Users</option>
            </Select>
            <Select aria-label="Filter by target type" className="h-8 w-auto" value={state.entity_type} onChange={(e) => setState({ entity_type: e.target.value })}>
              <option value="">All targets</option>
              {facets.data?.entity_types.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
            </Select>
            <label className="flex items-center gap-1 text-xs text-ink-muted">
              <Input type="date" aria-label="From" className="h-8 w-auto" value={state.from} max={state.to || undefined} onChange={(e) => setState({ from: e.target.value })} />
              –
              <Input type="date" aria-label="To" className="h-8 w-auto" value={state.to} min={state.from || undefined} onChange={(e) => setState({ to: e.target.value })} />
            </label>
          </>
        }
      />
      <Modal open={detail !== null} onClose={() => setDetail(null)} title={detail ? humanize(detail.action) : ""} size="lg">
        {detail && (
          <div className="space-y-4">
            <DetailList items={[
              { label: "Time", value: formatDateTime(detail.created_at) },
              { label: "Actor", value: `${detail.actor.name}${detail.actor.email ? ` (${detail.actor.email})` : ""}` },
              { label: "Target", value: `${detail.entity_type ?? "—"} · ${detail.entity_id}` },
              { label: "IP hash (prefix)", value: detail.ip_hash },
            ]} />
            {/* Rendered as text (never HTML) so logged values cannot inject markup. */}
            <pre className="max-h-80 overflow-auto rounded-md bg-slate-50 p-3 text-xs text-ink">{JSON.stringify(detail.details, null, 2)}</pre>
          </div>
        )}
      </Modal>
    </>
  );
}

export default function AuditLogPage() {
  return <RequirePermission permission="audit.view"><AuditLog /></RequirePermission>;
}
