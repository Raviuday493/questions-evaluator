"use client";

import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Table2, LineChart as LineIcon } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { formatNumber } from "@/utils/format";
import { SERIES_COLORS } from "./Bars";

const INK_MUTED = "#898781";
const GRID = "#e1e0d9";

export interface SeriesDef {
  key: string;
  label: string;
}

function labelFor(iso: string, bucket: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  const opts: Intl.DateTimeFormatOptions = bucket === "month" ? { month: "short", year: "2-digit", timeZone: "UTC" } : { month: "short", day: "numeric", timeZone: "UTC" };
  return new Intl.DateTimeFormat(undefined, opts).format(d);
}

export function TrendChart({ labels, bucket, series, data, height = 260 }: {
  labels: string[];
  bucket: string;
  series: SeriesDef[];
  data: Record<string, number[]>;
  height?: number;
}) {
  const [asTable, setAsTable] = useState(false);
  const rows = labels.map((l, i) => {
    const row: Record<string, string | number> = { label: labelFor(l, bucket), iso: l };
    for (const s of series) row[s.key] = data[s.key]?.[i] ?? 0;
    return row;
  });
  const total = (key: string) => (data[key] ?? []).reduce((a, b) => a + b, 0);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-soft">
          {series.map((s, i) => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-3 rounded" style={{ background: SERIES_COLORS[i] }} aria-hidden />
              {s.label} <strong className="font-semibold text-ink tabular-nums">{formatNumber(total(s.key))}</strong>
            </span>
          ))}
        </div>
        <Button size="sm" variant="ghost" onClick={() => setAsTable((v) => !v)} icon={asTable ? <LineIcon size={14} /> : <Table2 size={14} />}>
          {asTable ? "Chart" : "Table"}
        </Button>
      </div>
      {asTable ? (
        <div className="max-h-[300px] overflow-auto rounded border border-line">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-slate-50 text-left text-xs text-ink-muted">
              <tr>
                <th className="px-3 py-2 font-medium">{bucket === "day" ? "Day" : bucket === "week" ? "Week of" : "Month"}</th>
                {series.map((s) => <th key={s.key} className="px-3 py-2 text-right font-medium">{s.label}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-line tabular-nums">
              {rows.map((r) => (
                <tr key={r.iso as string}>
                  <td className="px-3 py-1.5">{r.label}</td>
                  {series.map((s) => <td key={s.key} className="px-3 py-1.5 text-right">{formatNumber(r[s.key] as number)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ height }} role="img" aria-label={`Trend of ${series.map((s) => s.label).join(", ")}`}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: INK_MUTED }} tickLine={false} axisLine={{ stroke: "#c3c2b7" }} minTickGap={24} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: INK_MUTED }} tickLine={false} axisLine={false} width={40} />
              <Tooltip
                cursor={{ stroke: "#c3c2b7", strokeWidth: 1 }}
                contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 4px 12px rgba(15,23,42,.08)" }}
                labelStyle={{ color: "#0f172a", fontWeight: 600, marginBottom: 4 }}
                itemStyle={{ color: "#334155", padding: 0 }}
              />
              {series.map((s, i) => (
                <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={SERIES_COLORS[i]} strokeWidth={2} dot={rows.length <= 14 ? { r: 3, strokeWidth: 0, fill: SERIES_COLORS[i] } : false} activeDot={{ r: 5, stroke: "#fff", strokeWidth: 2 }} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
