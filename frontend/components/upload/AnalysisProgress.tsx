"use client";

import React from "react";
import { AlertTriangle, BarChart3, CheckCircle2, Eye, Loader2 } from "lucide-react";

interface AnalysisProgressProps {
  isAnalyzing: boolean;
  progressPercent: number;
  currentStep: string;
  onViewReport: () => void;
  reportReady: boolean;
  errorMessage?: string | null;
}

export default function AnalysisProgress({
  isAnalyzing,
  progressPercent,
  currentStep,
  onViewReport,
  reportReady,
  errorMessage = null,
}: AnalysisProgressProps) {
  return (
    <section className="qpi-card p-6 h-full flex flex-col justify-between min-h-[420px]">
      <div>
        <h3 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-3">
          <span className="qpi-step">3</span>
          Analysis Status
        </h3>

        {errorMessage && !isAnalyzing && (
          <div className="flex flex-col items-center justify-center text-center py-12 gap-3" role="alert">
            <div className="w-16 h-16 rounded-2xl bg-red-50 border border-red-100 flex items-center justify-center">
              <AlertTriangle className="text-red-500" size={30} strokeWidth={1.6} />
            </div>
            <p className="text-sm font-semibold text-slate-900">Analysis could not be completed</p>
            <p className="text-sm text-slate-600 max-w-[280px] leading-relaxed">{errorMessage}</p>
          </div>
        )}

        {!isAnalyzing && !reportReady && !errorMessage && (
          <div className="flex flex-col items-center justify-center text-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center mb-4">
              <BarChart3 className="text-slate-400" size={32} strokeWidth={1.6} />
            </div>
            <p className="text-sm text-slate-500 max-w-[220px] leading-relaxed">
              Awaiting paper upload and submission to begin analysis.
            </p>
          </div>
        )}

        {(isAnalyzing || reportReady) && (
          <div className="flex flex-col gap-4 py-4">
            <div className="flex justify-between items-end">
              <span className="text-sm font-medium text-slate-800">{currentStep}</span>
              <span className="text-sm text-accent font-bold">{progressPercent}%</span>
            </div>

            <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent transition-all duration-500 rounded-full"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            <div className="mt-2 p-3 bg-slate-50 rounded-xl border border-slate-100">
              <div className="flex items-center gap-2 text-sm text-slate-700 font-medium">
                {reportReady ? (
                  <CheckCircle2 className="text-emerald-600 shrink-0" size={18} />
                ) : (
                  <Loader2 className="text-accent shrink-0 animate-spin" size={18} />
                )}
                <span>
                  {reportReady
                    ? "Analysis complete. Question matches and originality score calculated."
                    : currentStep}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {reportReady && (
        <button
          onClick={onViewReport}
          className="w-full mt-6 bg-accent text-white font-semibold text-sm py-3 rounded-xl hover:bg-primary transition-colors flex items-center justify-center gap-2"
        >
          <Eye size={16} />
          View Originality & Match Report
        </button>
      )}
    </section>
  );
}
