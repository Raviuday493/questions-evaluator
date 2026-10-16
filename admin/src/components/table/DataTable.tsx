"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Columns3, Download, RefreshCw } from "lucide-react";
import { Button, Checkbox, Select, Skeleton } from "@/components/ui/primitives";
import { EmptyState, ErrorState } from "@/components/ui/feedback";
import { cn, formatNumber } from "@/utils/format";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Server-side sort key; omit for unsortable columns. */
  sortKey?: string;
  className?: string;
  /** Columns hidden by default can be switched on from the column menu. */
  defaultHidden?: boolean;
  /** Columns that cannot be hidden (e.g. the primary identifier). */
  alwaysVisible?: boolean;
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  onPage: (page: number) => void;
  onLimit?: (limit: number) => void;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  loading?: boolean;
  fetching?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onRefresh?: () => void;
  onExport?: () => Promise<void> | void;
  exporting?: boolean;
  sort?: { key: string; order: "asc" | "desc"; onChange: (key: string, order: "asc" | "desc") => void };
  selection?: { selected: Set<string>; onChange: (next: Set<string>) => void; bulkActions: ReactNode };
  pagination?: Pagination;
  toolbar?: ReactNode;
  emptyTitle?: string;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  storageKey?: string;
}

function useColumnVisibility<T>(columns: Column<T>[], storageKey?: string) {
  const [hidden, setHidden] = useState<Set<string>>(() => new Set(columns.filter((c) => c.defaultHidden).map((c) => c.key)));
  useEffect(() => {
    if (!storageKey) return;
    try {
      const saved = window.localStorage.getItem(`cols:${storageKey}`);
      if (saved) setHidden(new Set(JSON.parse(saved)));
    } catch {
      // storage unavailable: keep defaults
    }
  }, [storageKey]);
  const toggle = (key: string) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      if (storageKey) {
        try {
          window.localStorage.setItem(`cols:${storageKey}`, JSON.stringify(Array.from(next)));
        } catch {
          // ignore
        }
      }
      return next;
    });
  return { hidden, toggle };
}

