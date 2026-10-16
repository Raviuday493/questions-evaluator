"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, Pencil, Power, Trash2 } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { ActiveBadge, OriginalityValue, PageHeader, PaperStatusBadge, RoleBadge, StatCard } from "@/components/ui/common";
import { ErrorState, Modal, useConfirm, useToast } from "@/components/ui/feedback";
import { Button, Card, DetailList, Field, Input, Select, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { ROLE_LABELS, USER_ROLES, formatDateTime, formatNumber, formatRelative, humanize } from "@/utils/format";
import type { AppUserDetail, UserRole } from "@/types";

function EditUserModal({ user, open, onClose }: { user: AppUserDetail; open: boolean; onClose: () => void }) {
  const toast = useToast();
  const client = useQueryClient();
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => adminApi.departments.list(), enabled: open });
  const [form, setForm] = useState({ email: user.email, full_name: user.full_name, role: user.role, department_id: user.department?.id ?? "" });
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setForm({ email: user.email, full_name: user.full_name, role: user.role, department_id: user.department?.id ?? "" });
      setError(null);
    }
  }, [open, user]);
  const save = useMutation({
    mutationFn: () => adminApi.users.update(user.id, {
      email: form.email,
      full_name: form.full_name,
      role: form.role,
      ...(form.department_id ? { department_id: form.department_id } : { clear_department: true }),
    }),
    onSuccess: () => {
      toast.success("User updated.");
      client.invalidateQueries({ queryKey: ["users"] });
      client.invalidateQueries({ queryKey: ["user", user.id] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save changes."),
  });
  const roleChanged = form.role !== user.role;
  return (
    <Modal open={open} onClose={onClose} title="Edit user" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>Save changes</Button></>}>
      <div className="space-y-3">
        {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
        <Field label="Full name" htmlFor="e-name" required>
          <Input id="e-name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} maxLength={255} />
        </Field>
        <Field label="Email" htmlFor="e-email" required>
          <Input id="e-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Role" htmlFor="e-role" hint={roleChanged ? "Changing the role signs the user out everywhere." : undefined}>
            <Select id="e-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
              {USER_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </Select>
          </Field>
          <Field label="Department" htmlFor="e-dept">
            <Select id="e-dept" value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}>
              <option value="">None</option>
              {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.name}</option>)}
            </Select>
          </Field>
        </div>
      </div>
    </Modal>
  );
}

function ResetPasswordModal({ user, open, onClose }: { user: AppUserDetail; open: boolean; onClose: () => void }) {
  const toast = useToast();
  const [pw, setPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setPw("");
      setError(null);
    }
  }, [open]);
  const reset = useMutation({
    mutationFn: () => adminApi.users.resetPassword(user.id, pw),
    onSuccess: () => {
      toast.success(`Password reset for ${user.email}. They have been signed out everywhere.`);
      onClose();
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Reset failed"),
  });
  const valid = pw.length >= 8 && /[A-Za-z]/.test(pw) && /\d/.test(pw);
  return (
    <Modal open={open} onClose={onClose} title="Reset password" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="danger" disabled={!valid} loading={reset.isPending} onClick={() => reset.mutate()}>Reset password</Button></>}>
      <div className="space-y-3 text-sm text-ink-soft">
        <p>Set a temporary password for <strong className="text-ink">{user.email}</strong>. All their current sessions will end.</p>
        {error && <p className="text-red-700" role="alert">{error}</p>}
        <Field label="New password" htmlFor="r-pw" hint="At least 8 characters with a letter and a digit.">
          <Input id="r-pw" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} maxLength={72} />
        </Field>
      </div>
    </Modal>
  );
}

