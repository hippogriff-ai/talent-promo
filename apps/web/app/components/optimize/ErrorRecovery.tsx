"use client";

import { WorkflowStage, getStageLabel } from "../../hooks/useWorkflowSession";

interface ErrorRecoveryProps {
  error: string;
  errorStage: WorkflowStage | null;
  completedStages: WorkflowStage[];
  onRetry: () => void;
  onStartFresh: () => void;
  onPasteResume?: () => void;
}

// Check if error is a rate limit error
function isRateLimitError(error: string): boolean {
  return error.toLowerCase().includes("rate limit") ||
         error.toLowerCase().includes("resume juice") ||
         error.toLowerCase().includes("creativity tank");
}

// Check if error is a LinkedIn fetch failure
function isLinkedInFetchError(error: string): boolean {
  return error.includes("LINKEDIN_FETCH_FAILED") ||
         (error.toLowerCase().includes("linkedin") &&
          (error.toLowerCase().includes("failed to fetch") ||
           error.toLowerCase().includes("unable to access")));
}

// Extract the LinkedIn URL from the error message
function extractLinkedInUrl(error: string): string | null {
  const urlMatch = error.match(/URL:\s*(https?:\/\/[^\s]+)/);
  return urlMatch ? urlMatch[1] : null;
}

/**
 * Error recovery component.
 * Shows error details and offers:
 * - Retry: Resume from the failed point
 * - Start Fresh: Reset from error stage, preserve completed stages
 */
