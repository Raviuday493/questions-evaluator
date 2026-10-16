"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { DataTable, type Column } from "@/components/table/DataTable";
import { OriginalityValue, PageHeader, PaperStatusBadge, SearchInput } from "@/components/ui/common";
import { useConfirm, useToast } from "@/components/ui/feedback";
import { Badge, Button, Input, Select } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useDebounced, useUrlState } from "@/hooks/useUrlState";
import { PAPER_STATUSES, STATUS_LABELS, formatBytes, formatDate } from "@/utils/format";
import type { Paper } from "@/types";

const DEFAULTS = {
  search: "", status: "", department_id: "", course_id: "", uploader_id: "", archive: "", stuck: "", from: "", to: "",
  sort: "created_at", order: "desc", page: "1", limit: "20",
};

function PapersTable() {
  const { can } = useAdmin();
  const router = useRouter();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const [state, setState] = useUrlState(DEFAULTS);
  const [search, setSearch] = useState(state.search);
  const debounced = useDebounced(search);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (debounced !== state.search) setState({ search: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);
  useEffect(() => setSelected(new Set()), [state.search, state.status, state.archive, state.page, state.department_id]);

  const filters = {
    search: state.search, status: state.status, department_id: state.department_id, course_id: state.course_id,
    uploader_id: state.uploader_id, archive: state.archive, stuck: state.stuck, from: state.from, to: state.to,
  };
  const params = { ...filters, sort: state.sort, order: state.order, page: state.page, limit: state.limit };
  const papers = useQuery({
    queryKey: ["papers", params],
    queryFn: () => adminApi.papers.list(params),
    placeholderData: keepPreviousData,
    // Keep in-flight analyses fresh while they are on screen.
    refetchInterval: (q) => (q.state.data?.items.some((p) => ["QUEUED", "PARSING", "EMBEDDING", "MATCHING"].includes(p.status)) ? 5000 : false),
  });
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => adminApi.departments.list(), enabled: can("catalog.view") });

  const bulk = useMutation({
    mutationFn: (action: "reanalyze" | "delete") => adminApi.papers.bulk(Array.from(selected), action),
    onSuccess: (r, action) => {
      const skipped = r.skipped.length ? ` ${r.skipped.length} skipped (${r.skipped[0].reason}${r.skipped.length > 1 ? ", …" : ""}).` : "";
      toast.success(`${action === "delete" ? "Deleted" : "Queued"} ${r.done.length} paper(s).${skipped}`);
      setSelected(new Set());
      client.invalidateQueries({ queryKey: ["papers"] });
      client.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e) => toast.error(e, "Bulk action failed"),
  });

  const columns: Column<Paper>[] = [
    { key: "course", header: "Paper", sortKey: "course_code", alwaysVisible: true, render: (p) => (
      <Link href={`/papers/${p.id}`} className="block min-w-[200px] hover:underline">
        <span className="font-medium text-ink">{p.course?.code}</span>
        {p.is_historical_archive && <Badge tone="neutral" className="ml-1.5">Archive</Badge>}
        <span className="block text-xs text-ink-muted">{p.exam_type} · {p.term} {p.academic_year}</span>
      </Link>
    ) },
    { key: "status", header: "Status", sortKey: "status", render: (p) => (
      <div>
        <PaperStatusBadge status={p.status} stuck={p.is_stuck} />
        {p.status === "FAILED" && p.error_message && <p className="mt-1 max-w-[260px] truncate text-xs text-red-700" title={p.error_message}>{p.error_message}</p>}
      </div>
    ) },
    { key: "originality", header: "Originality", sortKey: "originality_score", className: "text-right", render: (p) => <OriginalityValue value={p.originality_score} /> },
    { key: "matches", header: "Matched Qs", className: "text-right tabular-nums", render: (p) => p.matched_questions_count === null ? "—" : `${p.matched_questions_count}/${p.total_questions}` },
    { key: "uploader", header: "Uploaded by", render: (p) => p.uploader ? <Link href={`/users/${p.uploader.id}`} className="hover:underline">{p.uploader.full_name}</Link> : "—" },
    { key: "department", header: "Dept.", render: (p) => p.department?.code ?? "—" },
    { key: "created", header: "Uploaded", sortKey: "created_at", render: (p) => formatDate(p.created_at) },
    { key: "file", header: "File", defaultHidden: true, sortKey: "file_size_bytes", render: (p) => <span className="text-xs">{p.original_filename} · {formatBytes(p.file_size_bytes)}</span> },
    { key: "updated", header: "Updated", sortKey: "updated_at", defaultHidden: true, render: (p) => formatDate(p.updated_at) },
  ];

  const activeScope = state.uploader_id || state.course_id;

  return (
    <>
      <PageHeader title="Question papers" description="Every draft and historical archive paper, with its analysis status and originality." />
      {activeScope && (
        <div className="mb-3 flex items-center gap-2 text-sm text-ink-soft">
          <Badge tone="violet">Filtered to one {state.uploader_id ? "uploader" : "course"}</Badge>
          <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => setState({ uploader_id: "", course_id: "" })}>Clear</Button>
        </div>
      )}
      <DataTable
        storageKey="papers"
        columns={columns}
        rows={papers.data?.items}
        rowKey={(p) => p.id}
        loading={papers.isLoading}
        fetching={papers.isFetching}
        error={papers.error}
        onRetry={() => papers.refetch()}
        onRefresh={() => papers.refetch()}
        onRowClick={(p) => router.push(`/papers/${p.id}`)}
        exporting={exporting}
        onExport={can("reports.export") ? async () => {
          setExporting(true);
          try {
            await adminApi.papers.export(filters);
            toast.success("Export downloaded.");
          } catch (e) {
            toast.error(e, "Export failed");
          } finally {
            setExporting(false);
          }
        } : undefined}
        sort={{ key: state.sort, order: state.order as "asc" | "desc", onChange: (sort, order) => setState({ sort, order }) }}
        selection={can("papers.manage") || can("papers.delete") ? {
          selected,
          onChange: setSelected,
          bulkActions: (
            <>
              {can("papers.manage") && (
                <Button size="sm" onClick={() => ask({
                  title: `Re-analyse ${selected.size} paper(s)?`,
                  message: "Failed papers and completed drafts are re-queued; their current reports are replaced. Archive and approved papers are skipped.",
                  confirmLabel: "Re-analyse",
                }, () => bulk.mutateAsync("reanalyze"))}>Re-analyse</Button>
              )}
              {can("papers.delete") && (
                <Button size="sm" variant="danger" onClick={() => ask({
                  title: `Delete ${selected.size} paper(s)?`,
                  message: "The papers, their questions, reports and stored files are permanently removed. Matches that other reports found against archive papers are removed too. Papers being analysed are skipped.",
                  confirmLabel: "Delete permanently",
                  danger: true,
                  typeToConfirm: "DELETE",
                }, () => bulk.mutateAsync("delete"))}>Delete</Button>
              )}
            </>
          ),
        } : undefined}
        pagination={papers.data && {
          page: papers.data.page, limit: papers.data.limit, total: papers.data.total, totalPages: papers.data.total_pages,
          onPage: (p) => setState({ page: String(p) }), onLimit: (l) => setState({ limit: String(l) }),
        }}
        emptyTitle="No papers match these filters"
        toolbar={
          <>
            <SearchInput value={search} onChange={setSearch} placeholder="Course, file, uploader…" label="Search papers" />
            <Select aria-label="Filter by status" className="h-8 w-auto" value={state.status.includes(",") ? "__in_progress" : state.status}
              onChange={(e) => setState({ status: e.target.value === "__in_progress" ? "QUEUED,PARSING,EMBEDDING,MATCHING" : e.target.value })}>
              <option value="">All statuses</option>
              <option value="__in_progress">In progress</option>
              {PAPER_STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </Select>
            <Select aria-label="Filter by type" className="h-8 w-auto" value={state.archive} onChange={(e) => setState({ archive: e.target.value })}>
              <option value="">Drafts & archive</option>
              <option value="false">Drafts only</option>
              <option value="true">Archive only</option>
            </Select>
            {departments.data && (
              <Select aria-label="Filter by department" className="h-8 w-auto" value={state.department_id} onChange={(e) => setState({ department_id: e.target.value })}>
                <option value="">All departments</option>
                {departments.data.map((d) => <option key={d.id} value={d.id}>{d.code}</option>)}
              </Select>
            )}
            <label className="flex items-center gap-1.5 text-xs text-ink-soft">
              <input type="checkbox" className="accent-brand-600" checked={state.stuck === "true"} onChange={(e) => setState({ stuck: e.target.checked ? "true" : "" })} />
              Stuck only
            </label>
            <label className="flex items-center gap-1 text-xs text-ink-muted">
              Uploaded
              <Input type="date" aria-label="Uploaded from" className="h-8 w-auto" value={state.from} max={state.to || undefined} onChange={(e) => setState({ from: e.target.value })} />
              –
              <Input type="date" aria-label="Uploaded to" className="h-8 w-auto" value={state.to} min={state.from || undefined} onChange={(e) => setState({ to: e.target.value })} />
            </label>
          </>
        }
      />
      {dialog}
    </>
  );
}

export default function PapersPage() {
  return <RequirePermission permission="papers.view"><PapersTable /></RequirePermission>;
}
