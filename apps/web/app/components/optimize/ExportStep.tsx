"use client";

import { useState, useEffect, useCallback } from "react";
import {
  useExportStorage,
  ExportStep as ExportStepType,
} from "../../hooks/useExportStorage";
import ATSReportDisplay from "./ATSReportDisplay";
import LinkedInSuggestionsDisplay from "./LinkedInSuggestionsDisplay";


interface ExportStepProps {
  threadId: string;
  draftApproved: boolean;
  onComplete?: () => void;
  onGoBackToDrafting?: () => void;
}

const EXPORT_STEPS: { step: ExportStepType; label: string }[] = [
  { step: "optimizing", label: "Optimizing for ATS" },
  { step: "generating_pdf", label: "Generating PDF" },
  { step: "generating_txt", label: "Generating TXT" },
  { step: "generating_json", label: "Generating JSON" },
  { step: "analyzing_ats", label: "Analyzing ATS Compatibility" },
  { step: "generating_linkedin", label: "Generating LinkedIn Suggestions" },
];

/**
 * Export step component.
 *
 * Features:
 * - Progress tracking for export steps
 * - ATS report display
 * - LinkedIn suggestions display
 * - Download buttons for PDF, TXT, JSON
 * - Copy to clipboard
 * - Session recovery
 */
