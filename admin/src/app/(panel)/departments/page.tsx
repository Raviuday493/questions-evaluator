"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { DataTable, type Column } from "@/components/table/DataTable";
import { PageHeader, SearchInput } from "@/components/ui/common";
import { Modal, useConfirm, useToast } from "@/components/ui/feedback";
import { Button, Field, Input } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useDebounced } from "@/hooks/useUrlState";
import { formatDate } from "@/utils/format";
import type { Department } from "@/types";

function DepartmentModal({ open, onClose, department }: { open: boolean; onClose: () => void; department: Department | null }) {
  const toast = useToast();
  const client = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setCode(department?.code ?? "");
      setName(department?.name ?? "");
      setError(null);
    }
  }, [open, department]);
  const save = useMutation({
    mutationFn: () => (department ? adminApi.departments.update(department.id, { code, name }) : adminApi.departments.create({ code, name })),
    onSuccess: (d) => {
      toast.success(department ? `Updated ${d.code}.` : `Created ${d.code}.`);
      client.invalidateQueries({ queryKey: ["departments"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save."),
  });
  const submit = () => {
    if (!/^[A-Za-z0-9][A-Za-z0-9-]{1,19}$/.test(code.trim())) return setError("Code must be 2–20 letters, digits or hyphens.");
    if (name.trim().length < 2) return setError("Name must be at least 2 characters.");
    setError(null);
    save.mutate();
  };
  return (
    <Modal open={open} onClose={onClose} title={department ? "Edit department" : "New department"}
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={submit}>{department ? "Save" : "Create"}</Button></>}>
      <div className="space-y-3">
        {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
        <Field label="Code" htmlFor="d-code" hint="Short uppercase identifier, e.g. PHY. Used in course codes and the upload form." required>
          <Input id="d-code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={20} />
        </Field>
        <Field label="Name" htmlFor="d-name" required>
          <Input id="d-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={255} />
        </Field>
      </div>
    </Modal>
  );
}

function Departments() {
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const [search, setSearch] = useState("");
  const debounced = useDebounced(search);
  const [editing, setEditing] = useState<Department | null | undefined>(undefined);
  const q = useQuery({ queryKey: ["departments", debounced], queryFn: () => adminApi.departments.list({ search: debounced }) });

  const columns: Column<Department>[] = [
    { key: "code", header: "Code", alwaysVisible: true, render: (d) => <span className="font-mono font-medium text-ink">{d.code}</span> },
    { key: "name", header: "Name", render: (d) => d.name },
    { key: "courses", header: "Courses", className: "text-right tabular-nums", render: (d) => <Link className="hover:underline" href={`/courses?department_id=${d.id}`}>{d.course_count}</Link> },
    { key: "users", header: "Users", className: "text-right tabular-nums", render: (d) => <Link className="hover:underline" href={`/users?department_id=${d.id}`}>{d.user_count}</Link> },
    { key: "papers", header: "Papers", className: "text-right tabular-nums", render: (d) => <Link className="hover:underline" href={`/papers?department_id=${d.id}`}>{d.paper_count}</Link> },
    { key: "created", header: "Created", render: (d) => formatDate(d.created_at) },
    { key: "actions", header: "", alwaysVisible: true, className: "text-right", render: (d) => (
      <span className="inline-flex gap-1">
        {can("catalog.edit") && <Button size="sm" variant="ghost" aria-label={`Edit ${d.code}`} icon={<Pencil size={14} />} onClick={() => setEditing(d)} />}
        {can("catalog.delete") && (
          <Button size="sm" variant="ghost" className="text-red-700" aria-label={`Delete ${d.code}`} icon={<Trash2 size={14} />} onClick={() => ask({
            title: `Delete ${d.code}?`,
            message: d.course_count || d.user_count
              ? `${d.name} still has ${d.course_count} course(s) and ${d.user_count} user(s); the server will refuse until they are moved or removed.`
              : `${d.name} has no courses or users and will be removed permanently.`,
            confirmLabel: "Delete department",
            danger: true,
          }, async () => {
            try {
              await adminApi.departments.remove(d.id);
              toast.success(`Deleted ${d.code}.`);
              client.invalidateQueries({ queryKey: ["departments"] });
            } catch (e) {
              toast.error(e, "Could not delete department");
              throw e;
            }
          })} />
        )}
      </span>
    ) },
  ];

  return (
    <>
      <PageHeader title="Departments" description="Academic departments that own courses and faculty accounts."
        actions={can("catalog.edit") && <Button variant="primary" icon={<Plus size={15} />} onClick={() => setEditing(null)}>New department</Button>} />
      <DataTable
        storageKey="departments"
        columns={columns}
        rows={q.data}
        rowKey={(d) => d.id}
        loading={q.isLoading}
        fetching={q.isFetching}
        error={q.error}
        onRetry={() => q.refetch()}
        onRefresh={() => q.refetch()}
        emptyTitle="No departments found"
        toolbar={<SearchInput value={search} onChange={setSearch} placeholder="Search code or name" label="Search departments" />}
      />
      <DepartmentModal open={editing !== undefined} department={editing ?? null} onClose={() => setEditing(undefined)} />
      {dialog}
    </>
  );
}

export default function DepartmentsPage() {
  return <RequirePermission permission="catalog.view"><Departments /></RequirePermission>;
}