export function DataTable<T>(props: Props<T>) {
  const { columns, rows, rowKey, loading, fetching, error, onRetry, onRefresh, onExport, exporting, sort, selection, pagination, toolbar } = props;
  const { hidden, toggle } = useColumnVisibility(columns, props.storageKey);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenuOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  const visible = columns.filter((c) => c.alwaysVisible || !hidden.has(c.key));
  const pageIds = (rows ?? []).map(rowKey);
  const selectedOnPage = selection ? pageIds.filter((id) => selection.selected.has(id)).length : 0;
  const colSpan = visible.length + (selection ? 1 : 0);

  const toggleAll = (checked: boolean) => {
    if (!selection) return;
    const next = new Set(selection.selected);
    pageIds.forEach((id) => (checked ? next.add(id) : next.delete(id)));
    selection.onChange(next);
  };

  return (
    <div className="rounded-lg border border-line bg-white shadow-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2.5">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">{toolbar}</div>
        <div className="flex items-center gap-1.5">
          {onRefresh && (
            <Button size="sm" variant="ghost" onClick={onRefresh} aria-label="Refresh" title="Refresh" icon={<RefreshCw size={14} className={fetching ? "animate-spin" : undefined} />} />
          )}
          <div className="relative" ref={menuRef}>
            <Button size="sm" variant="ghost" aria-haspopup="true" aria-expanded={menuOpen} onClick={() => setMenuOpen((v) => !v)} icon={<Columns3 size={14} />}>
              <span className="hidden sm:inline">Columns</span>
            </Button>
            {menuOpen && (
              <div className="absolute right-0 z-20 mt-1 w-52 rounded-md border border-line bg-white p-1.5 shadow-lg">
                {columns.filter((c) => !c.alwaysVisible).map((c) => (
                  <label key={c.key} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-50">
                    <Checkbox checked={!hidden.has(c.key)} onChange={() => toggle(c.key)} label={`Show ${c.header}`} />
                    {c.header}
                  </label>
                ))}
              </div>
            )}
          </div>
          {onExport && (
            <Button size="sm" onClick={() => onExport()} loading={exporting} icon={<Download size={14} />}>
              Export CSV
            </Button>
          )}
        </div>
      </div>

      {selection && selection.selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-b border-brand-100 bg-brand-50 px-3 py-2 text-sm">
          <span className="font-medium text-brand-700">{selection.selected.size} selected</span>
          <Button size="sm" variant="ghost" onClick={() => selection.onChange(new Set())}>Clear</Button>
          <div className="ml-auto flex flex-wrap gap-2">{selection.bulkActions}</div>
        </div>
      )}

      <div className={cn("overflow-x-auto transition-opacity", fetching && !loading ? "opacity-60" : undefined)} aria-busy={fetching}>
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-ink-muted">
            <tr>
              {selection && (
                <th className="w-10 px-3 py-2.5">
                  <Checkbox
                    label="Select all on this page"
                    checked={pageIds.length > 0 && selectedOnPage === pageIds.length}
                    indeterminate={selectedOnPage > 0 && selectedOnPage < pageIds.length}
                    onChange={toggleAll}
                    disabled={!pageIds.length}
                  />
                </th>
              )}
              {visible.map((c) => {
                const active = sort && c.sortKey && sort.key === c.sortKey;
                return (
                  <th key={c.key} className={cn("whitespace-nowrap px-3 py-2.5 font-medium", c.className)} aria-sort={active ? (sort!.order === "asc" ? "ascending" : "descending") : undefined}>
                    {sort && c.sortKey ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 uppercase hover:text-ink"
                        onClick={() => sort.onChange(c.sortKey!, active && sort.order === "desc" ? "asc" : "desc")}
                      >
                        {c.header}
                        {active ? sort.order === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} /> : <ArrowUpDown size={12} className="opacity-40" />}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: colSpan }).map((__, j) => (
                    <td key={j} className="px-3 py-3"><Skeleton className="h-4 w-full max-w-[160px]" /></td>
                  ))}
                </tr>
              ))
            ) : error ? (
              <tr><td colSpan={colSpan}><ErrorState error={error} onRetry={onRetry} compact /></td></tr>
            ) : !rows?.length ? (
              <tr><td colSpan={colSpan}><EmptyState title={props.emptyTitle ?? "Nothing here yet"} message={props.emptyMessage} /></td></tr>
            ) : (
              rows.map((row) => {
                const id = rowKey(row);
                const selected = selection?.selected.has(id);
                return (
                  <tr
                    key={id}
                    className={cn("align-top", selected ? "bg-brand-50/60" : "hover:bg-slate-50", props.onRowClick && "cursor-pointer")}
                    onClick={props.onRowClick ? (e) => {
                      if ((e.target as HTMLElement).closest("a,button,input,label")) return;
                      props.onRowClick!(row);
                    } : undefined}
                  >
                    {selection && (
                      <td className="px-3 py-2.5">
                        <Checkbox
                          label="Select row"
                          checked={Boolean(selected)}
                          onChange={(checked) => {
                            const next = new Set(selection.selected);
                            if (checked) next.add(id);
                            else next.delete(id);
                            selection.onChange(next);
                          }}
                        />
                      </td>
                    )}
                    {visible.map((c) => (
                      <td key={c.key} className={cn("px-3 py-2.5 text-ink", c.className)}>{c.render(row)}</td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {pagination && !error && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-3 py-2.5 text-sm text-ink-muted">
          <span>
            {pagination.total === 0
              ? "No results"
              : `${formatNumber((pagination.page - 1) * pagination.limit + 1)}–${formatNumber(Math.min(pagination.page * pagination.limit, pagination.total))} of ${formatNumber(pagination.total)}`}
          </span>
          <div className="flex items-center gap-2">
            {pagination.onLimit && (
              <label className="flex items-center gap-1.5">
                <span className="hidden sm:inline">Rows</span>
                <Select className="h-8 w-[72px]" value={pagination.limit} onChange={(e) => pagination.onLimit!(Number(e.target.value))} aria-label="Rows per page">
                  {[10, 20, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
                </Select>
              </label>
            )}
            <Button size="sm" aria-label="Previous page" disabled={pagination.page <= 1 || fetching} onClick={() => pagination.onPage(pagination.page - 1)} icon={<ChevronLeft size={14} />} />
            <span className="tabular-nums">Page {pagination.page} of {pagination.totalPages}</span>
            <Button size="sm" aria-label="Next page" disabled={pagination.page >= pagination.totalPages || fetching} onClick={() => pagination.onPage(pagination.page + 1)} icon={<ChevronRight size={14} />} />
          </div>
        </div>
      )}
    </div>
  );
}
