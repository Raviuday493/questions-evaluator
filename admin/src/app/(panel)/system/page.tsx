"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { PageHeader, StatCard } from "@/components/ui/common";
import { ErrorState } from "@/components/ui/feedback";
import { Badge, Button, Card, DetailList, Skeleton } from "@/components/ui/primitives";
import { formatDateTime, humanize } from "@/utils/format";

function System() {
  const q = useQuery({ queryKey: ["system"], queryFn: adminApi.system.health, refetchInterval: 30_000 });
  if (q.isLoading) return <div className="grid gap-4 lg:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>;
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>;
  const h = q.data;
  const ok = h.status === "healthy";
  return (
    <>
      <PageHeader title="System health" description={`Checked ${formatDateTime(h.checked_at)} · refreshes every 30 seconds`}
        actions={<Button onClick={() => q.refetch()} loading={q.isFetching}>Check now</Button>} />
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Overall" value={<span className="inline-flex items-center gap-2">{ok ? <CheckCircle2 className="text-status-good" /> : <XCircle className="text-status-critical" />}{humanize(h.status)}</span>} tone={ok ? "default" : "danger"} />
        <StatCard label="Database" value={humanize(h.database.status)} hint={`${h.database.dialect} · migration ${h.database.migration ?? "unknown"}`} tone={h.database.status === "ok" ? "default" : "danger"} />
        <StatCard label="Analyses in progress" value={h.task_queue.in_progress} hint={`${h.task_queue.backend} queue`} href="/papers?status=QUEUED,PARSING,EMBEDDING,MATCHING" />
        <StatCard label="Stuck analyses" value={h.task_queue.stuck} hint={`No progress for ${h.task_queue.stuck_after_minutes}+ min`} tone={h.task_queue.stuck ? "warn" : "default"} href="/papers?stuck=true" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Runtime">
          <DetailList items={[
            { label: "Version", value: h.version },
            { label: "Environment", value: <Badge tone={h.environment === "production" ? "green" : "amber"}>{h.environment}</Badge> },
            { label: "Task queue", value: h.task_queue.backend },
            { label: "File storage", value: h.storage.type },
            { label: "Embedding provider", value: h.embeddings.provider },
            { label: "Embedding model", value: `${h.embeddings.model} (${h.embeddings.dimension}-d)` },
          ]} />
        </Card>
        <Card title="Security configuration">
          <DetailList items={Object.entries(h.security).map(([k, v]) => ({
            label: humanize(k),
            value: Array.isArray(v) ? <span className="flex flex-wrap gap-1">{v.map((o) => <Badge key={String(o)}><code>{String(o)}</code></Badge>)}</span> : typeof v === "boolean" ? (v ? "Yes" : "No") : String(v),
          }))} />
          <p className="mt-3 text-xs text-ink-muted">Values come from the backend environment. Change runtime behaviour in <Link href="/settings" className="text-brand-600 hover:underline">Settings</Link>.</p>
        </Card>
      </div>
    </>
  );
}

export default function SystemPage() {
  return <RequirePermission permission="system.view"><System /></RequirePermission>;
}