export default function ExportStep({
  threadId,
  draftApproved,
  onComplete,
  onGoBackToDrafting,
}: ExportStepProps) {
  const storage = useExportStorage();
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"ats" | "linkedin">("ats");
  const [copySuccess, setCopySuccess] = useState(false);
  const [showRecoveryPrompt, setShowRecoveryPrompt] = useState(false);

  // Initialize/check for existing session
  useEffect(() => {
    if (threadId && !storage.session) {
      const existing = storage.checkExistingSession(threadId);
      if (existing && existing.exportCompleted) {
        setShowRecoveryPrompt(true);
      } else if (!existing) {
        storage.startSession(threadId);
      }
    }
  }, [threadId, storage]);

  // Start export workflow
  const startExport = useCallback(async () => {
    if (!draftApproved) {
      setError("Draft must be approved before export");
      return;
    }

    setIsExporting(true);
    setError(null);

    try {
      // Update progress steps
      storage.updateStep("optimizing");

      const response = await fetch(
        `/api/optimize/${threadId}/export/start`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Export failed");
      }

      const data = await response.json();

      // Save results
      if (data.ats_report) {
        storage.saveATSReport(data.ats_report);
      }
      if (data.linkedin_suggestions) {
        storage.saveLinkedInSuggestions(data.linkedin_suggestions);
      }

      storage.completeExport();
      onComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setIsExporting(false);
    }
  }, [threadId, draftApproved, storage, onComplete]);

  // Download file
  const downloadFile = useCallback(
    async (format: "pdf" | "txt" | "json" | "docx") => {
      try {
        const response = await fetch(
          `/api/optimize/${threadId}/export/download/${format}`
        );

        if (!response.ok) {
          throw new Error("Download failed");
        }

        // Get filename from Content-Disposition header
        const contentDisposition = response.headers.get("Content-Disposition");
        const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
        const filename = filenameMatch?.[1] || `resume.${format}`;

        // Create download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        setError("Download failed");
      }
    },
    [threadId]
  );

  // Copy to clipboard
  const copyToClipboard = useCallback(async () => {
    try {
      const response = await fetch(
        `/api/optimize/${threadId}/export/copy-text`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        throw new Error("Failed to get text");
      }

      const data = await response.json();
      await navigator.clipboard.writeText(data.text);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      setError("Copy failed");
    }
  }, [threadId]);

  // Re-export
  const reExport = useCallback(async () => {
    storage.clearSession(threadId);
    storage.startSession(threadId);
    await startExport();
  }, [threadId, storage, startExport]);

  // Handle session recovery
  const handleResumeSession = () => {
    if (storage.existingSession) {
      storage.resumeSession(storage.existingSession);
    }
    setShowRecoveryPrompt(false);
  };

  const handleStartFresh = () => {
    storage.clearSession(threadId);
    storage.startSession(threadId);
    setShowRecoveryPrompt(false);
  };

  // Show recovery prompt
  if (showRecoveryPrompt && storage.existingSession) {
    return (
      <div className="bg-white rounded-lg shadow p-6 max-w-md mx-auto">
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Previous Export Found
        </h3>
        <p className="text-gray-600 mb-4">
          You have previous export results from{" "}
          {new Date(storage.existingSession.completedAt || storage.existingSession.startedAt).toLocaleString()}.
          Would you like to view them or start fresh?
        </p>
        <div className="flex space-x-3">
          <button
            onClick={handleResumeSession}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            View Previous
          </button>
          <button
            onClick={handleStartFresh}
            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
          >
            Start Fresh
          </button>
        </div>
      </div>
    );
  }

  // Draft not approved
  if (!draftApproved) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
        <svg
          className="w-12 h-12 text-amber-500 mx-auto mb-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <h3 className="text-lg font-medium text-amber-800 mb-2">
          Draft Not Approved
        </h3>
        <p className="text-amber-700">
          Please approve your draft in the Drafting stage before exporting.
        </p>
      </div>
    );
  }

  const exportCompleted = storage.session?.exportCompleted;
  const atsReport = storage.session?.atsReport;
  const linkedinSuggestions = storage.session?.linkedinSuggestions;

  return (
    <div className="space-y-6" data-testid="export-step">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Export & Download
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Generate ATS-optimized files and LinkedIn suggestions
          </p>
        </div>
        <div className="flex items-center space-x-4">
          {onGoBackToDrafting && (
            <button
              onClick={onGoBackToDrafting}
              className="text-sm text-gray-600 hover:text-gray-800 flex items-center"
              data-testid="go-back-to-edit"
            >
              <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 17l-5-5m0 0l5-5m-5 5h12" />
              </svg>
              Edit Resume
            </button>
          )}
          {exportCompleted && (
            <button
              onClick={reExport}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Re-export
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-sm text-red-600 hover:text-red-800 mt-2"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Not exported yet */}
      {!exportCompleted && !isExporting && (
        <div className="bg-white border rounded-lg p-6 text-center">
          <svg
            className="w-16 h-16 text-gray-400 mx-auto mb-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Ready to Export
          </h3>
          <p className="text-gray-600 mb-6">
            Generate ATS-optimized files, analyze keyword compatibility, and get
            LinkedIn suggestions.
          </p>
          <button
            onClick={startExport}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
            data-testid="start-export-button"
          >
            Start Export
          </button>
        </div>
      )}

      {/* Exporting in progress */}
      {isExporting && (
        <div className="bg-white border rounded-lg p-6">
          <div className="flex items-center justify-center mb-4">
            <svg
              className="animate-spin h-8 w-8 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          </div>
          <p className="text-center text-gray-600">Generating export...</p>

          {/* Progress steps */}
          <div className="mt-6 space-y-2">
            {EXPORT_STEPS.map((step, idx) => {
              const currentStep = storage.session?.currentStep || "idle";
              const stepIndex = EXPORT_STEPS.findIndex(
                (s) => s.step === currentStep
              );
              let status: "pending" | "in_progress" | "completed" = "pending";
              if (idx < stepIndex) status = "completed";
              else if (idx === stepIndex) status = "in_progress";

              return (
                <div
                  key={step.step}
                  className="flex items-center space-x-3"
                  data-testid={`progress-${step.step}`}
                >
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center ${
                      status === "completed"
                        ? "bg-green-500"
                        : status === "in_progress"
                        ? "bg-blue-500"
                        : "bg-gray-200"
                    }`}
                  >
                    {status === "completed" ? (
                      <svg
                        className="w-4 h-4 text-white"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    ) : status === "in_progress" ? (
                      <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                    ) : (
                      <div className="w-2 h-2 bg-gray-400 rounded-full" />
                    )}
                  </div>
                  <span
                    className={
                      status === "completed"
                        ? "text-green-700"
                        : status === "in_progress"
                        ? "text-blue-700"
                        : "text-gray-500"
                    }
                  >
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Export completed */}
      {exportCompleted && (
        <>
          {/* Download buttons */}
          <div className="bg-white border rounded-lg p-6">
            <h3 className="font-medium text-gray-900 mb-4">Download Files</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <button
                onClick={() => downloadFile("pdf")}
                className="flex flex-col items-center p-4 border rounded-lg hover:bg-gray-50"
                data-testid="download-pdf"
              >
                <svg
                  className="w-8 h-8 text-red-500 mb-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
                <span className="font-medium">PDF</span>
              </button>

              <button
                onClick={() => downloadFile("docx")}
                className="flex flex-col items-center p-4 border rounded-lg hover:bg-gray-50"
                data-testid="download-docx"
              >
                <svg
                  className="w-8 h-8 text-blue-500 mb-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span className="font-medium">DOCX</span>
              </button>

              <button
                onClick={() => downloadFile("txt")}
                className="flex flex-col items-center p-4 border rounded-lg hover:bg-gray-50"
                data-testid="download-txt"
              >
                <svg
                  className="w-8 h-8 text-gray-500 mb-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span className="font-medium">TXT</span>
              </button>

              <button
                onClick={() => downloadFile("json")}
                className="flex flex-col items-center p-4 border rounded-lg hover:bg-gray-50"
                data-testid="download-json"
              >
                <svg
                  className="w-8 h-8 text-yellow-500 mb-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
                  />
                </svg>
                <span className="font-medium">JSON</span>
              </button>
            </div>

            {/* Copy to clipboard */}
            <div className="mt-4 pt-4 border-t">
              <button
                onClick={copyToClipboard}
                className="w-full py-2 border rounded-lg text-gray-700 hover:bg-gray-50 flex items-center justify-center space-x-2"
                data-testid="copy-clipboard"
              >
                {copySuccess ? (
                  <>
                    <svg
                      className="w-5 h-5 text-green-500"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    <span>Copied to clipboard!</span>
                  </>
                ) : (
                  <>
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                      />
                    </svg>
                    <span>Copy Plain Text to Clipboard</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Tabs for ATS Report and LinkedIn */}
          <div className="bg-white border rounded-lg overflow-hidden">
            <div className="border-b flex">
              <button
                onClick={() => setActiveTab("ats")}
                className={`flex-1 py-3 px-4 text-center font-medium ${
                  activeTab === "ats"
                    ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                data-testid="tab-ats"
              >
                ATS Report
              </button>
              <button
                onClick={() => setActiveTab("linkedin")}
                className={`flex-1 py-3 px-4 text-center font-medium ${
                  activeTab === "linkedin"
                    ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                data-testid="tab-linkedin"
              >
                LinkedIn Suggestions
              </button>
            </div>

            <div className="p-6">
              {activeTab === "ats" && atsReport && (
                <ATSReportDisplay report={atsReport} />
              )}
              {activeTab === "linkedin" && linkedinSuggestions && (
                <LinkedInSuggestionsDisplay suggestions={linkedinSuggestions} />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
