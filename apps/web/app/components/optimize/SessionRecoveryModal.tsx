"use client";

import { WorkflowSession, getStageLabel } from "../../hooks/useWorkflowSession";

interface SessionRecoveryModalProps {
  session: WorkflowSession;
  onResume: () => void;
  onStartFresh: () => void;
}

/**
 * Modal shown when user returns with an existing session.
 * Prompts: Resume where you left off, or Start fresh.
 */
export default function SessionRecoveryModal({
  session,
  onResume,
  onStartFresh,
}: SessionRecoveryModalProps) {
  // Calculate progress
  let completedStages = 0;
  if (session.researchComplete) completedStages++;
  if (session.discoveryConfirmed) completedStages++;
  if (session.draftApproved) completedStages++;
  if (session.exportComplete) completedStages++;

  const progressPercentage = Math.round((completedStages / 4) * 100);

  // Format last activity time
  const lastActivity = new Date(session.updatedAt);
  const timeAgo = formatTimeAgo(lastActivity);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-blue-50 px-6 py-4 border-b border-blue-100">
          <h2 className="text-lg font-semibold text-blue-900">
            Welcome Back!
          </h2>
          <p className="text-sm text-blue-700 mt-1">
            We found an existing session from {timeAgo}
          </p>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {/* Progress summary */}
          <div className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">Progress</span>
              <span className="font-medium text-gray-900">{progressPercentage}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>

          {/* Current position */}
          <div className="bg-gray-50 rounded-lg p-3 mb-4">
            <div className="text-sm text-gray-600 mb-2">Current Stage</div>
            <div className="flex items-center">
              <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                {['research', 'discovery', 'drafting', 'export'].indexOf(session.currentStage) + 1}
              </div>
              <div className="ml-3">
                <div className="font-medium text-gray-900">
                  {getStageLabel(session.currentStage)}
                </div>
                <div className="text-xs text-gray-500">
                  {getStageDescription(session.currentStage)}
                </div>
              </div>
            </div>
          </div>

          {/* Stage breakdown */}
          <div className="space-y-2 mb-4">
            {(['research', 'discovery', 'drafting', 'export'] as const).map((stage) => {
              const status = session.stages[stage];
              const isComplete = status === 'completed';
              const isCurrent = stage === session.currentStage;
              const isLocked = status === 'locked';

              return (
                <div key={stage} className="flex items-center text-sm">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center mr-2 ${
                    isComplete ? 'bg-green-500 text-white' :
                    isCurrent ? 'bg-blue-500 text-white' :
                    isLocked ? 'bg-gray-200 text-gray-400' :
                    'bg-gray-200 text-gray-400'
                  }`}>
                    {isComplete ? (
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    ) : null}
                  </div>
                  <span className={isComplete ? 'text-green-700' : isCurrent ? 'text-blue-700 font-medium' : 'text-gray-400'}>
                    {getStageLabel(stage)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Error state if applicable */}
          {session.lastError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-red-500 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div>
                  <div className="text-sm font-medium text-red-800">
                    Previous session had an error
                  </div>
                  <div className="text-xs text-red-600 mt-1">
                    {session.lastError}
                  </div>
                </div>
              </div>
            </div>
          )}
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
            onClick={onResume}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Resume Session
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Get stage description for display.
 */
function getStageDescription(stage: string): string {
  const descriptions: Record<string, string> = {
    research: 'Analyzing profile and job requirements',
    discovery: 'Finding hidden experiences',
    drafting: 'Creating tailored resume',
    export: 'Generating final documents',
  };
  return descriptions[stage] || '';
}

/**
 * Format time ago string.
 */
function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays === 1) return 'yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;

  return date.toLocaleDateString();
}
