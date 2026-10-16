"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch } from "lucide-react";
import DropZone from "@/components/upload/DropZone";
import MetadataForm, { MetadataValues } from "@/components/upload/MetadataForm";
import AnalysisProgress from "@/components/upload/AnalysisProgress";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { api, errorText } from "@/lib/api";
import { academicYearOptions, isInProgress } from "@/lib/format";

const INITIAL_METADATA: MetadataValues = {
  academicYear: academicYearOptions()[0],
  department: "",
  courseCode: "",
  term: "Fall",
  examType: "Final Examination",
  totalMarks: 100,
  isHistoricalArchive: false,
};

function UploadWorkspace() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const revisionOf = params.get("revisionOf");

  const { data: user } = useCurrentUser();
  const departments = useQuery({ queryKey: ["departments"], queryFn: api.departments });
  const previousPaper = useQuery({
    queryKey: ["paper", revisionOf],
    queryFn: () => api.paper(revisionOf!),
    enabled: !!revisionOf,
  });

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<MetadataValues>(INITIAL_METADATA);
  const [paperId, setPaperId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const courses = useQuery({
    queryKey: ["courses", metadata.department],
    queryFn: () => api.courses(metadata.department),
    enabled: !!metadata.department,
  });

  // Default the department to the signed-in user's department.
  useEffect(() => {
    if (user?.department && !metadata.department && !revisionOf) {
      setMetadata((m) => ({ ...m, department: user.department!.code }));
    }
  }, [user, metadata.department, revisionOf]);

  // A revised draft inherits the original paper's course and exam details.
  useEffect(() => {
    const p = previousPaper.data;
    if (!p) return;
    setMetadata((m) => ({
      ...m,
      department: p.department_code ?? m.department,
      courseCode: p.course_code,
      academicYear: p.academic_year,
      term: p.term,
      examType: p.exam_type,
      totalMarks: p.total_marks,
    }));
  }, [previousPaper.data]);

  const upload = useMutation({
    mutationFn: api.uploadPaper,
    onSuccess: (data) => {
      setPaperId(data.paper_id);
      queryClient.invalidateQueries({ queryKey: ["papers"] });
    },
    onError: (err) => setFormError(errorText(err)),
  });

  const status = useQuery({
    queryKey: ["paper-status", paperId],
    queryFn: () => api.paperStatus(paperId!),
    enabled: !!paperId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return !s || isInProgress(s) ? 2000 : false;
    },
  });

  const statusData = status.data;
  const failed = statusData?.status === "FAILED";
  const reportReady = !!statusData?.report_id && !isInProgress(statusData.status) && !failed;
  const isAnalyzing = upload.isPending || (!!paperId && !reportReady && !failed && !status.isError);

  useEffect(() => {
    if (reportReady || failed) {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    }
  }, [reportReady, failed, queryClient]);

  let progressPercent = 0;
  let currentStep = "Awaiting file upload";
  if (upload.isPending) {
    progressPercent = 5;
    currentStep = "Uploading paper document...";
  } else if (statusData) {
    progressPercent = statusData.progress_percent;
    currentStep = statusData.current_step ?? statusData.status;
  } else if (paperId) {
    progressPercent = 5;
    currentStep = "Queued for analysis";
  }

  const pollingError = status.isError ? `Lost track of the analysis: ${errorText(status.error)}` : null;
  const errorMessage = failed ? statusData?.error_message ?? "Analysis failed." : pollingError;

  const handleBeginAnalysis = () => {
    setFormError(null);
    if (!selectedFile) {
      setFormError("Please select a question paper file first.");
      return;
    }
    if (!metadata.department) {
      setFormError("Please select a department.");
      return;
    }
    if (!metadata.courseCode.trim()) {
      setFormError("Please enter the subject / course code.");
      return;
    }
    if (!Number.isInteger(metadata.totalMarks) || metadata.totalMarks < 1 || metadata.totalMarks > 1000) {
      setFormError("Total marks must be a whole number between 1 and 1000.");
      return;
    }
    upload.mutate({
      file: selectedFile,
      courseCode: metadata.courseCode.trim(),
      departmentCode: metadata.department,
      academicYear: metadata.academicYear,
      term: metadata.term,
      examType: metadata.examType,
      totalMarks: metadata.totalMarks,
      previousPaperId: revisionOf,
      isHistoricalArchive: metadata.isHistoricalArchive,
    });
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPaperId(null);
    setFormError(null);
    upload.reset();
  };

  const handleViewReport = () => {
    if (statusData?.report_id) router.push(`/reports/${statusData.report_id}`);
  };

  const canArchive = user?.role === "ARCHIVAL_ADMIN" || user?.role === "SYSTEM_ADMIN";
  const locked = isAnalyzing || reportReady;

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Upload & Analyze Paper
        </h1>
        <p className="text-slate-500 mt-2 max-w-2xl">
          Submit a new question paper draft for archival similarity analysis and quality verification.
        </p>
      </header>

      {revisionOf && (
        <div className="qpi-card p-4 flex items-start gap-3 border-blue-200 bg-blue-50/40">
          <GitBranch className="text-accent shrink-0 mt-0.5" size={18} />
          <div className="text-sm text-slate-700">
            {previousPaper.isLoading && "Loading the original paper..."}
            {previousPaper.isError && (
              <span className="text-red-700">Could not load the original paper: {errorText(previousPaper.error)}</span>
            )}
            {previousPaper.data && (
              <>
                Uploading a <strong>revised draft</strong> of {previousPaper.data.course_code}{" "}
                {previousPaper.data.exam_type} ({previousPaper.data.original_filename}). The new analysis will be linked to
                the original{previousPaper.data.originality_score !== null &&
                  ` (originality ${previousPaper.data.originality_score.toFixed(0)}%)`}.{" "}
                <Link href="/upload" className="text-accent font-semibold hover:underline">Upload a new paper instead</Link>
              </>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 flex flex-col gap-6">
          <DropZone selectedFile={selectedFile} onFileSelected={setSelectedFile} disabled={locked} />
          <MetadataForm
            values={metadata}
            onChange={setMetadata}
            departments={departments.data ?? []}
            departmentsLoading={departments.isLoading}
            courses={courses.data ?? []}
            canArchive={canArchive && !revisionOf}
            disabled={locked}
            lockCourse={!!revisionOf}
          />
          {departments.isError && (
            <p className="text-sm text-red-700" role="alert">Could not load departments: {errorText(departments.error)}</p>
          )}
        </div>

        <div className="lg:col-span-4 flex flex-col">
          <AnalysisProgress
            isAnalyzing={isAnalyzing}
            progressPercent={progressPercent}
            currentStep={currentStep}
            reportReady={reportReady}
            onViewReport={handleViewReport}
            errorMessage={errorMessage}
          />
        </div>
      </div>

      {formError && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3" role="alert">
          {formError}
        </div>
      )}

      <div className="flex justify-end gap-3 border-t border-slate-200 pt-6">
        <button
          type="button"
          onClick={handleReset}
          className="px-5 py-2.5 border border-slate-200 text-slate-600 rounded-full text-sm font-semibold hover:bg-white transition-colors"
        >
          {reportReady || errorMessage ? "Start Over" : "Cancel"}
        </button>
        <button
          type="button"
          onClick={handleBeginAnalysis}
          disabled={!selectedFile || locked}
          className={`px-5 py-2.5 rounded-full text-sm font-semibold transition-all ${
            selectedFile && !locked
              ? "bg-accent text-white hover:bg-primary cursor-pointer shadow-sm"
              : "bg-slate-200 text-slate-400 cursor-not-allowed"
          }`}
        >
          {isAnalyzing ? "Scanning..." : reportReady ? "Analysis Complete" : "Begin Analysis"}
        </button>
      </div>
    </div>
  );
}

export default function UploadPage() {
  return (
    <Suspense>
      <UploadWorkspace />
    </Suspense>
  );
}
