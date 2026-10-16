"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, UserPlus } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { DataTable, type Column } from "@/components/table/DataTable";
import { ActiveBadge, PageHeader, SearchInput } from "@/components/ui/common";
import { Modal, useToast } from "@/components/ui/feedback";
import { Badge, Button, Field, Input, Select } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useDebounced } from "@/hooks/useUrlState";
import { formatDate, formatRelative } from "@/utils/format";
import { assignableRoles } from "@/utils/roles";
import type { AdminAccount } from "@/types";

function CreateAdminModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { admin, can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const router = useRouter();
  const roles = useQuery({ queryKey: ["roles"], queryFn: adminApi.roles.list, enabled: open });
  const options = assignableRoles(roles.data, Boolean(admin?.is_super_admin), can);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role_id: "" });
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setForm({ email: "", full_name: "", password: "", role_id: "" });
      setError(null);
    }
  }, [open]);
  const create = useMutation({
    mutationFn: () => adminApi.admins.create(form),
    onSuccess: (a) => {
      toast.success(`Admin ${a.email} created.`);
      client.invalidateQueries({ queryKey: ["admins"] });
      onClose();
      router.push(`/admins/${a.id}`);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not create admin."),
  });
  const submit = () => {
    if (!/^\S+@\S+\.\S+$/.test(form.email)) return setError("Enter a valid email address.");
    if (form.full_name.trim().length < 2) return setError("Name must be at least 2 characters.");
    if (form.password.length < 12 || !/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)) return setError("Password needs 12+ characters with letters and digits.");
    if (!form.role_id) return setError("Choose a role.");
    setError(null);
    create.mutate();
  };
  return (
    <Modal open={open} onClose={onClose} title="Create administrator" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={create.isPending} onClick={submit}>Create admin</Button></>}>
      <div className="space-y-3">
        {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
        <Field label="Email" htmlFor="a-email" required><Input id="a-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <Field label="Full name" htmlFor="a-name" required><Input id="a-name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} maxLength={255} /></Field>
        <Field label="Initial password" htmlFor="a-pw" hint="At least 12 characters with letters and digits." required>
          <Input id="a-pw" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} maxLength={72} />
        </Field>
        <Field label="Role" htmlFor="a-role" hint="You can only assign roles whose permissions you hold yourself." required>
          <Select id="a-role" value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
            <option value="">Select…</option>
            {options.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function Admins() {
  const { can, admin } = useAdmin();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const debounced = useDebounced(search);
  const [creating, setCreating] = useState(false);
  const q = useQuery({ queryKey: ["admins", debounced], queryFn: () => adminApi.admins.list({ search: debounced }) });
  const columns: Column<AdminAccount>[] = [
    { key: "name", header: "Administrator", alwaysVisible: true, render: (a) => (
      <Link href={`/admins/${a.id}`} className="block hover:underline">
        <span className="font-medium text-ink">{a.full_name}</span>{a.id === admin?.id && <Badge tone="violet" className="ml-1.5">You</Badge>}
        <span className="block text-xs text-ink-muted">{a.email}</span>
      </Link>
    ) },
    { key: "role", header: "Role", render: (a) => <Badge tone={a.is_super_admin ? "red" : "neutral"}>{a.role?.name ?? "—"}</Badge> },
    { key: "status", header: "Status", render: (a) => (
      <span className="flex gap-1"><ActiveBadge active={a.is_active} activeLabel="Active" inactiveLabel="Disabled" />{a.is_locked && <Badge tone="orange" icon={<Lock size={11} />}>Locked</Badge>}</span>
    ) },
    { key: "sessions", header: "Active sessions", className: "text-right tabular-nums", render: (a) => a.active_sessions },
    { key: "last_login", header: "Last sign-in", render: (a) => formatRelative(a.last_login_at) },
    { key: "created", header: "Created", render: (a) => formatDate(a.created_at) },
  ];
  return (
    <>
      <PageHeader title="Administrators" description="Accounts that can sign in to this admin console. They are separate from application users."
        actions={can("admins.manage") && <Button variant="primary" icon={<UserPlus size={15} />} onClick={() => setCreating(true)}>New administrator</Button>} />
      <DataTable
        storageKey="admins"
        columns={columns}
        rows={q.data}
        rowKey={(a) => a.id}
        loading={q.isLoading}
        fetching={q.isFetching}
        error={q.error}
        onRetry={() => q.refetch()}
        onRefresh={() => q.refetch()}
        onRowClick={(a) => router.push(`/admins/${a.id}`)}
        toolbar={<SearchInput value={search} onChange={setSearch} placeholder="Search name or email" label="Search administrators" />}
      />
      <CreateAdminModal open={creating} onClose={() => setCreating(false)} />
    </>
  );
}

export default function AdminsPage() {
  return <RequirePermission permission="admins.view"><Admins /></RequirePermission>;
}
