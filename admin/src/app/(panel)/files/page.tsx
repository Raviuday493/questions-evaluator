"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { DataTable, type Column } from "@/components/table/DataTable";
import { PageHeader, PaperStatusBadge, SearchInput, StatCard } from "@/components/ui/common";
import { useToast } from "@/components/ui/feedback";
import { Badge, Button, Select, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useDebounced, useUrlState } from "@/hooks/useUrlState";
import { formatBytes, formatDateTime, formatNumber } from "@/utils/format";
import type { Paper } from "@/types";

const DEFAULTS = { search: "", mime: "", sort: "created_at", order: "desc", page: "1", limit: "20" };

function DownloadButton({ paper }: { paper: Paper }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <Button size="sm" variant="ghost" loading={busy} icon={<Download size={14} />} aria-label={`Download ${paper.original_filename}`} onClick={async () => {
      setBusy(true);
      try {
        await adminApi.papers.download(paper.id, paper.original_filename);
      } catch (e) {
        toast.error(e, "Download failed");
      } finally {
        setBusy(false);
      }
    }} />
  );
}

function FilesTable() {
  const { can } = useAdmin();
  const [state, setState] = useUrlState(DEFAULTS);
  const [search, setSearch] = useState(state.search);
  const debounced = useDebounced(search);
  useEffect(() => {
    if (debounced !== state.search) setState({ search: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);
  const files = useQuery({ queryKey: ["files", state], queryFn: () => adminApi.files.list(state), placeholderData: keepPreviousData });
  const s = files.data?.summary;

  const columns: Column<Paper>[] = [
    { key: "name", header: "File", alwaysVisible: true, render: (p) => (
      <span className="flex min-w-[220px] items-start gap-2">
        <FileText size={16} className="mt-0.5 shrink-0 text-ink-faint" aria-hidden />
        <span className="min-w-0">
          <span className="block truncate font-medium text-ink" title={p.original_filename}>{p.original_filename}</span>
          <span className="text-xs text-ink-muted">{p.file_mime_type.includes("pdf") ? "PDF" : "DOCX"}</span>
        </span>
      </span>
    ) },
    { key: "size", header: "Size", sortKey: "file_size_bytes", className: "text-right tabular-nums", render: (p) => formatBytes(p.file_size_bytes) },
    { key: "paper", header: "Paper", render: (p) => (
      <Link href={`/papers/${p.id}`} className="hover:underline">{p.course?.code} · {p.term} {p.academic_year}{p.is_historical_archive && <Badge className="ml-1.5">Archive</Badge>}</Link>
    ) },
    { key: "status", header: "Status", render: (p) => <PaperStatusBadge status={p.status} /> },
    { key: "owner", header: "Owner", render: (p) => p.uploader ? <Link href={`/users/${p.uploader.id}`} className="hover:underline">{p.uploader.full_name}</Link> : "—" },
    { key: "created", header: "Uploaded", sortKey: "created_at", render: (p) => formatDateTime(p.created_at) },
    ...(can("papers.download") ? [{ key: "download", header: "", alwaysVisible: true, className: "text-right", render: (p: Paper) => <DownloadButton paper={p} /> }] : []),
  ];

  return (
    <>
      <PageHeader title="Files" description="Original PDF/DOCX uploads. Storage locations are managed by the backend and are not exposed here." />
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {s ? (
          <>
            <StatCard label="Stored files" value={formatNumber(s.total_files)} />
            <StatCard label="Total size" value={formatBytes(s.total_bytes)} />
            {s.by_type.map((t) => (
              <StatCard key={t.mime_type} label={t.mime_type.includes("pdf") ? "PDF files" : "DOCX files"} value={formatNumber(t.count)} hint={formatBytes(t.bytes)} />
            ))}
          </>
        ) : Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[92px]" />)}
      </div>
      <DataTable
        storageKey="files"
        columns={columns}
        rows={files.data?.items}
        rowKey={(p) => p.id}
        loading={files.isLoading}
        fetching={files.isFetching}
        error={files.error}
        onRetry={() => files.refetch()}
        onRefresh={() => files.refetch()}
        sort={{ key: state.sort, order: state.order as "asc" | "desc", onChange: (sort, order) => setState({ sort, order }) }}
        pagination={files.data && {
          page: files.data.page, limit: files.data.limit, total: files.data.total, totalPages: files.data.total_pages,
          onPage: (p) => setState({ page: String(p) }), onLimit: (l) => setState({ limit: String(l) }),
        }}
        emptyTitle="No files match these filters"
        toolbar={
          <>
            <SearchInput value={search} onChange={setSearch} placeholder="File name, course, owner…" label="Search files" />
            <Select aria-label="Filter by type" className="h-8 w-auto" value={state.mime} onChange={(e) => setState({ mime: e.target.value })}>
              <option value="">All types</option>
              <option value="pdf">PDF</option>
              <option value="docx">DOCX</option>
            </Select>
            {s && <span className="text-xs text-ink-muted">Storage backend: {s.storage_type}</span>}
          </>
        }
      />
    </>
  );
}

export default function FilesPage() {
  return <RequirePermission permission="papers.view"><FilesTable /></RequirePermission>;
}
