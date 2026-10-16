import type { PaperSummary } from "@/lib/types";
import { STATUS_LABELS } from "@/lib/format";

export function papersCsv(items: PaperSummary[]): string {
  const cell = (value: string | number | null) => {
    const text = String(value ?? "");
    // User-supplied titles and filenames must remain text when opened in a spreadsheet.
    const safe = /^\s*[=+@-]/.test(text) || /^[\t\r\n]/.test(text) ? `'${text}` : text;
    return `"${safe.replace(/"/g, '""')}"`;
  };
  const rows = [
    ["Course", "Title", "File", "Term", "Academic year", "Exam", "Status", "Originality (%)", "Uploaded", "Archive"],
    ...items.map((p) => [p.course_code, p.course_title, p.original_filename, p.term, p.academic_year, p.exam_type, STATUS_LABELS[p.status], p.originality_score, p.created_at, p.is_historical_archive ? "Yes" : "No"]),
  ];
  return "\uFEFF" + rows.map((row) => row.map(cell).join(",")).join("\r\n");
}

export function exportPapersCsv(items: PaperSummary[]) {
  const url = URL.createObjectURL(new Blob([papersCsv(items)], { type: "text/csv;charset=utf-8;" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `qpi-papers-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
