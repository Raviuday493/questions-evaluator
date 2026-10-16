"use client";

import { Input, Select } from "@/components/ui/primitives";
import { cn, formatNumber } from "@/utils/format";

// Categorical slots in fixed order (validated reference palette); never cycled.
export const SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"];

/** Horizontal magnitude bars with direct value labels (plain HTML: accessible and print-safe). */
export function BarList({ items, color = SERIES_COLORS[0], format = formatNumber, emptyText = "No data yet" }: {
  items: { label: string; value: number; hint?: string; color?: string }[];
  color?: string;
  format?: (v: number) => string;
  emptyText?: string;
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  if (!items.length) return <p className="py-6 text-center text-sm text-ink-muted">{emptyText}</p>;
  return (
    <ul className="space-y-2.5">
      {items.map((item) => (
        <li key={item.label} className="group" title={item.hint ? `${item.label}: ${format(item.value)} (${item.hint})` : `${item.label}: ${format(item.value)}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate text-ink-soft">{item.label}</span>
            <span className="shrink-0 font-medium tabular-nums text-ink">{format(item.value)}</span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-100">
            <div className="h-2 rounded-full transition-[width] group-hover:opacity-80" style={{ width: `${Math.max(2, (item.value / max) * 100)}%`, background: item.color ?? color }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export const RANGE_OPTIONS = [
  { value: "today", label: "Today" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 3 months" },
  { value: "180d", label: "Last 6 months" },
  { value: "365d", label: "Last year" },
  { value: "custom", label: "Custom range" },
];

export function DateRangeControl({ range, from, to, onChange }: {
  range: string;
  from: string;
  to: string;
  onChange: (next: { range: string; from: string; to: string }) => void;
}) {
  const invalid = range === "custom" && Boolean(from && to && from > to);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select aria-label="Date range" className="h-8 w-auto" value={range} onChange={(e) => onChange({ range: e.target.value, from, to })}>
        {RANGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </Select>
      {range === "custom" && (
        <>
          <Input type="date" aria-label="From date" className={cn("h-8 w-auto", invalid && "border-red-400")} value={from} max={to || undefined} onChange={(e) => onChange({ range, from: e.target.value, to })} />
          <span className="text-xs text-ink-muted">to</span>
          <Input type="date" aria-label="To date" className={cn("h-8 w-auto", invalid && "border-red-400")} value={to} min={from || undefined} onChange={(e) => onChange({ range, from, to: e.target.value })} />
        </>
      )}
    </div>
  );
}
