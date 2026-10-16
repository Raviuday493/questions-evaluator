"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Save } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { PageHeader } from "@/components/ui/common";
import { ErrorState, useConfirm, useToast } from "@/components/ui/feedback";
import { Badge, Button, Card, Input, Skeleton, Toggle } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { formatDateTime } from "@/utils/format";
import type { SettingItem } from "@/types";

type Draft = Record<string, boolean | string>;

function toDraft(items: SettingItem[]): Draft {
  return Object.fromEntries(items.map((s) => [s.key, s.type === "bool" ? Boolean(s.value) : String(s.value)]));
}

function Settings() {
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const q = useQuery({ queryKey: ["settings"], queryFn: adminApi.settings.list });
  const [draft, setDraft] = useState<Draft>({});
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (q.data) setDraft(toDraft(q.data)); }, [q.data]);
  const editable = can("settings.edit");

  const save = useMutation({
    mutationFn: (values: Record<string, unknown>) => adminApi.settings.update(values),
    onSuccess: (items) => {
      client.setQueryData(["settings"], items);
      toast.success("Settings saved. They apply to new requests immediately.");
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save settings."),
  });

  if (q.isLoading) return <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>;
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>;

  const items = q.data;
  const changed = items.filter((s) => (s.type === "bool" ? draft[s.key] !== s.value : Number(draft[s.key]) !== s.value));
  const groups = Array.from(new Set(items.map((s) => s.group)));

  const payload = () => {
    const values: Record<string, unknown> = {};
    for (const s of changed) {
      const raw = draft[s.key];
      if (s.type === "bool") values[s.key] = raw;
      else {
        const n = Number(raw);
        if (raw === "" || Number.isNaN(n)) throw new Error(`${s.label} must be a number.`);
        if ((s.min !== null && n < s.min) || (s.max !== null && n > s.max)) throw new Error(`${s.label} must be between ${s.min} and ${s.max}.`);
        if (s.type === "int" && !Number.isInteger(n)) throw new Error(`${s.label} must be a whole number.`);
        values[s.key] = n;
      }
    }
    return values;
  };

  const submit = () => {
    let values: Record<string, unknown>;
    try {
      values = payload();
    } catch (e) {
      setError((e as Error).message);
      return;
    }
    const risky = ("uploads_enabled" in values && values.uploads_enabled === false) || ("registration_enabled" in values && values.registration_enabled === false);
    ask({
      title: `Save ${changed.length} setting change(s)?`,
      message: (
        <ul className="list-disc space-y-1 pl-4">
          {changed.map((s) => <li key={s.key}><strong>{s.label}</strong>: {String(s.value)} → {String(values[s.key])}</li>)}
          {risky && <li className="text-red-700">This blocks faculty from uploading or registering until turned back on.</li>}
        </ul>
      ),
      confirmLabel: "Save settings",
      danger: risky,
    }, () => save.mutateAsync(values));
  };

  return (
    <>
      <PageHeader title="Settings" description="Runtime configuration applied by the backend. Secrets and infrastructure (database, JWT keys, storage credentials) are environment-only and never shown here."
        actions={editable && (
          <>
            {changed.length > 0 && <Button icon={<RotateCcw size={14} />} onClick={() => { setDraft(toDraft(items)); setError(null); }}>Discard</Button>}
            <Button variant="primary" icon={<Save size={14} />} disabled={!changed.length} loading={save.isPending} onClick={submit}>Save{changed.length ? ` (${changed.length})` : ""}</Button>
          </>
        )} />
      {error && <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
      <div className="space-y-4">
        {groups.map((g) => (
          <Card key={g} title={g} padded={false}>
            <ul className="divide-y divide-line">
              {items.filter((s) => s.group === g).map((s) => (
                <li key={s.key} className="flex flex-wrap items-center justify-between gap-4 px-4 py-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <label htmlFor={`s-${s.key}`} className="text-sm font-medium text-ink">{s.label}</label>
                      {s.is_overridden && <Badge tone="violet">Overridden</Badge>}
                    </div>
                    <p className="mt-0.5 text-xs text-ink-muted">{s.description}</p>
                    <p className="mt-0.5 text-xs text-ink-faint">
                      Default {String(s.default)}{s.updated_at && s.is_overridden ? ` · changed ${formatDateTime(s.updated_at)}${s.updated_by ? ` by ${s.updated_by}` : ""}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {s.type === "bool" ? (
                      <Toggle label={s.label} checked={Boolean(draft[s.key])} disabled={!editable} onChange={(v) => setDraft({ ...draft, [s.key]: v })} />
                    ) : (
                      <Input id={`s-${s.key}`} type="number" className="h-8 w-28 text-right" value={String(draft[s.key] ?? "")} disabled={!editable}
                        min={s.min ?? undefined} max={s.max ?? undefined} step={s.type === "int" ? 1 : 0.01}
                        onChange={(e) => setDraft({ ...draft, [s.key]: e.target.value })} />
                    )}
                    {editable && s.is_overridden && (
                      <Button size="sm" variant="ghost" title="Reset to the environment default" onClick={() => ask({
                        title: `Reset “${s.label}”?`, message: `It returns to the environment default (${String(s.default)}).`, confirmLabel: "Reset",
                      }, () => save.mutateAsync({ [s.key]: null }))}>Reset</Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
      {dialog}
    </>
  );
}

export default function SettingsPage() {
  return <RequirePermission permission="settings.view"><Settings /></RequirePermission>;
}
