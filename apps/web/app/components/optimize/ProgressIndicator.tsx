"use client";

import { WorkflowStep } from "../../hooks/useWorkflow";

interface ProgressIndicatorProps {
  currentStep: WorkflowStep;
  progress: Record<string, string>;
}

const steps = [
  { key: "ingest", label: "Profile & Job" },
  { key: "research", label: "Research" },
  { key: "analysis", label: "Analysis" },
  { key: "qa", label: "Q&A" },
  { key: "draft", label: "Draft" },
  { key: "editor", label: "Edit" },
  { key: "completed", label: "Export" },
];

export default function ProgressIndicator({
  currentStep,
  progress,
}: ProgressIndicatorProps) {
  const getStepStatus = (stepKey: string) => {
    if (currentStep === "error") return "error";
    return progress[stepKey] || "pending";
  };

  const getStepClasses = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-500 text-white";
      case "in_progress":
        return "bg-blue-500 text-white animate-pulse";
      case "error":
        return "bg-red-500 text-white";
      default:
        return "bg-gray-200 text-gray-500";
    }
  };

  const getLineClasses = (fromStatus: string, toStatus: string) => {
    if (fromStatus === "completed") return "bg-green-500";
    if (fromStatus === "in_progress") return "bg-blue-500";
    return "bg-gray-200";
  };

  return (
    <div className="flex items-center justify-between">
      {steps.map((step, index) => {
        const status = getStepStatus(step.key);
        const prevStatus = index > 0 ? getStepStatus(steps[index - 1].key) : null;

        return (
          <div key={step.key} className="flex items-center flex-1">
            {/* Connector line */}
            {index > 0 && (
              <div
                className={`h-1 flex-1 ${getLineClasses(
                  prevStatus || "pending",
                  status
                )}`}
              />
            )}

            {/* Step circle */}
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${getStepClasses(
                  status
                )}`}
              >
                {status === "completed" ? (
                  <svg
                    className="w-5 h-5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  index + 1
                )}
              </div>
              <span className="mt-1 text-xs text-gray-600">{step.label}</span>
            </div>

            {/* Final connector */}
            {index < steps.length - 1 && index === steps.length - 2 && (
              <div className={`h-1 flex-1 ${getLineClasses(status, "pending")}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
