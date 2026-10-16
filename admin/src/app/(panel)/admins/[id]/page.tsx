"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, Pencil, Power, Trash2, Unlock } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { ActiveBadge, PageHeader } from "@/components/ui/common";
import { ErrorState, Modal, useConfirm, useToast } from "@/components/ui/feedback";
import { Badge, Button, Card, DetailList, Field, Input, Select, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { formatDateTime, formatRelative, humanize } from "@/utils/format";
import { assignableRoles } from "@/utils/roles";
import type { AdminAccountDetail } from "@/types";

function EditAdminModal({ target, open, onClose }: { target: AdminAccountDetail; open: boolean; onClose: () => void }) {
  const { admin, can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: adminApi.roles.list, enabled: open });
  const isSelf = admin?.id === target.id;
  const options = assignableRoles(roles.data, Boolean(admin?.is_super_admin), can);
  const [form, setForm] = useState({ email: target.email, full_name: target.full_name, role_id: target.role?.id ?? "" });
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setForm({ email: target.email, full_name: target.full_name, role_id: target.role?.id ?? "" });
      setError(null);
    }
  }, [open, target]);
  const save = useMutation({
    mutationFn: () => adminApi.admins.update(target.id, {
      email: form.email,
      full_name: form.full_name,
      ...(form.role_id !== target.role?.id ? { role_id: form.role_id } : {}),
    }),
    onSuccess: () => {
      toast.success("Administrator updated.");
      client.invalidateQueries({ queryKey: ["admin-account", target.id] });
      client.invalidateQueries({ queryKey: ["admins"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save."),
  });
  const roleOptions = target.role && !options.some((r) => r.id === target.role!.id) ? [{ id: target.role.id, name: target.role.name }, ...options] : options;
  return (
    <Modal open={open} onClose={onClose} title="Edit administrator" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>Save</Button></>}>
      <div className="space-y-3">
        {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
        <Field label="Full name" htmlFor="ea-name"><Input id="ea-name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} maxLength={255} /></Field>
        <Field label="Email" htmlFor="ea-email"><Input id="ea-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <Field label="Role" htmlFor="ea-role" hint={isSelf ? "You cannot change your own role." : "Changing the role signs this admin out so the new permissions apply."}>
          <Select id="ea-role" value={form.role_id} disabled={isSelf} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
            {roleOptions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function ResetAdminPasswordModal({ target, open, onClose }: { target: AdminAccountDetail; open: boolean; onClose: () => void }) {
  const toast = useToast();
  const [pw, setPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (open) { setPw(""); setError(null); } }, [open]);
  const valid = pw.length >= 12 && /[A-Za-z]/.test(pw) && /\d/.test(pw);
  const reset = useMutation({
    mutationFn: () => adminApi.admins.resetPassword(target.id, pw),
    onSuccess: () => { toast.success("Password reset; the admin has been signed out."); onClose(); },
    onError: (e) => setError(e instanceof Error ? e.message : "Reset failed"),
  });
  return (
    <Modal open={open} onClose={onClose} title="Reset admin password" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="danger" disabled={!valid} loading={reset.isPending} onClick={() => reset.mutate()}>Reset password</Button></>}>
      <div className="space-y-3 text-sm text-ink-soft">
        <p>Set a new password for <strong className="text-ink">{target.email}</strong>. Their sessions end and any lockout is cleared.</p>
        {error && <p className="text-red-700" role="alert">{error}</p>}
        <Field label="New password" htmlFor="ar-pw" hint="At least 12 characters with letters and digits.">
          <Input id="ar-pw" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} maxLength={72} />
        </Field>
      </div>
    </Modal>
  );
}

function AdminDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { admin: me, can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const [editing, setEditing] = useState(false);
  const [resetting, setResetting] = useState(false);
  const q = useQuery({ queryKey: ["admin-account", id], queryFn: () => adminApi.admins.get(id) });

  const act = (fn: () => Promise<unknown>, success: string) => async () => {
    try {
      await fn();
      toast.success(success);
      client.invalidateQueries({ queryKey: ["admin-account", id] });
      client.invalidateQueries({ queryKey: ["admins"] });
    } catch (e) {
      toast.error(e);
      throw e;
    }
  };

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-64" /></div>;
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>;
  const a = q.data;
  const isSelf = me?.id === a.id;
  const manage = can("admins.manage") && (!a.is_super_admin || Boolean(me?.is_super_admin));

  return (
    <>
      <PageHeader
        back={{ href: "/admins", label: "Administrators" }}
        title={a.full_name}
        description={<span className="inline-flex flex-wrap items-center gap-2">{a.email} <Badge tone={a.is_super_admin ? "red" : "neutral"}>{a.role?.name}</Badge>{isSelf && <Badge tone="violet">You</Badge>}</span>}
        actions={manage && (
          <>
            <Button icon={<Pencil size={14} />} onClick={() => setEditing(true)}>Edit</Button>
            {!isSelf && <Button icon={<KeyRound size={14} />} onClick={() => setResetting(true)}>Reset password</Button>}
            {a.is_locked && <Button icon={<Unlock size={14} />} onClick={() => ask({ title: "Unlock this account?", message: "Clears the failed sign-in lockout.", confirmLabel: "Unlock" }, act(() => adminApi.admins.unlock(a.id), "Account unlocked."))}>Unlock</Button>}
            <Button icon={<LogOut size={14} />} onClick={() => ask({
              title: isSelf ? "Sign out your other sessions?" : "Sign this admin out everywhere?",
              message: isSelf ? "Every session except this one ends." : "All of this admin's sessions end immediately.",
              confirmLabel: "Revoke sessions",
            }, act(() => adminApi.admins.revokeSessions(a.id), "Sessions revoked."))}>Revoke sessions</Button>
            {!isSelf && (a.is_active ? (
              <Button variant="danger" icon={<Power size={14} />} onClick={() => ask({
                title: `Disable ${a.full_name}?`,
                message: "They are signed out and cannot sign in until re-enabled. The last active Super Admin cannot be disabled.",
                confirmLabel: "Disable", danger: true,
              }, act(() => adminApi.admins.update(a.id, { is_active: false }), "Administrator disabled."))}>Disable</Button>
            ) : (
              <Button variant="primary" icon={<Power size={14} />} onClick={() => ask({
                title: `Re-enable ${a.full_name}?`, message: "They will be able to sign in again.", confirmLabel: "Enable",
              }, act(() => adminApi.admins.update(a.id, { is_active: true }), "Administrator enabled."))}>Enable</Button>
            ))}
            {!isSelf && (
              <Button variant="ghost" className="text-red-700" icon={<Trash2 size={14} />} onClick={() => ask({
                title: "Delete this administrator?",
                message: "The account and its sessions are removed. Their audit entries remain and are marked as a deleted admin.",
                confirmLabel: "Delete administrator", danger: true, typeToConfirm: a.email,
              }, async () => {
                try {
                  await adminApi.admins.remove(a.id);
                  toast.success("Administrator deleted.");
                  client.invalidateQueries({ queryKey: ["admins"] });
                  router.replace("/admins");
                } catch (e) {
                  toast.error(e, "Could not delete administrator");
                  throw e;
                }
              })}>Delete</Button>
            )}
          </>
        )}
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Account" className="lg:col-span-2">
          <DetailList items={[
            { label: "Status", value: <span className="flex gap-1"><ActiveBadge active={a.is_active} inactiveLabel="Disabled" />{a.is_locked && <Badge tone="orange">Locked until {formatDateTime(a.locked_until)}</Badge>}</span> },
            { label: "Role", value: a.role?.name ?? "—" },
            { label: "Last sign-in", value: a.last_login_at ? `${formatDateTime(a.last_login_at)} (${formatRelative(a.last_login_at)})` : "Never" },
            { label: "Password changed", value: formatDateTime(a.password_changed_at) },
            { label: "Created", value: formatDateTime(a.created_at) },
            { label: "Active sessions", value: a.active_sessions },
          ]} />
        </Card>
        <Card title={`Permissions (${a.permissions.length})`}>
          <div className="flex flex-wrap gap-1">{a.permissions.map((p) => <Badge key={p}><code>{p}</code></Badge>)}</div>
        </Card>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card title="Sessions" padded={false}>
          {!a.sessions.length ? <p className="p-4 text-sm text-ink-muted">No sessions.</p> : (
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-ink-muted"><tr><th className="px-4 py-2 font-medium">Started</th><th className="px-4 py-2 font-medium">Last seen</th><th className="px-4 py-2 font-medium">Status</th><th className="px-4 py-2 font-medium">Client</th></tr></thead>
              <tbody className="divide-y divide-line">
                {a.sessions.map((s) => (
                  <tr key={s.id}>
                    <td className="whitespace-nowrap px-4 py-2">{formatDateTime(s.created_at)}</td>
                    <td className="whitespace-nowrap px-4 py-2">{formatRelative(s.last_seen_at)}</td>
                    <td className="px-4 py-2">{s.is_current ? <Badge tone="violet">This session</Badge> : s.is_active ? <Badge tone="green">Active</Badge> : <Badge>{s.revoked_at ? "Revoked" : "Expired"}</Badge>}</td>
                    <td className="max-w-[200px] truncate px-4 py-2 text-xs text-ink-muted" title={s.user_agent ?? undefined}>{s.user_agent ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        {can("audit.view") && (
          <Card title="Recent actions" actions={<Link href={`/audit-logs?admin_id=${a.id}`} className="text-xs font-medium text-brand-600 hover:underline">Full history</Link>}>
            {!a.recent_actions.length ? <p className="text-sm text-ink-muted">No actions recorded.</p> : (
              <ul className="divide-y divide-line text-sm">
                {a.recent_actions.map((r) => (
                  <li key={r.id} className="flex justify-between gap-3 py-2"><span className="text-ink">{humanize(r.action)}</span><span className="shrink-0 text-xs text-ink-faint">{formatDateTime(r.created_at)}</span></li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>
      <EditAdminModal target={a} open={editing} onClose={() => setEditing(false)} />
      <ResetAdminPasswordModal target={a} open={resetting} onClose={() => setResetting(false)} />
      {dialog}
    </>
  );
}

export default function AdminDetailPage() {
  return <RequirePermission permission="admins.view"><AdminDetail /></RequirePermission>;
}
