"use client";

import { WorkflowStage, StageStatus, getStageLabel, getStageDescription } from "../../hooks/useWorkflowSession";

interface WorkflowStepperProps {
  stages: Record<WorkflowStage, StageStatus>;
  currentStage: WorkflowStage;
  onStageClick?: (stage: WorkflowStage) => void;
}

const STAGES: WorkflowStage[] = ["research", "discovery", "drafting", "export"];

/**
 * 4-stage workflow stepper component.
 * Shows: Research → Discovery → Drafting → Export
 *
 * Stage states:
 * - locked: Gray, not clickable, shows lock icon
 * - active: Blue, pulsing, shows current step indicator
 * - completed: Green, checkmark, clickable to revisit
 * - error: Red, shows error icon, clickable for retry
 */
export default function WorkflowStepper({
  stages,
  currentStage,
  onStageClick,
}: WorkflowStepperProps) {
  const getStageClasses = (stage: WorkflowStage, status: StageStatus): string => {
    const isActive = stage === currentStage && status === "active";

    switch (status) {
      case "completed":
        return "bg-green-500 text-white cursor-pointer hover:bg-green-600";
      case "active":
        return isActive
          ? "bg-blue-500 text-white animate-pulse"
          : "bg-blue-500 text-white cursor-pointer hover:bg-blue-600";
      case "error":
        return "bg-red-500 text-white cursor-pointer hover:bg-red-600";
      case "locked":
      default:
        return "bg-gray-200 text-gray-400 cursor-not-allowed";
    }
  };

  const getConnectorClasses = (fromStatus: StageStatus): string => {
    switch (fromStatus) {
      case "completed":
        return "bg-green-500";
      case "active":
        return "bg-blue-300";
      case "error":
        return "bg-red-300";
      default:
        return "bg-gray-200";
    }
  };

  const handleStageClick = (stage: WorkflowStage) => {
    const status = stages[stage];
    if (status !== "locked" && onStageClick) {
      onStageClick(stage);
    }
  };

  const renderStageIcon = (stage: WorkflowStage, status: StageStatus, index: number) => {
    switch (status) {
      case "completed":
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        );
      case "error":
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
        );
      case "locked":
        return (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
              clipRule="evenodd"
            />
          </svg>
        );
      default:
        return <span className="text-sm font-semibold">{index + 1}</span>;
    }
  };

  return (
    <nav aria-label="Workflow progress">
      <ol className="flex items-center justify-between">
        {STAGES.map((stage, index) => {
          const status = stages[stage];
          const isLast = index === STAGES.length - 1;

          return (
            <li key={stage} className="flex items-center flex-1">
              {/* Stage circle */}
              <div className="flex flex-col items-center">
                <button
                  type="button"
                  onClick={() => handleStageClick(stage)}
                  disabled={status === "locked"}
                  className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 ${getStageClasses(stage, status)}`}
                  title={`${getStageLabel(stage)}: ${getStageDescription(stage)}`}
                  aria-label={`${getStageLabel(stage)} - ${status}`}
                  aria-current={stage === currentStage ? "step" : undefined}
                >
                  {renderStageIcon(stage, status, index)}
                </button>
                <span className={`mt-2 text-xs font-medium ${
                  status === "locked" ? "text-gray-400" :
                  status === "error" ? "text-red-600" :
                  stage === currentStage ? "text-blue-600" :
                  "text-gray-700"
                }`}>
                  {getStageLabel(stage)}
                </span>
              </div>

              {/* Connector line */}
              {!isLast && (
                <div className="flex-1 mx-2">
                  <div className={`h-1 rounded-full ${getConnectorClasses(status)}`} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
