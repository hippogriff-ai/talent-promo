"use client";

import { ResearchSession, getStepLabel } from "../../hooks/useResearchStorage";

interface SessionRecoveryPromptProps {
  /**
   * The existing session that was found.
   */
  session: ResearchSession;

  /**
   * Called when user chooses to resume the session.
   */
  onResume: () => void;

  /**
   * Called when user chooses to start fresh.
   */
  onStartFresh: () => void;
}

/**
 * Prompt shown when user returns with an incomplete session.
 *
 * Allows user to either:
 * - Resume from where they left off
 * - Start fresh (clears previous progress)
 */
export default function SessionRecoveryPrompt({
  session,
  onResume,
  onStartFresh,
}: SessionRecoveryPromptProps) {
  const completedCount = session.completedSteps.length;
  const totalSteps = 7;
  const progressPercent = Math.round((completedCount / totalSteps) * 100);

  // Determine next step to resume from
  const nextStep = session.currentStep;
  const nextStepLabel = nextStep ? getStepLabel(nextStep) : "Unknown step";

  // Format when session was last updated
  const lastUpdated = new Date(session.updatedAt);
  const timeAgo = formatTimeAgo(lastUpdated);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        {/* Header */}
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
            <svg
              className="w-5 h-5 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Resume Previous Session?
            </h2>
            <p className="text-sm text-gray-500">
              You have an incomplete optimization session
            </p>
          </div>
        </div>

        {/* Session info */}
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          {/* Progress */}
          <div className="mb-3">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">Progress</span>
              <span className="font-medium text-gray-900">
                {completedCount}/{totalSteps} steps ({progressPercent}%)
              </span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Next step */}
          <div className="text-sm">
            <span className="text-gray-600">Resume from: </span>
            <span className="font-medium text-blue-700">{nextStepLabel}</span>
          </div>

          {/* Last updated */}
          <div className="text-sm mt-1">
            <span className="text-gray-600">Last active: </span>
            <span className="text-gray-900">{timeAgo}</span>
          </div>

          {/* Session details */}
          {session.lastError && (
            <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-sm">
              <span className="text-amber-700">
                Previous attempt encountered an error: {session.lastError}
              </span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col space-y-3">
          <button
            onClick={onResume}
            className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center justify-center space-x-2"
          >
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
                d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>Resume from Step {completedCount + 1}</span>
          </button>

          <button
            onClick={onStartFresh}
            className="w-full px-4 py-3 bg-white border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            Start Fresh
          </button>
        </div>

        {/* Note */}
        <p className="text-xs text-gray-500 text-center mt-4">
          Starting fresh will clear your previous progress
        </p>
      </div>
    </div>
  );
}

/**
 * Format a date as relative time (e.g., "5 minutes ago").
 */
function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) {
    return "Just now";
  } else if (diffMins < 60) {
    return `${diffMins} minute${diffMins === 1 ? "" : "s"} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
  } else {
    return date.toLocaleDateString();
  }
}
