"use client";

import { WorkflowStage, getStageLabel } from "../../hooks/useWorkflowSession";

interface ErrorRecoveryProps {
  error: string;
  errorStage: WorkflowStage | null;
  completedStages: WorkflowStage[];
  onRetry: () => void;
  onStartFresh: () => void;
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
}: ErrorRecoveryProps) {
  const hasCompletedStages = completedStages.length > 0;

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

        {/* Recovery options */}
        <div className="space-y-3">
          <div className="flex items-start p-3 bg-blue-50 rounded-lg">
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
          </div>

          <div className="flex items-start p-3 bg-gray-50 rounded-lg">
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
          </div>
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
