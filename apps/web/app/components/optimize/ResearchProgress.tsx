"use client";

import { ResearchStep, getStepLabel } from "../../hooks/useResearchStorage";

interface ResearchProgressProps {
  /**
   * List of completed research steps.
   */
  completedSteps: ResearchStep[];

  /**
   * Currently executing step (shown with spinner).
   */
  currentStep: ResearchStep | null;

  /**
   * Error message if current step failed.
   */
  error: string | null;

  /**
   * Overall progress percentage (0-100).
   */
  progressPercent: number;
}

const STEP_ORDER: ResearchStep[] = [
  "profile_fetch",
  "job_fetch",
  "company_research",
  "similar_hires",
  "ex_employees",
  "hiring_criteria",
  "ideal_profile",
];

/**
 * Component showing research progress with 7 sub-tasks.
 *
 * Displays:
 * - Each step with status icon (pending/in-progress/completed/error)
 * - Progress bar showing overall completion
 * - Current step highlighted with spinner
 */
export default function ResearchProgress({
  completedSteps,
  currentStep,
  error,
  progressPercent,
}: ResearchProgressProps) {
  const getStepStatus = (step: ResearchStep): "pending" | "in_progress" | "completed" | "error" => {
    if (completedSteps.includes(step)) return "completed";
    if (step === currentStep && error) return "error";
    if (step === currentStep) return "in_progress";
    return "pending";
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Research Progress</h3>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-sm text-gray-600 mb-1">
          <span>Overall Progress</span>
          <span>{progressPercent}%</span>
        </div>
        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-500 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Step list */}
      <div className="space-y-3">
        {STEP_ORDER.map((step, index) => {
          const status = getStepStatus(step);

          return (
            <div
              key={step}
              className={`flex items-center space-x-3 p-2 rounded-lg transition-colors ${
                status === "in_progress" ? "bg-blue-50" : ""
              } ${status === "error" ? "bg-red-50" : ""}`}
            >
              {/* Step number / status icon */}
              <div className="flex-shrink-0">
                <StepIcon status={status} number={index + 1} />
              </div>

              {/* Step label */}
              <div className="flex-1">
                <span
                  className={`text-sm font-medium ${
                    status === "completed"
                      ? "text-green-700"
                      : status === "in_progress"
                      ? "text-blue-700"
                      : status === "error"
                      ? "text-red-700"
                      : "text-gray-500"
                  }`}
                >
                  {getStepLabel(step)}
                </span>

                {/* Show error message if this step failed */}
                {status === "error" && error && (
                  <p className="text-xs text-red-600 mt-0.5">{error}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Step status icon component.
 */
function StepIcon({
  status,
  number,
}: {
  status: "pending" | "in_progress" | "completed" | "error";
  number: number;
}) {
  switch (status) {
    case "completed":
      return (
        <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center">
          <svg
            className="w-4 h-4 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2.5}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
      );

    case "in_progress":
      return (
        <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center">
          <svg
            className="animate-spin w-4 h-4 text-white"
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
      );

    case "error":
      return (
        <div className="w-6 h-6 rounded-full bg-red-500 flex items-center justify-center">
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
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>
      );

    default:
      return (
        <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center">
          <span className="text-xs font-medium text-gray-500">{number}</span>
        </div>
      );
  }
}
