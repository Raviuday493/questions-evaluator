"use client";

import React from "react";
import type { Course, Department } from "@/lib/types";
import { academicYearOptions } from "@/lib/format";

export interface MetadataValues {
  academicYear: string;
  department: string; // department code
  courseCode: string;
  term: string;
  examType: string;
  totalMarks: number;
  isHistoricalArchive: boolean;
}

interface MetadataFormProps {
  values: MetadataValues;
  onChange: (values: MetadataValues) => void;
  departments: Department[];
  courses: Course[];
  departmentsLoading?: boolean;
  canArchive?: boolean;
  disabled?: boolean;
  lockCourse?: boolean;
}

export default function MetadataForm({
  values,
  onChange,
  departments,
  courses,
  departmentsLoading = false,
  canArchive = false,
  disabled = false,
  lockCourse = false,
}: MetadataFormProps) {
  const handleChange = (field: keyof MetadataValues, val: string | number | boolean) => {
    onChange({
      ...values,
      [field]: val,
    });
  };
  const years = academicYearOptions();
  if (values.academicYear && !years.includes(values.academicYear)) years.push(values.academicYear);

  return (
    <section className="qpi-card p-6">
      <h3 className="text-base font-semibold text-slate-900 mb-5 flex items-center gap-3">
        <span className="qpi-step">2</span>
        Paper Metadata
      </h3>

      <form className="grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={(e) => e.preventDefault()}>
        <fieldset disabled={disabled} className="contents">
          <div className="flex flex-col gap-1.5">
            <label className="qpi-label" htmlFor="academic-year">
              Academic Year
            </label>
            <select
              id="academic-year"
              value={values.academicYear}
              onChange={(e) => handleChange("academicYear", e.target.value)}
              className="qpi-input"
            >
              {years.map((y) => (
                <option key={y} value={y}>{y.replace("-", " - ")}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="qpi-label" htmlFor="department">
              Department
            </label>
            <select
              id="department"
              value={values.department}
              onChange={(e) => onChange({ ...values, department: e.target.value, courseCode: "" })}
              className="qpi-input"
              disabled={departmentsLoading || lockCourse}
            >
              <option value="">{departmentsLoading ? "Loading departments..." : "Select department"}</option>
              {departments.map((d) => (
                <option key={d.code} value={d.code}>{d.name}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="qpi-label" htmlFor="course-code">
              Subject / Course Code
            </label>
            <input
              id="course-code"
              type="text"
              list="course-options"
              value={values.courseCode}
              onChange={(e) => handleChange("courseCode", e.target.value.toUpperCase())}
              placeholder="e.g. PHY-201"
              className="qpi-input"
              maxLength={31}
              disabled={lockCourse}
              required
            />
            <datalist id="course-options">
              {courses.map((c) => (
                <option key={c.id} value={c.code}>{c.title}</option>
              ))}
            </datalist>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="qpi-label" htmlFor="exam-term">
              Term & Exam Type
            </label>
            <div className="flex gap-2">
              <select
                id="exam-term"
                value={values.term}
                onChange={(e) => handleChange("term", e.target.value)}
                className="qpi-input flex-1"
              >
                <option value="Fall">Fall</option>
                <option value="Spring">Spring</option>
                <option value="Summer">Summer</option>
              </select>
              <select
                aria-label="Exam type"
                value={values.examType}
                onChange={(e) => handleChange("examType", e.target.value)}
                className="qpi-input flex-1"
              >
                <option value="Final Examination">Final Exam</option>
                <option value="Midterm Examination">Midterm</option>
                <option value="Quiz">Quiz</option>
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5 md:col-span-2">
            <label className="qpi-label" htmlFor="total-marks">
              Total Paper Marks
            </label>
            <input
              id="total-marks"
              type="number"
              min={1}
              max={1000}
              value={values.totalMarks}
              onChange={(e) => handleChange("totalMarks", Number(e.target.value))}
              placeholder="100"
              className="qpi-input max-w-xs"
            />
          </div>

          {canArchive && (
            <label className="md:col-span-2 flex items-start gap-3 text-sm text-slate-700 bg-slate-50 border border-slate-100 rounded-xl p-3">
              <input
                type="checkbox"
                checked={values.isHistoricalArchive}
                onChange={(e) => handleChange("isHistoricalArchive", e.target.checked)}
                className="mt-0.5 h-4 w-4 accent-[#2563eb]"
              />
              <span>
                <span className="font-semibold">Add to historical exam archive</span>
                <span className="block text-xs text-slate-500">
                  Archived papers are used as the comparison pool for future drafts of this course.
                </span>
              </span>
            </label>
          )}
        </fieldset>
      </form>
    </section>
  );
}
