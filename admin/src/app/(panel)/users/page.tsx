"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { RequirePermission } from "@/components/layout/Shell";
import { DataTable, type Column } from "@/components/table/DataTable";
import { ActiveBadge, PageHeader, RoleBadge, SearchInput } from "@/components/ui/common";
import { Modal, useConfirm, useToast } from "@/components/ui/feedback";
import { Button, Field, Input, Select } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useDebounced, useUrlState } from "@/hooks/useUrlState";
import { ROLE_LABELS, USER_ROLES, formatDate, formatRelative } from "@/utils/format";
import type { AppUser, UserRole } from "@/types";

const DEFAULTS = { search: "", role: "", department_id: "", active: "", from: "", to: "", sort: "created_at", order: "desc", page: "1", limit: "20" };

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const client = useQueryClient();
  const router = useRouter();
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => adminApi.departments.list(), enabled: open });
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "FACULTY" as UserRole, department_id: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => {
    if (open) {
      setForm({ email: "", full_name: "", password: "", role: "FACULTY", department_id: "" });
      setErrors({});
    }
  }, [open]);
  const create = useMutation({
    mutationFn: () => adminApi.users.create({ ...form, department_id: form.department_id || null }),
    onSuccess: (user) => {
      toast.success(`Created ${user.email}.`);
      client.invalidateQueries({ queryKey: ["users"] });
      onClose();
      router.push(`/users/${user.id}`);
    },
    onError: (e) => {
      if (e instanceof ApiError && e.fieldErrors.length) setErrors(Object.fromEntries(e.fieldErrors.map((f) => [f.field, f.message])));
      toast.error(e, "Could not create user");
    },
  });
  const submit = () => {
    const next: Record<string, string> = {};
    if (!/^\S+@\S+\.\S+$/.test(form.email)) next.email = "Enter a valid email address.";
    if (form.full_name.trim().length < 2) next.full_name = "Name must be at least 2 characters.";
    if (form.password.length < 8 || !/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)) next.password = "At least 8 characters with a letter and a digit.";
    if (form.role === "DEPT_HEAD" && !form.department_id) next.department_id = "Department heads need a department.";
    setErrors(next);
    if (!Object.keys(next).length) create.mutate();
  };
  return (
    <Modal open={open} onClose={onClose} title="Create user" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={create.isPending} onClick={submit}>Create user</Button></>}>
      <div className="space-y-3">
        <Field label="Email" htmlFor="u-email" error={errors.email} required>
          <Input id="u-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Full name" htmlFor="u-name" error={errors.full_name} required>
          <Input id="u-name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} maxLength={255} />
        </Field>
        <Field label="Initial password" htmlFor="u-pw" error={errors.password} hint="Share it securely; the user should change it after signing in." required>
          <Input id="u-pw" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} maxLength={72} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Role" htmlFor="u-role">
            <Select id="u-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
              {USER_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </Select>
          </Field>
          <Field label="Department" htmlFor="u-dept" error={errors.department_id}>
            <Select id="u-dept" value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}>
              <option value="">None</option>
              {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.name}</option>)}
            </Select>
          </Field>
        </div>
      </div>
    </Modal>
  );
}

