"use client";

import { useMemo } from "react";

/**
 * Agenda topic status type.
 */
export type TopicStatus = "pending" | "in_progress" | "covered" | "skipped";

/**
 * Agenda topic data structure.
 */
export interface AgendaTopic {
  id: string;
  title: string;
  goal: string;
  related_gaps: string[];
  priority: number;
  status: TopicStatus;
  prompts_asked: number;
  max_prompts: number;
  experiences_found: string[];
}

/**
 * Discovery agenda data structure.
 */
export interface DiscoveryAgenda {
  topics: AgendaTopic[];
  current_topic_id: string | null;
  total_topics: number;
  covered_topics: number;
}

interface DiscoveryAgendaProps {
  agenda: DiscoveryAgenda | null;
  className?: string;
}

/**
 * DiscoveryAgenda component displays a structured list of topics
 * being covered in the discovery conversation.
 *
 * Features:
 * - Shows progress bar with completion percentage
 * - Lists all topics with status indicators
 * - Highlights current topic
 * - Shows covered/pending/skipped states
 */
export default function DiscoveryAgenda({
  agenda,
  className = "",
}: DiscoveryAgendaProps) {
  // Calculate progress percentage
  const progress = useMemo(() => {
    if (!agenda || agenda.total_topics === 0) return 0;
    return Math.round((agenda.covered_topics / agenda.total_topics) * 100);
  }, [agenda]);

  if (!agenda || !agenda.topics?.length) {
    return null;
  }

  return (
    <div className={`bg-white rounded-lg shadow p-4 ${className}`}>
      {/* Header with progress */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-gray-900 text-sm">AGENDA</h4>
          <span className="text-xs text-gray-500">
            {agenda.covered_topics}/{agenda.total_topics} complete
          </span>
        </div>
        {/* Progress bar */}
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-purple-600 transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Topics list */}
      <ul className="space-y-2">
        {agenda.topics.map((topic) => {
          const isCurrent = topic.id === agenda.current_topic_id;
          const isCovered = topic.status === "covered";
          const isSkipped = topic.status === "skipped";
          const isPending = topic.status === "pending";

          return (
            <li
              key={topic.id}
              className={`flex items-start space-x-2 py-1.5 px-2 rounded transition-colors ${
                isCurrent
                  ? "bg-purple-50 border border-purple-200"
                  : ""
              }`}
            >
              {/* Status icon */}
              <div className="flex-shrink-0 mt-0.5">
                {isCovered ? (
                  // Checkmark for covered
                  <svg
                    className="w-4 h-4 text-green-500"
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
                ) : isSkipped ? (
                  // Skip icon
                  <svg
                    className="w-4 h-4 text-gray-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 7l5 5m0 0l-5 5m5-5H6"
                    />
                  </svg>
                ) : isCurrent ? (
                  // Arrow for current
                  <svg
                    className="w-4 h-4 text-purple-600"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  // Empty circle for pending
                  <svg
                    className="w-4 h-4 text-gray-300"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <circle
                      cx="12"
                      cy="12"
                      r="9"
                      strokeWidth={2}
                    />
                  </svg>
                )}
              </div>

              {/* Topic title and goal */}
              <div className="flex-1 min-w-0">
                <p
                  className={`text-sm font-medium truncate ${
                    isCovered
                      ? "text-gray-500 line-through"
                      : isSkipped
                      ? "text-gray-400"
                      : isCurrent
                      ? "text-purple-900"
                      : "text-gray-700"
                  }`}
                >
                  {topic.title}
                </p>
                {/* Show goal for current topic */}
                {isCurrent && topic.goal && (
                  <p className="text-xs text-purple-600 mt-0.5 line-clamp-2">
                    {topic.goal}
                  </p>
                )}
                {/* Show experience count for covered topics */}
                {isCovered && topic.experiences_found?.length > 0 && (
                  <p className="text-xs text-green-600 mt-0.5">
                    {topic.experiences_found.length} experience(s) found
                  </p>
                )}
              </div>

              {/* Prompt counter for in-progress topics */}
              {(isCurrent || topic.status === "in_progress") && (
                <span className="flex-shrink-0 text-xs text-purple-500 bg-purple-100 px-1.5 py-0.5 rounded">
                  {topic.prompts_asked}/{topic.max_prompts}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {/* Completion message */}
      {agenda.covered_topics === agenda.total_topics && agenda.total_topics > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs text-green-600 text-center">
            All topics covered! Ready to proceed.
          </p>
        </div>
      )}
    </div>
  );
}