export default function ErrorRecovery({
  error,
  errorStage,
  completedStages,
  onRetry,
  onStartFresh,
  onPasteResume,
}: ErrorRecoveryProps) {
  const hasCompletedStages = completedStages.length > 0;
  const isRateLimit = isRateLimitError(error);
  const isLinkedInError = isLinkedInFetchError(error);
  const linkedInUrl = isLinkedInError ? extractLinkedInUrl(error) : null;

  // Special UI for LinkedIn fetch failures
  if (isLinkedInError) {
    return (
      <div className="bg-white rounded-lg shadow-lg border border-blue-200 overflow-hidden max-w-lg mx-auto">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 px-6 py-6 border-b border-blue-100">
          <div className="text-center">
            <span className="text-5xl mb-3 block">🔒</span>
            <h2 className="text-xl font-semibold text-blue-900">
              LinkedIn Access Blocked
            </h2>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          <div className="bg-blue-50 rounded-lg p-4 mb-4 text-center">
            <p className="text-blue-800 text-sm">
              LinkedIn blocks automated access to profiles. This isn&apos;t your fault - it&apos;s a security measure on their end.
            </p>
            {linkedInUrl && (
              <p className="text-xs text-blue-600 mt-2 break-all">
                {linkedInUrl}
              </p>
            )}
          </div>

          {/* Solution */}
          <div className="bg-green-50 rounded-lg p-4 mb-4">
            <h3 className="text-sm font-medium text-green-900 mb-2 flex items-center">
              <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              Easy Fix: Paste Your Resume
            </h3>
            <p className="text-sm text-green-800">
              Copy your resume text (from a PDF, Word doc, or your LinkedIn &quot;About&quot; section) and paste it directly. This works even better than scraping!
            </p>
          </div>

          {/* Quick tips */}
          <div className="text-sm text-gray-600 space-y-2">
            <p className="font-medium">Quick ways to get your resume text:</p>
            <ul className="list-disc list-inside text-xs space-y-1 text-gray-500">
              <li>Open your resume PDF and select all → copy</li>
              <li>Export from LinkedIn: Profile → More → Save to PDF</li>
              <li>Copy from Google Docs or Word</li>
            </ul>
          </div>
        </div>

        {/* Actions */}
        <div className="px-6 py-4 bg-gray-50 border-t space-y-3">
          {onPasteResume && (
            <button
              onClick={onPasteResume}
              className="w-full px-4 py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center"
            >
              <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" />
                <path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z" />
              </svg>
              Paste Resume Instead
            </button>
          )}
          <button
            onClick={onStartFresh}
            className="w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Start Over with Different URL
          </button>
        </div>
      </div>
    );
  }

  // Special UI for rate limiting
  if (isRateLimit) {
    return (
      <div className="bg-white rounded-lg shadow-lg border border-amber-200 overflow-hidden max-w-lg mx-auto">
        {/* Header with coffee theme */}
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 px-6 py-6 border-b border-amber-100">
          <div className="text-center">
            <span className="text-5xl mb-3 block">☕</span>
            <h2 className="text-xl font-semibold text-amber-900">
              Time for a Coffee Break!
            </h2>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          <div className="bg-amber-50 rounded-lg p-4 mb-4 text-center">
            <p className="text-amber-800">{error}</p>
          </div>

          <div className="text-center text-gray-600 space-y-3">
            <p className="text-sm">
              We limit usage to keep the service free and fast for everyone.
            </p>
            <p className="text-sm">
              <strong>Pro tip:</strong> Use this time to polish your LinkedIn profile
              or research the company you&apos;re applying to!
            </p>
          </div>

          {/* Fun suggestions */}
          <div className="mt-6 bg-blue-50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-blue-900 mb-2">While you wait...</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Perfect your elevator pitch</li>
              <li>• Stalk... er, research your interviewer on LinkedIn</li>
              <li>• Practice your &quot;tell me about yourself&quot;</li>
              <li>• Actually get that coffee ☕</li>
            </ul>
          </div>
        </div>

        {/* Actions */}
        <div className="px-6 py-4 bg-gray-50 border-t">
          <button
            onClick={onStartFresh}
            className="w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Got it, I&apos;ll come back later
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-lg border border-red-200 overflow-hidden max-w-lg mx-auto">
      {/* Header */}
      <div className="bg-red-50 px-6 py-4 border-b border-red-100">
        <div className="flex items-center">
          <svg
            className="w-6 h-6 text-red-500 mr-3"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          <h2 className="text-lg font-semibold text-red-900">
            Something went wrong
          </h2>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-4">
        {/* Error message */}
        <div className="bg-red-50 rounded-lg p-4 mb-4">
          <p className="text-sm text-red-800">{error}</p>
          {errorStage && (
            <p className="text-xs text-red-600 mt-2">
              Error occurred during: {getStageLabel(errorStage)}
            </p>
          )}
        </div>

        {/* Preserved progress */}
        {hasCompletedStages && (
          <div className="mb-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              Your progress is preserved
            </h3>
            <div className="flex flex-wrap gap-2">
              {completedStages.map((stage) => (
                <span
                  key={stage}
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800"
                >
                  <svg
                    className="w-3 h-3 mr-1"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                  {getStageLabel(stage)}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Recovery options - clickable cards */}
        <div className="space-y-3">
          <button
            onClick={onRetry}
            className="w-full flex items-start p-3 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors cursor-pointer text-left"
          >
            <svg
              className="w-5 h-5 text-blue-500 mt-0.5 mr-3 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <h4 className="text-sm font-medium text-blue-900">Retry</h4>
              <p className="text-xs text-blue-700 mt-0.5">
                Attempt to resume from where the error occurred
              </p>
            </div>
          </button>

          <button
            onClick={onStartFresh}
            className="w-full flex items-start p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer text-left"
          >
            <svg
              className="w-5 h-5 text-gray-500 mt-0.5 mr-3 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <h4 className="text-sm font-medium text-gray-900">Start Fresh</h4>
              <p className="text-xs text-gray-600 mt-0.5">
                {hasCompletedStages
                  ? `Reset ${errorStage ? getStageLabel(errorStage) : "current stage"} and try again`
                  : "Start the workflow from the beginning"}
              </p>
            </div>
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
        <button
          onClick={onStartFresh}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Start Fresh
        </button>
        <button
          onClick={onRetry}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
