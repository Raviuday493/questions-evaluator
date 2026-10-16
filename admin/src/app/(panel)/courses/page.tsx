"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { RequirePermission } from "@/components/layout/Shell";
import { DataTable, type Column } from "@/components/table/DataTable";
import { PageHeader, SearchInput } from "@/components/ui/common";
import { Modal, useToast } from "@/components/ui/feedback";
import { CourseForm, currentAcademicYear, validateCourse } from "@/components/CourseForm";
import { Badge, Button, Select } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { useDebounced, useUrlState } from "@/hooks/useUrlState";
import { formatDate } from "@/utils/format";
import type { Course, Department } from "@/types";

const DEFAULTS = { search: "", department_id: "", sort: "code", order: "asc", page: "1", limit: "20" };

function CreateCourseModal({ open, onClose, departments }: { open: boolean; onClose: () => void; departments: Department[] | undefined }) {
  const toast = useToast();
  const client = useQueryClient();
  const router = useRouter();
  const [form, setForm] = useState({ department_id: "", code: "", title: "", academic_year: currentAcademicYear() });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setForm({ department_id: "", code: "", title: "", academic_year: currentAcademicYear() });
      setErrors({});
      setServerError(null);
    }
  }, [open]);
  const create = useMutation({
    mutationFn: () => adminApi.courses.create(form),
    onSuccess: (c) => {
      toast.success(`Created ${c.code}.`);
      client.invalidateQueries({ queryKey: ["courses"] });
      client.invalidateQueries({ queryKey: ["departments"] });
      onClose();
      router.push(`/courses/${c.id}`);
    },
    onError: (e) => setServerError(e instanceof ApiError ? e.message : "Could not create course."),
  });
  return (
    <Modal open={open} onClose={onClose} title="New course" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={create.isPending} onClick={() => {
      const next = validateCourse(form);
      setErrors(next);
      if (!Object.keys(next).length) create.mutate();
    }}>Create course</Button></>}>
      {serverError && <p className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{serverError}</p>}
      <CourseForm value={form} onChange={setForm} departments={departments} errors={errors} />
    </Modal>
  );
}

function Courses() {
  const { can } = useAdmin();
  const router = useRouter();
  const [state, setState] = useUrlState(DEFAULTS);
  const [search, setSearch] = useState(state.search);
  const debounced = useDebounced(search);
  const [creating, setCreating] = useState(false);
  useEffect(() => {
    if (debounced !== state.search) setState({ search: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);
  const q = useQuery({ queryKey: ["courses", state], queryFn: () => adminApi.courses.list(state), placeholderData: keepPreviousData });
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => adminApi.departments.list() });

  const columns: Column<Course>[] = [
    { key: "code", header: "Course", sortKey: "code", alwaysVisible: true, render: (c) => (
      <Link href={`/courses/${c.id}`} className="block hover:underline"><span className="font-medium text-ink">{c.code}</span><span className="block text-xs text-ink-muted">{c.title}</span></Link>
    ) },
    { key: "title", header: "Title", sortKey: "title", defaultHidden: true, render: (c) => c.title },
    { key: "department", header: "Department", render: (c) => c.department?.code ?? "—" },
    { key: "year", header: "Academic year", sortKey: "academic_year", render: (c) => c.academic_year },
    { key: "syllabus", header: "Syllabus", render: (c) => c.unit_count ? <Badge tone="green">{c.unit_count} units</Badge> : <Badge tone="amber">Not set</Badge> },
    { key: "papers", header: "Papers", className: "text-right tabular-nums", render: (c) => <Link className="hover:underline" href={`/papers?course_id=${c.id}`}>{c.paper_count}</Link> },
    { key: "created", header: "Created", sortKey: "created_at", render: (c) => formatDate(c.created_at) },
  ];

  return (
    <>
      <PageHeader title="Courses & syllabi" description="Courses are created automatically on first upload; define syllabus units here so analyses report unit coverage."
        actions={can("catalog.edit") && <Button variant="primary" icon={<Plus size={15} />} onClick={() => setCreating(true)}>New course</Button>} />
      <DataTable
        storageKey="courses"
        columns={columns}
        rows={q.data?.items}
        rowKey={(c) => c.id}
        loading={q.isLoading}
        fetching={q.isFetching}
        error={q.error}
        onRetry={() => q.refetch()}
        onRefresh={() => q.refetch()}
        onRowClick={(c) => router.push(`/courses/${c.id}`)}
        sort={{ key: state.sort, order: state.order as "asc" | "desc", onChange: (sort, order) => setState({ sort, order }) }}
        pagination={q.data && {
          page: q.data.page, limit: q.data.limit, total: q.data.total, totalPages: q.data.total_pages,
          onPage: (p) => setState({ page: String(p) }), onLimit: (l) => setState({ limit: String(l) }),
        }}
        emptyTitle="No courses found"
        toolbar={
          <>
            <SearchInput value={search} onChange={setSearch} placeholder="Search code or title" label="Search courses" />
            <Select aria-label="Filter by department" className="h-8 w-auto" value={state.department_id} onChange={(e) => setState({ department_id: e.target.value })}>
              <option value="">All departments</option>
              {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.code}</option>)}
            </Select>
          </>
        }
      />
      <CreateCourseModal open={creating} onClose={() => setCreating(false)} departments={departments.data} />
    </>
  );
}

export default function CoursesPage() {
  return <RequirePermission permission="catalog.view"><Courses /></RequirePermission>;
}
