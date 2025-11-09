"use client";

import { useState } from "react";
import type { JobPosting } from "@/app/types/jobPosting";
import DOMPurify from "dompurify";

interface JobViewerProps {
  job: JobPosting;
}

export default function JobViewer({ job }: JobViewerProps) {
  const [viewMode, setViewMode] = useState<"structured" | "json">("structured");
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(job, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const sanitize = (text: string) => {
    return DOMPurify.sanitize(text, { ALLOWED_TAGS: [] });
  };

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold">Job Details</h3>
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode("structured")}
              className={`px-3 py-1 rounded ${
                viewMode === "structured"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Structured
            </button>
            <button
              onClick={() => setViewMode("json")}
              className={`px-3 py-1 rounded ${
                viewMode === "json"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              JSON
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
            {job.platform}
          </span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm"
          >
            {copied ? "Copied!" : "Copy JSON"}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 max-h-[600px] overflow-y-auto">
        {viewMode === "structured" ? (
          <div className="space-y-6">
            {/* Title and Company */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                {sanitize(job.title)}
              </h2>
              <div className="flex flex-wrap items-center gap-4 text-gray-600">
                <p className="text-lg font-medium">{sanitize(job.company.name)}</p>
                {job.location.specificLocation && (
                  <p className="flex items-center gap-1">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    {sanitize(job.location.specificLocation)}
                  </p>
                )}
                <span className={`px-2 py-1 rounded text-sm ${
                  job.workLocation === "Remote"
                    ? "bg-green-100 text-green-800"
                    : job.workLocation === "Hybrid"
                    ? "bg-yellow-100 text-yellow-800"
                    : "bg-gray-100 text-gray-800"
                }`}>
                  {job.workLocation}
                </span>
                <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                  {job.jobType}
                </span>
              </div>
            </div>

            {/* Salary */}
            {job.salaryRange && (
              <div className="p-4 bg-green-50 rounded-lg">
                <p className="text-sm font-medium text-green-900 mb-1">Salary Range</p>
                <p className="text-lg font-bold text-green-800">
                  {job.salaryRange.displayText ||
                    `${job.salaryRange.currency} ${job.salaryRange.min?.toLocaleString()} - ${job.salaryRange.max?.toLocaleString()}/${job.salaryRange.period}`}
                </p>
              </div>
            )}

            {/* Description */}
            <div>
              <h3 className="text-lg font-semibold mb-2">Description</h3>
              <div className="text-gray-700 whitespace-pre-wrap">
                {sanitize(job.description)}
              </div>
            </div>

            {/* Responsibilities */}
            {job.responsibilities && job.responsibilities.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold mb-2">Responsibilities</h3>
                <ul className="space-y-2">
                  {job.responsibilities.map((resp, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-blue-500 mr-2">•</span>
                      <span className="text-gray-700">{sanitize(resp)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Requirements */}
            {job.requirements.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold mb-2">Requirements</h3>
                <div className="space-y-2">
                  {job.requirements.filter(r => r.required).length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-1">Required:</p>
                      <ul className="space-y-1">
                        {job.requirements
                          .filter(r => r.required)
                          .map((req, idx) => (
                            <li key={idx} className="flex items-start">
                              <span className="text-red-500 mr-2">★</span>
                              <span className="text-gray-700">{sanitize(req.text)}</span>
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                  {job.requirements.filter(r => !r.required).length > 0 && (
                    <div className="mt-3">
                      <p className="text-sm font-medium text-gray-700 mb-1">Preferred:</p>
                      <ul className="space-y-1">
                        {job.requirements
                          .filter(r => !r.required)
                          .map((req, idx) => (
                            <li key={idx} className="flex items-start">
                              <span className="text-gray-400 mr-2">○</span>
                              <span className="text-gray-600">{sanitize(req.text)}</span>
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Benefits */}
            {job.benefits && job.benefits.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold mb-2">Benefits</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {job.benefits.map((benefit, idx) => (
                    <div key={idx} className="flex items-start p-2 bg-blue-50 rounded">
                      <span className="text-blue-500 mr-2">✓</span>
                      <span className="text-sm text-gray-700">{sanitize(benefit.description)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata */}
            <div className="border-t pt-4 space-y-2 text-sm text-gray-600">
              {job.postedDate && (
                <p>Posted: {new Date(job.postedDate).toLocaleDateString()}</p>
              )}
              {job.experienceLevel && (
                <p>Experience Level: {job.experienceLevel}</p>
              )}
              {job.sourceUrl && (
                <p>
                  Source:{" "}
                  <a
                    href={job.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    View Original
                  </a>
                </p>
              )}
              <p className="text-xs text-gray-500">
                Retrieved: {new Date(job.metadata.retrievedDate).toLocaleString()}
              </p>
            </div>
          </div>
        ) : (
          <pre className="text-xs bg-gray-50 p-4 rounded overflow-x-auto">
            {JSON.stringify(job, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
