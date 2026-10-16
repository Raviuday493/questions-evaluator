"use client";

import { Field, Input, Select } from "@/components/ui/primitives";
import type { Department } from "@/types";

export function currentAcademicYear(): string {
  const now = new Date();
  const start = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  return `${start}-${start + 1}`;
}

export function CourseForm({ value, onChange, departments, errors }: {
  value: { department_id: string; code: string; title: string; academic_year: string };
  onChange: (v: { department_id: string; code: string; title: string; academic_year: string }) => void;
  departments: Department[] | undefined;
  errors: Record<string, string>;
}) {
  return (
    <div className="space-y-3">
      <Field label="Department" htmlFor="c-dept" error={errors.department_id} required>
        <Select id="c-dept" value={value.department_id} onChange={(e) => onChange({ ...value, department_id: e.target.value })}>
          <option value="">Select…</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.name}</option>)}
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Course code" htmlFor="c-code" error={errors.code} hint="e.g. PHY-201" required>
          <Input id="c-code" value={value.code} onChange={(e) => onChange({ ...value, code: e.target.value.toUpperCase() })} maxLength={31} />
        </Field>
        <Field label="Academic year" htmlFor="c-year" error={errors.academic_year} hint="YYYY-YYYY" required>
          <Input id="c-year" value={value.academic_year} onChange={(e) => onChange({ ...value, academic_year: e.target.value })} maxLength={9} />
        </Field>
      </div>
      <Field label="Title" htmlFor="c-title" error={errors.title} required>
        <Input id="c-title" value={value.title} onChange={(e) => onChange({ ...value, title: e.target.value })} maxLength={255} />
      </Field>
    </div>
  );
}

export function validateCourse(v: { department_id: string; code: string; title: string; academic_year: string }): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!v.department_id) errors.department_id = "Choose a department.";
  if (!/^[A-Z0-9][A-Z0-9\- ]{1,30}$/.test(v.code.trim())) errors.code = "2–31 letters, digits, spaces or hyphens.";
  if (v.title.trim().length < 2) errors.title = "Title must be at least 2 characters.";
  const m = /^(\d{4})-(\d{4})$/.exec(v.academic_year.trim());
  if (!m || Number(m[2]) !== Number(m[1]) + 1) errors.academic_year = "Must look like 2025-2026.";
  return errors;
}
