"use client";

import { useState } from "react";
import type { JobPosting, BatchJobRetrievalResult } from "@/app/types/jobPosting";
import { saveJob, getJobByUrl, isCached } from "@/app/utils/storage/jobStorage";
import JobViewer from "./JobViewer";

const SUPPORTED_PLATFORMS = [
  { name: "LinkedIn", domain: "linkedin.com", color: "bg-blue-600" },
  { name: "Indeed", domain: "indeed.com", color: "bg-blue-500" },
  { name: "Glassdoor", domain: "glassdoor.com", color: "bg-green-600" },
  { name: "AngelList", domain: "wellfound.com", color: "bg-black" },
  { name: "Company Sites", domain: "other", color: "bg-gray-600" },
];

export default function JobURLInput() {
  const [url, setUrl] = useState("");
  const [urls, setUrls] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobPosting, setJobPosting] = useState<JobPosting | null>(null);
  const [batchMode, setBatchMode] = useState(false);
  const [batchResults, setBatchResults] = useState<BatchJobRetrievalResult | null>(null);
  const [recentUrls, setRecentUrls] = useState<string[]>([]);

  const detectPlatform = (url: string): string => {
    try {
      const urlObj = new URL(url);
      const platform = SUPPORTED_PLATFORMS.find(p =>
        p.domain !== "other" && urlObj.hostname.includes(p.domain)
      );
      return platform?.name || "Other";
    } catch {
      return "Unknown";
    }
  };

  const validateURL = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  const handleAddURL = () => {
    if (!url.trim()) return;

    if (!validateURL(url)) {
      setError("Please enter a valid URL");
      return;
    }

    if (batchMode) {
      if (!urls.includes(url)) {
        setUrls([...urls, url]);
      }
      setUrl("");
    } else {
      setUrls([url]);
    }

    setError(null);
  };

  const handleRemoveURL = (index: number) => {
    setUrls(urls.filter((_, i) => i !== index));
  };

  const handleFetch = async () => {
    if (urls.length === 0) {
      setError("Please add at least one URL");
      return;
    }

    setLoading(true);
    setError(null);
    setBatchResults(null);
    setJobPosting(null);

    try {
      if (batchMode) {
        // Batch processing
        const results = await fetchBatchJobs(urls);
        setBatchResults(results);
      } else {
        // Single URL
        const job = await fetchJob(urls[0]);
        setJobPosting(job);

        // Add to recent URLs
        const recent = [urls[0], ...recentUrls.filter(u => u !== urls[0])].slice(0, 5);
        setRecentUrls(recent);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch job posting");
    } finally {
      setLoading(false);
    }
  };

  const fetchJob = async (url: string): Promise<JobPosting> => {
    // Check cache first
    const cached = await isCached(url);
    if (cached) {
      const job = await getJobByUrl(url);
      if (job) return job;
    }

    // Fetch from backend
    const response = await fetch("/api/jobs/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.error || "Failed to fetch job posting");
    }

    // Save to storage
    await saveJob(result.data);

    return result.data;
  };

  const fetchBatchJobs = async (urls: string[]): Promise<BatchJobRetrievalResult> => {
    const response = await fetch("/api/jobs/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    const result = await response.json();

    // Save successful results to storage
    for (const jobResult of result.results) {
      if (jobResult.success && jobResult.data) {
        await saveJob(jobResult.data);
      }
    }

    return result;
  };

  const handleReset = () => {
    setUrl("");
    setUrls([]);
    setJobPosting(null);
    setBatchResults(null);
    setError(null);
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-bold mb-6">Job Posting Retriever</h2>

          {/* Supported Platforms */}
          <div className="mb-6">
            <p className="text-sm text-gray-600 mb-2">Supported Platforms:</p>
            <div className="flex flex-wrap gap-2">
              {SUPPORTED_PLATFORMS.map((platform) => (
                <span
                  key={platform.name}
                  className={`px-3 py-1 ${platform.color} text-white text-xs rounded-full`}
                >
                  {platform.name}
                </span>
              ))}
            </div>
          </div>

          {/* Mode Toggle */}
          <div className="mb-4 flex gap-2">
            <button
              onClick={() => { setBatchMode(false); setUrls([]); }}
              className={`px-4 py-2 rounded ${
                !batchMode
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Single URL
            </button>
            <button
              onClick={() => { setBatchMode(true); setUrls([]); }}
              className={`px-4 py-2 rounded ${
                batchMode
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Batch Processing
            </button>
          </div>

          {/* URL Input */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {batchMode ? "Add URLs (one at a time)" : "Job Posting URL"}
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleAddURL()}
                disabled={loading}
                placeholder="https://www.linkedin.com/jobs/view/..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
              />
              {batchMode && (
                <button
                  onClick={handleAddURL}
                  disabled={loading}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg disabled:opacity-50"
                >
                  Add
                </button>
              )}
            </div>
            {!batchMode && url && validateURL(url) && (
              <p className="mt-1 text-sm text-gray-600">
                Platform: <span className="font-medium">{detectPlatform(url)}</span>
              </p>
            )}
          </div>

          {/* URL List (for batch mode) */}
          {batchMode && urls.length > 0 && (
            <div className="mb-4">
              <p className="text-sm font-medium text-gray-700 mb-2">
                URLs to process ({urls.length}):
              </p>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {urls.map((u, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-2 bg-gray-50 rounded"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate">{u}</p>
                      <p className="text-xs text-gray-500">{detectPlatform(u)}</p>
                    </div>
                    <button
                      onClick={() => handleRemoveURL(index)}
                      disabled={loading}
                      className="ml-2 text-red-600 hover:text-red-800"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 mb-6">
            <button
              onClick={handleFetch}
              disabled={loading || (batchMode ? urls.length === 0 : !url)}
              className="flex-1 bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {loading ? "Fetching..." : batchMode ? `Fetch ${urls.length} Jobs` : "Fetch Job"}
            </button>
            {(jobPosting || batchResults) && (
              <button
                onClick={handleReset}
                className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
              >
                Reset
              </button>
            )}
          </div>

          {/* Recent URLs */}
          {!batchMode && recentUrls.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Recent URLs:</p>
              <div className="space-y-1">
                {recentUrls.map((recentUrl, index) => (
                  <button
                    key={index}
                    onClick={() => setUrl(recentUrl)}
                    className="block w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded truncate"
                  >
                    {recentUrl}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Help Text */}
          <div className="mt-6 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-blue-800">
              <strong>How it works:</strong> Enter a job posting URL from supported platforms.
              We'll extract and structure the job data including title, company, requirements,
              salary, and more. Use batch mode to process multiple URLs at once.
            </p>
          </div>
        </div>

        {/* Results Section */}
        <div>
          {jobPosting ? (
            <JobViewer job={jobPosting} />
          ) : batchResults ? (
            <BatchResultsView results={batchResults} />
          ) : (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-xl font-bold mb-4">Job Details</h3>
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
                    d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
                <p>Enter a job URL to see details here</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function BatchResultsView({ results }: { results: BatchJobRetrievalResult }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-xl font-bold mb-4">Batch Results</h3>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center p-4 bg-gray-50 rounded">
          <p className="text-2xl font-bold">{results.summary.total}</p>
          <p className="text-sm text-gray-600">Total</p>
        </div>
        <div className="text-center p-4 bg-green-50 rounded">
          <p className="text-2xl font-bold text-green-600">{results.summary.successful}</p>
          <p className="text-sm text-gray-600">Successful</p>
        </div>
        <div className="text-center p-4 bg-red-50 rounded">
          <p className="text-2xl font-bold text-red-600">{results.summary.failed}</p>
          <p className="text-sm text-gray-600">Failed</p>
        </div>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {results.results.map((result, index) => (
          <div
            key={index}
            className={`p-3 rounded border ${
              result.success
                ? "bg-green-50 border-green-200"
                : "bg-red-50 border-red-200"
            }`}
          >
            {result.success && result.data ? (
              <div>
                <p className="font-medium">{result.data.title}</p>
                <p className="text-sm text-gray-600">{result.data.company.name}</p>
              </div>
            ) : (
              <p className="text-sm text-red-600">{result.error}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
