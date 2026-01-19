"use client";

import { useState, useEffect } from "react";
import { RatingModal } from "./RatingModal";
import ATSReportDisplay from "./ATSReportDisplay";
import { ATSReport } from "../../hooks/useExportStorage";

interface DownloadLink {
  format: string;
  label: string;
  url: string;
}

interface CompletionScreenProps {
  downloads: DownloadLink[];
  onStartNew: () => void;
  atsScore?: number;
  atsReport?: ATSReport | null;
  linkedinOptimized?: boolean;
  threadId?: string;
  jobTitle?: string;
  companyName?: string;
  resumePreviewHtml?: string;
}

/**
 * Final completion screen shown when workflow is fully complete.
 * Shows success message, download links, and "Start New" option.
 */
const RATING_SHOWN_KEY = "resume_agent:rating_shown_";
const COMPLETED_RESUMES_KEY = "resume_agent:completed_resumes";

export default function CompletionScreen({
  downloads,
  onStartNew,
  atsScore,
  atsReport,
  linkedinOptimized,
  threadId,
  jobTitle,
  companyName,
  resumePreviewHtml,
}: CompletionScreenProps) {
  const [showRatingModal, setShowRatingModal] = useState(false);
  const [hasRated, setHasRated] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showATSDetails, setShowATSDetails] = useState(false);
  const [hasReviewed, setHasReviewed] = useState(false);

  // Track completed resumes and check if already rated
  useEffect(() => {
    if (!threadId) return;

    // Check if already rated this thread
    const ratingShown = localStorage.getItem(`${RATING_SHOWN_KEY}${threadId}`);
    if (ratingShown) {
      setHasRated(true);
      return;
    }

    // Increment completed resumes counter
    const currentCount = parseInt(localStorage.getItem(COMPLETED_RESUMES_KEY) || "0", 10);
    localStorage.setItem(COMPLETED_RESUMES_KEY, String(currentCount + 1));

    // DON'T auto-show rating modal - let user review first
  }, [threadId]);

  const handleRatingSubmit = () => {
    setHasRated(true);
    localStorage.setItem(`${RATING_SHOWN_KEY}${threadId}`, "true");
  };

  const handleShowRating = () => {
    setHasReviewed(true);
    setShowRatingModal(true);
  };

  return (
    <>
      <RatingModal
        threadId={threadId || ""}
        jobTitle={jobTitle}
        companyName={companyName}
        isOpen={showRatingModal}
        onClose={() => setShowRatingModal(false)}
        onSubmit={handleRatingSubmit}
      />
    <div className="max-w-2xl mx-auto">
      {/* Success Header */}
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-10 h-10 text-green-600"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Resume Optimization Complete!
        </h1>
        <p className="text-gray-600">
          Your tailored resume is ready for download
        </p>
      </div>

      {/* Stats Summary - Clickable to expand details */}
      {(atsScore !== undefined || linkedinOptimized) && (
        <div className="grid grid-cols-2 gap-4 mb-8">
          {atsScore !== undefined && (
            <button
              onClick={() => setShowATSDetails(!showATSDetails)}
              className="bg-white rounded-lg border p-4 text-center hover:border-blue-300 transition-colors group"
            >
              <div className={`text-3xl font-bold mb-1 ${atsScore >= 70 ? "text-green-600" : "text-amber-600"}`}>
                {atsScore}%
              </div>
              <div className="text-sm text-gray-600">ATS Compatibility</div>
              <div className="text-xs text-blue-500 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                {showATSDetails ? "Click to hide details" : "Click to view details"}
              </div>
            </button>
          )}
          {linkedinOptimized && (
            <div className="bg-white rounded-lg border p-4 text-center">
              <div className="flex items-center justify-center mb-1">
                <svg
                  className="w-8 h-8 text-blue-600"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" />
                </svg>
              </div>
              <div className="text-sm text-gray-600">LinkedIn Ready</div>
            </div>
          )}
        </div>
      )}

      {/* ATS Report Details (Expandable) */}
      {showATSDetails && atsReport && (
        <div className="mb-8 bg-white rounded-lg border overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b flex justify-between items-center">
            <h2 className="font-medium text-gray-900">ATS Analysis Details</h2>
            <button
              onClick={() => setShowATSDetails(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="p-4">
            <ATSReportDisplay report={atsReport} />
          </div>
        </div>
      )}

      {/* Resume Preview Toggle */}
      {resumePreviewHtml && (
        <div className="mb-8">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="w-full px-4 py-3 bg-white border rounded-lg flex items-center justify-between hover:border-blue-300 transition-colors"
          >
            <div className="flex items-center">
              <svg className="w-5 h-5 text-gray-500 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <span className="font-medium text-gray-900">
                {showPreview ? "Hide" : "Preview"} Your Optimized Resume
              </span>
            </div>
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${showPreview ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {showPreview && (
            <div className="mt-4 bg-white border rounded-lg p-6 max-h-[500px] overflow-y-auto">
              <div
                className="prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: resumePreviewHtml }}
              />
            </div>
          )}
        </div>
      )}

      {/* Downloads */}
      <div className="bg-white rounded-lg border overflow-hidden mb-8">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h2 className="font-medium text-gray-900">Download Your Resume</h2>
        </div>
        <div className="divide-y">
          {downloads.map((download) => (
            <a
              key={download.format}
              href={download.url}
              download
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center">
                <FileIcon format={download.format} />
                <span className="ml-3 font-medium text-gray-900">
                  {download.label}
                </span>
              </div>
              <svg
                className="w-5 h-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
            </a>
          ))}
        </div>
      </div>

      {/* Next Steps */}
      <div className="bg-blue-50 rounded-lg p-4 mb-8">
        <h3 className="font-medium text-blue-900 mb-2">Next Steps</h3>
        <ul className="text-sm text-blue-800 space-y-2">
          <li className="flex items-start">
            <span className="mr-2">1.</span>
            Download your resume in PDF format for online applications
          </li>
          <li className="flex items-start">
            <span className="mr-2">2.</span>
            Use the DOCX version if you need to make additional edits
          </li>
          <li className="flex items-start">
            <span className="mr-2">3.</span>
            Update your LinkedIn profile with the suggested improvements
          </li>
          <li className="flex items-start">
            <span className="mr-2">4.</span>
            Review the ATS report for any final optimizations
          </li>
        </ul>
      </div>

      {/* Rate Your Experience (shown before downloads if not rated) */}
      {!hasRated && threadId && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-6 mb-8 text-center">
          <h3 className="font-semibold text-purple-900 mb-2">
            How did we do?
          </h3>
          <p className="text-sm text-purple-700 mb-4">
            Your feedback helps us improve the resume optimization for everyone.
          </p>
          <button
            onClick={handleShowRating}
            className="px-6 py-2 bg-purple-600 text-white font-medium rounded-lg hover:bg-purple-700 transition-colors"
          >
            Rate This Resume
          </button>
        </div>
      )}

      {/* Start New */}
      <div className="text-center">
        <p className="text-gray-600 mb-4">
          Ready to optimize for another job?
        </p>
        <button
          onClick={onStartNew}
          className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          Start New Application
        </button>
      </div>
    </div>
    </>
  );
}

/**
 * File type icon component.
 */
function FileIcon({ format }: { format: string }) {
  const colors: Record<string, string> = {
    pdf: "text-red-500 bg-red-50",
    docx: "text-blue-500 bg-blue-50",
    txt: "text-gray-500 bg-gray-100",
    json: "text-green-500 bg-green-50",
  };

  const colorClass = colors[format.toLowerCase()] || colors.txt;

  return (
    <div
      className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorClass}`}
    >
      <span className="text-xs font-bold uppercase">{format}</span>
    </div>
  );
}