function UsersTable() {
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const router = useRouter();
  const { ask, dialog } = useConfirm();
  const [state, setState] = useUrlState(DEFAULTS);
  const [search, setSearch] = useState(state.search);
  const debounced = useDebounced(search);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (debounced !== state.search) setState({ search: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const filters = { search: state.search, role: state.role, department_id: state.department_id, active: state.active, from: state.from, to: state.to };
  const params = { ...filters, sort: state.sort, order: state.order, page: state.page, limit: state.limit };
  const users = useQuery({ queryKey: ["users", params], queryFn: () => adminApi.users.list(params), placeholderData: keepPreviousData });
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => adminApi.departments.list(), enabled: can("catalog.view") });

  useEffect(() => setSelected(new Set()), [state.search, state.role, state.department_id, state.active, state.page]);

  const bulk = useMutation({
    mutationFn: (action: "activate" | "deactivate" | "revoke_sessions") => adminApi.users.bulk(Array.from(selected), action),
    onSuccess: (r) => {
      toast.success(`Updated ${r.changed} of ${r.requested} users.`);
      setSelected(new Set());
      client.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (e) => toast.error(e, "Bulk action failed"),
  });

  const columns: Column<AppUser>[] = [
    { key: "name", header: "User", sortKey: "full_name", alwaysVisible: true, render: (u) => (
      <Link href={`/users/${u.id}`} className="block min-w-[180px] hover:underline">
        <span className="font-medium text-ink">{u.full_name}</span>
        <span className="block text-xs text-ink-muted">{u.email}</span>
      </Link>
    ) },
    { key: "role", header: "Role", sortKey: "role", render: (u) => <RoleBadge role={u.role} /> },
    { key: "department", header: "Department", render: (u) => u.department ? <span title={u.department.name}>{u.department.code}</span> : <span className="text-ink-faint">—</span> },
    { key: "status", header: "Status", render: (u) => <ActiveBadge active={u.is_active} /> },
    { key: "papers", header: "Papers", className: "text-right tabular-nums", render: (u) => u.paper_count },
    { key: "last_login", header: "Last sign-in", sortKey: "last_login_at", render: (u) => <span title={u.last_login_at ?? undefined}>{formatRelative(u.last_login_at)}</span> },
    { key: "created", header: "Joined", sortKey: "created_at", render: (u) => formatDate(u.created_at) },
    { key: "email", header: "Email", sortKey: "email", defaultHidden: true, render: (u) => u.email },
  ];

  const bulkConfirm = (action: "activate" | "deactivate" | "revoke_sessions") => {
    const labels = { activate: "Activate", deactivate: "Deactivate", revoke_sessions: "Sign out" };
    ask({
      title: `${labels[action]} ${selected.size} user(s)?`,
      message: action === "deactivate"
        ? "Deactivated users are signed out immediately and cannot sign in until reactivated. Their papers are kept."
        : action === "revoke_sessions" ? "The selected users will be signed out of every device." : "The selected users will be able to sign in again.",
      confirmLabel: labels[action],
      danger: action !== "activate",
    }, () => bulk.mutateAsync(action));
  };

  return (
    <>
      <PageHeader
        title="Users"
        description="Faculty, department heads and application administrators of the main website."
        actions={can("users.create") && <Button variant="primary" icon={<UserPlus size={15} />} onClick={() => setCreating(true)}>Create user</Button>}
      />
      <DataTable
        storageKey="users"
        columns={columns}
        rows={users.data?.items}
        rowKey={(u) => u.id}
        loading={users.isLoading}
        fetching={users.isFetching}
        error={users.error}
        onRetry={() => users.refetch()}
        onRefresh={() => users.refetch()}
        onRowClick={(u) => router.push(`/users/${u.id}`)}
        exporting={exporting}
        onExport={can("reports.export") ? async () => {
          setExporting(true);
          try {
            await adminApi.users.export(filters);
            toast.success("Export downloaded.");
          } catch (e) {
            toast.error(e, "Export failed");
          } finally {
            setExporting(false);
          }
        } : undefined}
        sort={{ key: state.sort, order: state.order as "asc" | "desc", onChange: (sort, order) => setState({ sort, order }) }}
        selection={can("users.status") ? {
          selected,
          onChange: setSelected,
          bulkActions: (
            <>
              <Button size="sm" onClick={() => bulkConfirm("activate")}>Activate</Button>
              <Button size="sm" onClick={() => bulkConfirm("revoke_sessions")}>Sign out everywhere</Button>
              <Button size="sm" variant="danger" onClick={() => bulkConfirm("deactivate")}>Deactivate</Button>
            </>
          ),
        } : undefined}
        pagination={users.data && {
          page: users.data.page, limit: users.data.limit, total: users.data.total, totalPages: users.data.total_pages,
          onPage: (p) => setState({ page: String(p) }), onLimit: (l) => setState({ limit: String(l) }),
        }}
        emptyTitle="No users match these filters"
        toolbar={
          <>
            <SearchInput value={search} onChange={setSearch} placeholder="Search name or email" label="Search users" />
            <Select aria-label="Filter by role" className="h-8 w-auto" value={state.role} onChange={(e) => setState({ role: e.target.value })}>
              <option value="">All roles</option>
              {USER_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </Select>
            {departments.data && (
              <Select aria-label="Filter by department" className="h-8 w-auto" value={state.department_id} onChange={(e) => setState({ department_id: e.target.value })}>
                <option value="">All departments</option>
                {departments.data.map((d) => <option key={d.id} value={d.id}>{d.code}</option>)}
              </Select>
            )}
            <Select aria-label="Filter by status" className="h-8 w-auto" value={state.active} onChange={(e) => setState({ active: e.target.value })}>
              <option value="">Any status</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </Select>
            <label className="flex items-center gap-1 text-xs text-ink-muted">
              Joined
              <Input type="date" aria-label="Joined from" className="h-8 w-auto" value={state.from} max={state.to || undefined} onChange={(e) => setState({ from: e.target.value })} />
              –
              <Input type="date" aria-label="Joined to" className="h-8 w-auto" value={state.to} min={state.from || undefined} onChange={(e) => setState({ to: e.target.value })} />
            </label>
          </>
        }
      />
      <CreateUserModal open={creating} onClose={() => setCreating(false)} />
      {dialog}
    </>
  );
}

export default function UsersPage() {
  return <RequirePermission permission="users.view"><UsersTable /></RequirePermission>;
}
