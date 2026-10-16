"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Pencil, Plus, Trash2 } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { PageHeader } from "@/components/ui/common";
import { ErrorState, Modal, useConfirm, useToast } from "@/components/ui/feedback";
import { Badge, Button, Card, Checkbox, Field, Input, Skeleton, Textarea } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import type { AdminRole, Permission } from "@/types";

function groupPermissions(perms: Permission[]): [string, Permission[]][] {
  const groups = new Map<string, Permission[]>();
  perms.forEach((p) => groups.set(p.group, [...(groups.get(p.group) ?? []), p]));
  return Array.from(groups.entries());
}

function RoleModal({ open, onClose, role, catalog }: { open: boolean; onClose: () => void; role: AdminRole | null; catalog: Permission[] }) {
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [perms, setPerms] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setName(role?.name ?? "");
      setDescription(role?.description ?? "");
      setPerms(new Set(role?.permissions ?? []));
      setError(null);
    }
  }, [open, role]);
  const save = useMutation({
    mutationFn: () => {
      const body = { name, description, permissions: Array.from(perms) };
      return role ? adminApi.roles.update(role.id, body) : adminApi.roles.create(body);
    },
    onSuccess: (r) => {
      toast.success(role ? `Role “${r.name}” updated.` : `Role “${r.name}” created.`);
      client.invalidateQueries({ queryKey: ["roles"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save role."),
  });
  return (
    <Modal open={open} onClose={onClose} size="lg" title={role ? `Edit role: ${role.name}` : "New custom role"}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => {
        if (name.trim().length < 2) return setError("Name must be at least 2 characters.");
        setError(null);
        save.mutate();
      }}>{role ? "Save role" : "Create role"}</Button></>}>
      <div className="space-y-4">
        {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name" htmlFor="role-name" required><Input id="role-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} /></Field>
          <Field label="Description" htmlFor="role-desc"><Textarea id="role-desc" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} className="min-h-[36px]" rows={1} /></Field>
        </div>
        <div>
          <p className="mb-2 text-xs text-ink-muted">Permissions you do not hold yourself are locked — you cannot grant more access than you have.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {groupPermissions(catalog).map(([group, items]) => (
              <fieldset key={group} className="rounded-md border border-line p-3">
                <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">{group}</legend>
                {items.map((p) => {
                  const allowed = can(p.key);
                  return (
                    <label key={p.key} className={`flex items-start gap-2 py-1 text-sm ${allowed ? "cursor-pointer" : "opacity-50"}`}>
                      <span className="mt-0.5"><Checkbox label={p.key} checked={perms.has(p.key)} disabled={!allowed && !perms.has(p.key)} onChange={(v) => setPerms((prev) => {
                        const next = new Set(prev);
                        if (v) next.add(p.key); else next.delete(p.key);
                        return next;
                      })} /></span>
                      <span><code className="text-xs text-ink">{p.key}</code><span className="block text-xs text-ink-muted">{p.description}</span></span>
                    </label>
                  );
                })}
              </fieldset>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}

function Roles() {
  const { can, admin } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const roles = useQuery({ queryKey: ["roles"], queryFn: adminApi.roles.list });
  const catalog = useQuery({ queryKey: ["permissions"], queryFn: adminApi.roles.permissions, staleTime: Infinity });
  const [editing, setEditing] = useState<AdminRole | null | undefined>(undefined);
  const manage = can("roles.manage");
  const byKey = useMemo(() => new Map((catalog.data ?? []).map((p) => [p.key, p])), [catalog.data]);

  if (roles.isLoading || catalog.isLoading) return <div className="grid gap-4 lg:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>;
  if (roles.isError || catalog.isError) return <Card><ErrorState error={roles.error ?? catalog.error} onRetry={() => { roles.refetch(); catalog.refetch(); }} /></Card>;

  return (
    <>
      <PageHeader title="Roles & permissions" description="Built-in roles are fixed and kept in sync with the backend. Create custom roles for anything else. Every permission is enforced by the API."
        actions={manage && <Button variant="primary" icon={<Plus size={15} />} onClick={() => setEditing(null)}>New role</Button>} />
      <div className="grid gap-4 lg:grid-cols-2">
        {roles.data!.map((r) => (
          <Card key={r.id} title={
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-ink">{r.name}</h2>
              {r.is_system ? <Badge icon={<Lock size={11} />}>Built-in</Badge> : <Badge tone="violet">Custom</Badge>}
              {admin?.role?.id === r.id && <Badge tone="blue">Your role</Badge>}
            </div>
          } actions={manage && !r.is_system && (
            <>
              <Button size="sm" variant="ghost" aria-label={`Edit ${r.name}`} icon={<Pencil size={14} />} disabled={admin?.role?.id === r.id} onClick={() => setEditing(r)} />
              <Button size="sm" variant="ghost" className="text-red-700" aria-label={`Delete ${r.name}`} icon={<Trash2 size={14} />} onClick={() => ask({
                title: `Delete role “${r.name}”?`,
                message: r.admin_count ? `${r.admin_count} administrator(s) have this role; reassign them first.` : "No administrators use this role.",
                confirmLabel: "Delete role", danger: true,
              }, async () => {
                try {
                  await adminApi.roles.remove(r.id);
                  toast.success("Role deleted.");
                  client.invalidateQueries({ queryKey: ["roles"] });
                } catch (e) {
                  toast.error(e, "Could not delete role");
                  throw e;
                }
              })} />
            </>
          )}>
            <p className="mb-3 text-sm text-ink-muted">{r.description || "No description."} · {r.admin_count} admin{r.admin_count === 1 ? "" : "s"}</p>
            {r.is_wildcard ? <Badge tone="red">All permissions, including future ones</Badge> : (
              <div className="flex flex-wrap gap-1">
                {r.permissions.length ? r.permissions.map((p) => <span key={p} title={byKey.get(p)?.description}><Badge><code>{p}</code></Badge></span>) : <span className="text-sm text-ink-faint">No permissions</span>}
              </div>
            )}
          </Card>
        ))}
      </div>
      <RoleModal open={editing !== undefined} role={editing ?? null} catalog={catalog.data ?? []} onClose={() => setEditing(undefined)} />
      {dialog}
    </>
  );
}

export default function RolesPage() {
  return <RequirePermission permission="admins.view"><Roles /></RequirePermission>;
}