function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const [editing, setEditing] = useState(false);
  const [resetting, setResetting] = useState(false);
  const q = useQuery({ queryKey: ["user", id], queryFn: () => adminApi.users.get(id) });

  const refresh = () => {
    client.invalidateQueries({ queryKey: ["user", id] });
    client.invalidateQueries({ queryKey: ["users"] });
  };
  const run = (fn: () => Promise<unknown>, success: string) => async () => {
    try {
      await fn();
      toast.success(success);
      refresh();
    } catch (e) {
      toast.error(e);
      throw e;
    }
  };

  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-48" /></div>;
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>;
  const u = q.data;

  return (
    <>
      <PageHeader
        back={{ href: "/users", label: "Users" }}
        title={u.full_name}
        description={u.email}
        actions={
          <>
            {can("users.edit") && <Button icon={<Pencil size={14} />} onClick={() => setEditing(true)}>Edit</Button>}
            {can("users.edit") && <Button icon={<KeyRound size={14} />} onClick={() => setResetting(true)}>Reset password</Button>}
            {can("users.status") && (
              <Button icon={<LogOut size={14} />} onClick={() => ask({
                title: "Sign this user out everywhere?",
                message: "All existing sessions on every device end immediately. The user can sign in again.",
                confirmLabel: "Sign out everywhere",
              }, run(() => adminApi.users.revokeSessions(u.id), "User signed out of all sessions."))}>Sign out everywhere</Button>
            )}
            {can("users.status") && (u.is_active ? (
              <Button variant="danger" icon={<Power size={14} />} onClick={() => ask({
                title: `Deactivate ${u.full_name}?`,
                message: "They will be signed out immediately and cannot sign in until reactivated. Their papers and reports are kept.",
                confirmLabel: "Deactivate",
                danger: true,
                reasonLabel: "Reason (recorded in the audit log)",
              }, (reason) => run(() => adminApi.users.deactivate(u.id, reason || undefined), "User deactivated.")())}>Deactivate</Button>
            ) : (
              <Button variant="primary" icon={<Power size={14} />} onClick={() => ask({
                title: `Reactivate ${u.full_name}?`, message: "The user will be able to sign in again.", confirmLabel: "Activate",
              }, run(() => adminApi.users.activate(u.id), "User activated."))}>Activate</Button>
            ))}
            {can("users.delete") && (
              <Button variant="ghost" className="text-red-700" icon={<Trash2 size={14} />} onClick={() => ask({
                title: "Permanently delete this user?",
                message: u.stats.papers_total
                  ? `This user owns ${u.stats.papers_total} paper(s), so the server will refuse deletion. Deactivate the account instead.`
                  : "The account is removed permanently. Audit entries are kept but no longer linked to a name.",
                confirmLabel: "Delete user",
                danger: true,
                typeToConfirm: u.email,
              }, async () => {
                try {
                  await adminApi.users.remove(u.id);
                  toast.success("User deleted.");
                  client.invalidateQueries({ queryKey: ["users"] });
                  router.replace("/users");
                } catch (e) {
                  toast.error(e, "Could not delete user");
                  throw e;
                }
              })}>Delete</Button>
            )}
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Profile" className="lg:col-span-2">
          <DetailList items={[
            { label: "Role", value: <RoleBadge role={u.role} /> },
            { label: "Status", value: <ActiveBadge active={u.is_active} /> },
            { label: "Department", value: u.department ? `${u.department.code} · ${u.department.name}` : "—" },
            { label: "Joined", value: formatDateTime(u.created_at) },
            { label: "Last sign-in", value: u.last_login_at ? `${formatDateTime(u.last_login_at)} (${formatRelative(u.last_login_at)})` : "Never" },
            { label: "Last activity", value: u.stats.last_activity_at ? formatRelative(u.stats.last_activity_at) : "None recorded" },
            { label: "Sessions revoked", value: u.sessions_invalidated_at ? formatDateTime(u.sessions_invalidated_at) : "Never" },
            { label: "User ID", value: <code className="text-xs text-ink-muted">{u.id}</code> },
          ]} />
        </Card>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
          <StatCard label="Papers uploaded" value={formatNumber(u.stats.papers_total)} hint={`${u.stats.approved} approved · ${u.stats.failed} failed`} href={`/papers?uploader_id=${u.id}`} />
          <StatCard label="Average originality (drafts)" value={<OriginalityValue value={u.stats.avg_originality} />} />
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card title="Recent papers" padded={false} actions={u.stats.papers_total > 0 && <Link className="text-xs font-medium text-brand-600 hover:underline" href={`/papers?uploader_id=${u.id}`}>View all</Link>}>
          {!u.recent_papers.length ? <p className="p-4 text-sm text-ink-muted">No papers uploaded.</p> : (
            <table className="min-w-full text-sm">
              <tbody className="divide-y divide-line">
                {u.recent_papers.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5">
                      <Link href={`/papers/${p.id}`} className="font-medium text-ink hover:underline">{p.course_code}</Link>
                      <div className="text-xs text-ink-muted">{p.exam_type} · {p.term} {p.academic_year}{p.is_historical_archive ? " · archive" : ""}</div>
                    </td>
                    <td className="px-4 py-2.5"><PaperStatusBadge status={p.status} /></td>
                    <td className="px-4 py-2.5 text-right"><OriginalityValue value={p.originality_score} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Recent activity">
          {!u.recent_activity.length ? <p className="text-sm text-ink-muted">No activity recorded.</p> : (
            <ul className="divide-y divide-line text-sm">
              {u.recent_activity.map((a) => (
                <li key={a.id} className="flex justify-between gap-3 py-2">
                  <span className="text-ink">{humanize(a.action)}</span>
                  <span className="shrink-0 text-xs text-ink-faint" title={formatDateTime(a.created_at)}>{formatRelative(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        {can("audit.view") && (
          <Card title="Admin actions on this account" className="xl:col-span-2" actions={<Link className="text-xs font-medium text-brand-600 hover:underline" href={`/audit-logs?entity_id=${u.id}`}>Audit log</Link>}>
            {!u.admin_actions.length ? <p className="text-sm text-ink-muted">No admin actions yet.</p> : (
              <ul className="divide-y divide-line text-sm">
                {u.admin_actions.map((a) => (
                  <li key={a.id} className="flex justify-between gap-3 py-2">
                    <span><span className="font-medium text-ink">{humanize(a.action)}</span> <span className="text-ink-muted">by {a.admin_name ?? "deleted admin"}</span>
                      {typeof a.details?.reason === "string" && a.details.reason && <span className="text-ink-muted"> — “{a.details.reason}”</span>}</span>
                    <span className="shrink-0 text-xs text-ink-faint">{formatDateTime(a.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>

      <EditUserModal user={u} open={editing} onClose={() => setEditing(false)} />
      <ResetPasswordModal user={u} open={resetting} onClose={() => setResetting(false)} />
      {dialog}
    </>
  );
}

export default function UserDetailPage() {
  return <RequirePermission permission="users.view"><UserDetail /></RequirePermission>;
}
