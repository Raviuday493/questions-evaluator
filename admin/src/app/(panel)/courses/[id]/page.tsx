"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { ApiError } from "@/api/client";
import { adminApi } from "@/api/endpoints";
import { CourseForm, validateCourse } from "@/components/CourseForm";
import { RequirePermission } from "@/components/layout/Shell";
import { OriginalityValue, PageHeader, StatCard } from "@/components/ui/common";
import { ErrorState, Modal, useConfirm, useToast } from "@/components/ui/feedback";
import { Button, Card, Input, Skeleton } from "@/components/ui/primitives";
import { useAdmin } from "@/hooks/useAdmin";
import { formatNumber } from "@/utils/format";
import type { CourseDetail } from "@/types";

interface UnitDraft {
  unit_number: string;
  title: string;
  target_weightage_percent: string;
  keywords: string;
}

function toDraft(c: CourseDetail): UnitDraft[] {
  return c.syllabus.map((u) => ({
    unit_number: String(u.unit_number),
    title: u.title,
    target_weightage_percent: String(u.target_weightage_percent),
    keywords: u.keywords.join(", "),
  }));
}

function SyllabusEditor({ course }: { course: CourseDetail }) {
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const [units, setUnits] = useState<UnitDraft[]>(() => toDraft(course));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setUnits(toDraft(course)), [course]);
  const editable = can("catalog.edit");
  const total = units.reduce((sum, u) => sum + (Number(u.target_weightage_percent) || 0), 0);
  const dirty = JSON.stringify(units) !== JSON.stringify(toDraft(course));

  const save = useMutation({
    mutationFn: () => adminApi.courses.saveSyllabus(course.id, units.map((u) => ({
      unit_number: Number(u.unit_number),
      title: u.title.trim(),
      target_weightage_percent: Number(u.target_weightage_percent),
      keywords: u.keywords.split(",").map((k) => k.trim()).filter(Boolean),
    }))),
    onSuccess: () => {
      toast.success("Syllabus saved. New analyses will use it; existing reports keep their unit tags until re-analysed.");
      client.invalidateQueries({ queryKey: ["course", course.id] });
      client.invalidateQueries({ queryKey: ["courses"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save syllabus."),
  });

  const validate = (): string | null => {
    const numbers = units.map((u) => Number(u.unit_number));
    if (units.some((u) => !Number.isInteger(Number(u.unit_number)) || Number(u.unit_number) < 1 || Number(u.unit_number) > 50)) return "Unit numbers must be whole numbers between 1 and 50.";
    if (new Set(numbers).size !== numbers.length) return "Unit numbers must be unique.";
    if (units.some((u) => !u.title.trim())) return "Every unit needs a title.";
    if (units.some((u) => u.target_weightage_percent === "" || Number.isNaN(Number(u.target_weightage_percent)) || Number(u.target_weightage_percent) < 0 || Number(u.target_weightage_percent) > 100)) return "Weightages must be between 0 and 100.";
    if (units.length && Math.abs(total - 100) > 0.5) return `Weightages must sum to 100% (currently ${total.toFixed(1)}%).`;
    return null;
  };

  const update = (i: number, patch: Partial<UnitDraft>) => setUnits((all) => all.map((u, j) => (j === i ? { ...u, ...patch } : u)));

  return (
    <Card
      title="Syllabus units"
      padded={false}
      actions={editable && (
        <>
          {dirty && <Button size="sm" variant="ghost" icon={<X size={14} />} onClick={() => { setUnits(toDraft(course)); setError(null); }}>Discard</Button>}
          <Button size="sm" variant="primary" icon={<Save size={14} />} disabled={!dirty} loading={save.isPending} onClick={() => {
            const problem = validate();
            setError(problem);
            if (!problem) save.mutate();
          }}>Save syllabus</Button>
        </>
      )}
    >
      {error && <p className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{error}</p>}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-ink-muted">
            <tr><th className="w-20 px-3 py-2 font-medium">Unit #</th><th className="px-3 py-2 font-medium">Title</th><th className="w-28 px-3 py-2 font-medium">Weight %</th><th className="px-3 py-2 font-medium">Keywords (comma separated)</th>{editable && <th className="w-10" />}</tr>
          </thead>
          <tbody className="divide-y divide-line">
            {units.map((u, i) => (
              <tr key={i}>
                <td className="px-3 py-2"><Input aria-label={`Unit ${i + 1} number`} type="number" min={1} max={50} value={u.unit_number} disabled={!editable} onChange={(e) => update(i, { unit_number: e.target.value })} className="h-8" /></td>
                <td className="px-3 py-2"><Input aria-label={`Unit ${i + 1} title`} value={u.title} disabled={!editable} maxLength={255} onChange={(e) => update(i, { title: e.target.value })} className="h-8" /></td>
                <td className="px-3 py-2"><Input aria-label={`Unit ${i + 1} weight`} type="number" min={0} max={100} step="0.5" value={u.target_weightage_percent} disabled={!editable} onChange={(e) => update(i, { target_weightage_percent: e.target.value })} className="h-8" /></td>
                <td className="px-3 py-2"><Input aria-label={`Unit ${i + 1} keywords`} value={u.keywords} disabled={!editable} onChange={(e) => update(i, { keywords: e.target.value })} className="h-8" placeholder="velocity, acceleration" /></td>
                {editable && <td className="px-2 py-2"><Button size="sm" variant="ghost" aria-label={`Remove unit ${i + 1}`} icon={<Trash2 size={14} />} onClick={() => setUnits((all) => all.filter((_, j) => j !== i))} /></td>}
              </tr>
            ))}
            {!units.length && <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-ink-muted">No syllabus units. Analyses of this course will not report unit coverage.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-sm">
        {editable ? (
          <Button size="sm" icon={<Plus size={14} />} disabled={units.length >= 50} onClick={() => setUnits((all) => [...all, {
            unit_number: String(Math.max(0, ...all.map((u) => Number(u.unit_number) || 0)) + 1), title: "", target_weightage_percent: "0", keywords: "",
          }])}>Add unit</Button>
        ) : <span />}
        <span className={Math.abs(total - 100) > 0.5 && units.length ? "font-medium text-red-700" : "text-ink-muted"}>Total weight: {total.toFixed(1)}%</span>
      </div>
    </Card>
  );
}

function EditCourseModal({ course, open, onClose }: { course: CourseDetail; open: boolean; onClose: () => void }) {
  const toast = useToast();
  const client = useQueryClient();
  const departments = useQuery({ queryKey: ["departments"], queryFn: () => adminApi.departments.list(), enabled: open });
  const initial = { department_id: course.department?.id ?? "", code: course.code, title: course.title, academic_year: course.academic_year };
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setForm({ department_id: course.department?.id ?? "", code: course.code, title: course.title, academic_year: course.academic_year });
      setErrors({});
      setServerError(null);
    }
  }, [open, course]);
  const save = useMutation({
    mutationFn: () => adminApi.courses.update(course.id, form),
    onSuccess: () => {
      toast.success("Course updated.");
      client.invalidateQueries({ queryKey: ["course", course.id] });
      client.invalidateQueries({ queryKey: ["courses"] });
      onClose();
    },
    onError: (e) => setServerError(e instanceof ApiError ? e.message : "Could not save."),
  });
  return (
    <Modal open={open} onClose={onClose} title="Edit course" footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" loading={save.isPending} onClick={() => {
      const next = validateCourse(form);
      setErrors(next);
      if (!Object.keys(next).length) save.mutate();
    }}>Save</Button></>}>
      {serverError && <p className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">{serverError}</p>}
      <CourseForm value={form} onChange={setForm} departments={departments.data} errors={errors} />
    </Modal>
  );
}

