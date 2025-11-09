"use client";

import { useState, useCallback, DragEvent } from "react";
import { parseResumeFile } from "@/app/utils/parsers/resumeParser";
import { saveResume } from "@/app/utils/storage/resumeStorage";
import type { ParsedResume } from "@/app/types/resume";
import ResumeViewer from "./ResumeViewer";

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ALLOWED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

export default function ResumeUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [parsedResume, setParsedResume] = useState<ParsedResume | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      return "Only PDF and DOCX files are allowed";
    }
    if (file.size > MAX_FILE_SIZE) {
      return "File size must be less than 5MB";
    }
    if (file.size === 0) {
      return "File is empty";
    }
    return null;
  };

  const handleDragEnter = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  }, []);

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);

    const droppedFile = e.dataTransfer.files?.[0];
    if (!droppedFile) return;

    const validationError = validateFile(droppedFile);
    if (validationError) {
      setError(validationError);
      setFile(null);
      return;
    }

    setFile(droppedFile);
    setError(null);
    setParsedResume(null);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    const validationError = validateFile(selectedFile);
    if (validationError) {
      setError(validationError);
      setFile(null);
      return;
    }

    setFile(selectedFile);
    setError(null);
    setParsedResume(null);
  };

  const handleParse = async () => {
    if (!file) {
      setError("Please select a file");
      return;
    }

    setParsing(true);
    setProgress(0);
    setError(null);
    setWarnings([]);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress((prev) => Math.min(prev + 15, 90));
      }, 200);

      // Parse the resume
      const resume = await parseResumeFile(file);

      clearInterval(progressInterval);
      setProgress(95);

      // Save to storage
      await saveResume(resume);

      setProgress(100);
      setParsedResume(resume);

      // Check confidence and add warnings
      if (resume.metadata.confidence && resume.metadata.confidence < 0.5) {
        setWarnings([
          "Low parsing confidence. Please review and edit the results.",
        ]);
      }

      // Reset progress after a delay
      setTimeout(() => {
        setProgress(0);
        setParsing(false);
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parsing failed");
      setParsing(false);
      setProgress(0);
    }
  };

  const handleReset = () => {
    setFile(null);
    setParsedResume(null);
    setError(null);
    setWarnings([]);
    setProgress(0);
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-bold mb-6">Upload Resume</h2>

          {/* Drag and Drop Zone */}
          <div
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragging
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400"
            } ${parsing ? "opacity-50 pointer-events-none" : ""}`}
          >
            <div className="space-y-4">
              <div className="flex justify-center">
                <svg
                  className="w-16 h-16 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </div>
              <div>
                <p className="text-lg font-medium text-gray-700">
                  {dragging ? "Drop file here" : "Drag and drop your resume"}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  or click to browse
                </p>
              </div>
              <input
                type="file"
                accept=".pdf,.docx"
                onChange={handleFileSelect}
                disabled={parsing}
                className="hidden"
                id="file-input"
              />
              <label
                htmlFor="file-input"
                className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
              >
                Browse Files
              </label>
              <p className="text-xs text-gray-500">
                PDF or DOCX • Max 5MB
              </p>
            </div>
          </div>

          {/* Selected File */}
          {file && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">{file.name}</p>
                  <p className="text-sm text-gray-600">
                    {(file.size / 1024 / 1024).toFixed(2)} MB •{" "}
                    {file.type.includes("pdf") ? "PDF" : "DOCX"}
                  </p>
                </div>
                {!parsing && !parsedResume && (
                  <button
                    onClick={() => setFile(null)}
                    className="text-red-600 hover:text-red-800"
                  >
                    Remove
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Progress Bar */}
          {parsing && (
            <div className="mt-4 space-y-2">
              <div className="flex justify-between text-sm text-gray-600">
                <span>Parsing resume...</span>
                <span>{progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              {warnings.map((warning, index) => (
                <p key={index} className="text-sm text-yellow-800">
                  ⚠️ {warning}
                </p>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="mt-6 flex gap-3">
            <button
              onClick={handleParse}
              disabled={!file || parsing || !!parsedResume}
              className="flex-1 bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {parsing ? "Parsing..." : parsedResume ? "Parsed ✓" : "Parse Resume"}
            </button>
            {parsedResume && (
              <button
                onClick={handleReset}
                className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
              >
                Upload Another
              </button>
            )}
          </div>

          {/* Help Text */}
          <div className="mt-6 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>How it works:</strong> Upload your resume in PDF or DOCX
              format. Our parser will extract structured data including work
              experience, education, skills, and more. You can review and edit
              the results before saving.
            </p>
          </div>
        </div>

        {/* Results Section */}
        <div>
          {parsedResume ? (
            <ResumeViewer resume={parsedResume} />
          ) : (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-xl font-bold mb-4">Parsed Results</h3>
              <div className="text-center py-12 text-gray-500">
                <svg
                  className="w-16 h-16 mx-auto mb-4 text-gray-300"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <p>Upload and parse a resume to see results here</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
