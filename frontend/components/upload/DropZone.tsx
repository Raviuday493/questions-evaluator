"use client";

import React, { useRef, useState } from "react";
import { FileUp, FileCheck2 } from "lucide-react";

interface DropZoneProps {
  onFileSelected: (file: File) => void;
  selectedFile: File | null;
  disabled?: boolean;
}

export default function DropZone({ onFileSelected, selectedFile, disabled = false }: DropZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSelect(e.target.files[0]);
    }
    // Allow re-selecting the same file after a reset.
    e.target.value = "";
  };

  const validateAndSelect = (file: File) => {
    const MAX_SIZE = 25 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setError("File size exceeds maximum 25MB limit.");
      return;
    }
    if (file.size === 0) {
      setError("The selected file is empty.");
      return;
    }
    const name = file.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
      setError("Please upload a PDF or DOCX file.");
      return;
    }
    setError(null);
    onFileSelected(file);
  };

  return (
    <section className="qpi-card p-6">
      <h3 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-3">
        <span className="qpi-step">1</span>
        File Selection
      </h3>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,.docx"
        className="hidden"
        disabled={disabled}
      />

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
        aria-disabled={disabled}
        className={`border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center transition-all min-h-[220px] ${
          disabled ? "cursor-not-allowed opacity-70" : "cursor-pointer"
        } ${
          isDragOver
            ? "border-accent bg-blue-50"
            : selectedFile
            ? "border-emerald-300 bg-emerald-50/60"
            : "border-slate-300 hover:border-accent hover:bg-blue-50/50 bg-slate-50/70"
        }`}
      >
        {selectedFile ? (
          <FileCheck2 className="text-emerald-600 mb-4" size={44} strokeWidth={1.6} />
        ) : (
          <FileUp className="text-accent mb-4" size={44} strokeWidth={1.6} />
        )}

        {selectedFile ? (
          <div className="text-center">
            <p className="font-semibold text-slate-900 text-base">{selectedFile.name}</p>
            <p className="text-sm text-slate-500 mt-1">
              {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready for scan
            </p>
            <button
              type="button"
              className="mt-4 text-sm bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-full font-semibold hover:bg-slate-50"
            >
              Change File
            </button>
          </div>
        ) : (
          <div className="text-center">
            <p className="text-lg font-semibold text-slate-900">
              Drag & drop question paper here
            </p>
            <p className="text-sm text-slate-500 mt-1">PDF or DOCX · Max 25MB</p>
            <button
              type="button"
              className="mt-5 bg-accent text-white text-sm font-semibold px-5 py-2.5 rounded-full hover:bg-primary transition-colors shadow-sm"
            >
              Browse Files
            </button>
          </div>
        )}
      </div>
      {error && (
        <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3 py-2" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