function CourseDetailView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAdmin();
  const toast = useToast();
  const client = useQueryClient();
  const { ask, dialog } = useConfirm();
  const [editing, setEditing] = useState(false);
  const q = useQuery({ queryKey: ["course", id], queryFn: () => adminApi.courses.get(id) });
  if (q.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-64" /></div>;
  if (q.isError || !q.data) return <Card><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>;
  const c = q.data;
  return (
    <>
      <PageHeader
        back={{ href: "/courses", label: "Courses" }}
        title={`${c.code} · ${c.title}`}
        description={`${c.department?.name ?? "No department"} · ${c.academic_year}`}
        actions={
          <>
            {can("catalog.edit") && <Button icon={<Pencil size={14} />} onClick={() => setEditing(true)}>Edit</Button>}
            {can("catalog.delete") && (
              <Button variant="ghost" className="text-red-700" icon={<Trash2 size={14} />} onClick={() => ask({
                title: `Delete ${c.code}?`,
                message: c.paper_count
                  ? `This course has ${c.paper_count} paper(s); the server will refuse. Delete those papers first.`
                  : "The course and its syllabus units are removed permanently.",
                confirmLabel: "Delete course",
                danger: true,
                typeToConfirm: c.code,
              }, async () => {
                try {
                  await adminApi.courses.remove(c.id);
                  toast.success(`Deleted ${c.code}.`);
                  client.invalidateQueries({ queryKey: ["courses"] });
                  router.replace("/courses");
                } catch (e) {
                  toast.error(e, "Could not delete course");
                  throw e;
                }
              })}>Delete</Button>
            )}
          </>
        }
      />
      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Papers" value={formatNumber(c.paper_count)} href={`/papers?course_id=${c.id}`} />
        <StatCard label="Archive papers" value={formatNumber(c.stats.archive_papers)} />
        <StatCard label="Analysed drafts" value={formatNumber(c.stats.analyzed_drafts)} />
        <StatCard label="Average originality" value={<OriginalityValue value={c.stats.avg_originality} />} />
      </div>
      <SyllabusEditor course={c} />
      <p className="mt-3 text-xs text-ink-muted">Keywords are matched against question text to tag each question with a unit. <Link href={`/papers?course_id=${c.id}`} className="text-brand-600 hover:underline">View this course&apos;s papers</Link></p>
      <EditCourseModal course={c} open={editing} onClose={() => setEditing(false)} />
      {dialog}
    </>
  );
}

export default function CourseDetailPage() {
  return <RequirePermission permission="catalog.view"><CourseDetailView /></RequirePermission>;
}
