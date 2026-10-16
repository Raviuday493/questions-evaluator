"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { PageHeader } from "@/components/ui/common";
import { ErrorState, useConfirm, useToast } from "@/components/ui/feedback";
import { Badge, Button, Card, DetailList, Field, Input, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { formatDateTime, formatRelative } from "@/utils/format";

function ChangePassword() {
  const toast = useToast();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: () => adminApi.auth.changePassword(form.current, form.next),
    onSuccess: () => {
      toast.success("Password changed. Your other sessions were signed out.");
      setForm({ current: "", next: "", confirm: "" });
      setError(null);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not change password."),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (form.next.length < 12 || !/[A-Za-z]/.test(form.next) || !/\d/.test(form.next)) return setError("The new password needs 12+ characters with letters and digits.");
    if (form.next !== form.confirm) return setError("The new passwords do not match.");
    setError(null);
    change.mutate();
  };
  return (
    <Card title="Change password">
      <form onSubmit={submit} className="max-w-sm space-y-3" noValidate>
        {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
        <Field label="Current password" htmlFor="p-cur"><Input id="p-cur" type="password" autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} maxLength={72} /></Field>
        <Field label="New password" htmlFor="p-new" hint="At least 12 characters with letters and digits."><Input id="p-new" type="password" autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} maxLength={72} /></Field>
        <Field label="Confirm new password" htmlFor="p-conf"><Input id="p-conf" type="password" autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} maxLength={72} /></Field>
        <Button type="submit" variant="primary" loading={change.isPending} disabled={!form.current || !form.next}>Update password</Button>
      </form>
    </Card>
  );
}

function Sessions() {
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const q = useQuery({ queryKey: ["my-sessions"], queryFn: adminApi.auth.sessions });
  if (q.isLoading) return <Skeleton className="h-48" />;
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} compact /></Card>;
  return (
    <Card title="Your sessions" padded={false}>
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-ink-muted"><tr><th className="px-4 py-2 font-medium">Started</th><th className="px-4 py-2 font-medium">Last seen</th><th className="px-4 py-2 font-medium">Client</th><th className="px-4 py-2 font-medium">Status</th><th /></tr></thead>
        <tbody className="divide-y divide-line">
          {q.data.map((s) => (
            <tr key={s.id}>
              <td className="whitespace-nowrap px-4 py-2">{formatDateTime(s.created_at)}</td>
              <td className="whitespace-nowrap px-4 py-2">{formatRelative(s.last_seen_at)}</td>
              <td className="max-w-[260px] truncate px-4 py-2 text-xs text-ink-muted" title={s.user_agent ?? undefined}>{s.user_agent ?? "—"}</td>
              <td className="px-4 py-2">{s.is_current ? <Badge tone="violet">This session</Badge> : s.is_active ? <Badge tone="green">Active</Badge> : <Badge>{s.revoked_at ? "Revoked" : "Expired"}</Badge>}</td>
              <td className="px-4 py-2 text-right">
                {s.is_active && !s.is_current && (
                  <Button size="sm" onClick={() => ask({ title: "Sign out this session?", message: "That browser will need to sign in again.", confirmLabel: "Sign out" }, async () => {
                    try {
                      await adminApi.auth.revokeSession(s.id);
                      toast.success("Session signed out.");
                      client.invalidateQueries({ queryKey: ["my-sessions"] });
                    } catch (e) {
                      toast.error(e);
                      throw e;
                    }
                  })}>Sign out</Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {dialog}
    </Card>
  );
}

export default function ProfilePage() {
  const { admin } = useAdmin();
  if (!admin) return null;
  return (
    <>
      <PageHeader title="My profile" description="Your admin account, password and active sessions." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Account">
          <DetailList items={[
            { label: "Name", value: admin.full_name },
            { label: "Email", value: admin.email },
            { label: "Role", value: admin.role?.name ?? "—" },
            { label: "Last sign-in", value: formatDateTime(admin.last_login_at) },
            { label: "Session expires", value: admin.session ? `${formatDateTime(admin.session.expires_at)} (after ${admin.session.idle_timeout_minutes} min idle)` : "—" },
            { label: "Permissions", value: `${admin.permissions.length} granted` },
          ]} />
        </Card>
        <ChangePassword />
      </div>
      <div className="mt-4"><Sessions /></div>
    </>
  );
}
