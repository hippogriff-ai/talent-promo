"use client";

import { useState } from "react";
import type { DraftingSuggestion, SuggestionStatus } from "../../hooks/useDraftingStorage";

interface SuggestionCardProps {
  suggestion: DraftingSuggestion;
  onAccept: (id: string) => Promise<void>;
  onDecline: (id: string) => Promise<void>;
  isLoading?: boolean;
}

/**
 * Card displaying a single suggestion with accept/decline actions.
 */
export default function SuggestionCard({
  suggestion,
  onAccept,
  onDecline,
  isLoading = false,
}: SuggestionCardProps) {
  const [localLoading, setLocalLoading] = useState(false);

  const isPending = suggestion.status === "pending";
  const isAccepted = suggestion.status === "accepted";
  const isDeclined = suggestion.status === "declined";

  const handleAccept = async () => {
    setLocalLoading(true);
    try {
      await onAccept(suggestion.id);
    } finally {
      setLocalLoading(false);
    }
  };

  const handleDecline = async () => {
    setLocalLoading(true);
    try {
      await onDecline(suggestion.id);
    } finally {
      setLocalLoading(false);
    }
  };

  const locationLabel = getLocationLabel(suggestion.location);

  return (
    <div
      className={`border rounded-lg p-4 transition-all ${
        isPending
          ? "bg-white border-gray-200"
          : isAccepted
          ? "bg-green-50 border-green-200"
          : "bg-gray-50 border-gray-200"
      }`}
      data-testid={`suggestion-card-${suggestion.id}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
              isPending
                ? "bg-amber-100 text-amber-800"
                : isAccepted
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {locationLabel}
          </span>
          {!isPending && (
            <span
              className={`text-xs ${
                isAccepted ? "text-green-600" : "text-gray-500"
              }`}
            >
              {isAccepted ? "Accepted" : "Declined"}
            </span>
          )}
        </div>
      </div>

      {/* Original Text */}
      <div className="mb-3">
        <p className="text-xs text-gray-500 mb-1">Original:</p>
        <p className="text-sm text-gray-700 bg-gray-50 p-2 rounded border-l-2 border-gray-300">
          {suggestion.originalText}
        </p>
      </div>

      {/* Proposed Text */}
      <div className="mb-3">
        <p className="text-xs text-gray-500 mb-1">Suggested:</p>
        <p
          className={`text-sm p-2 rounded border-l-2 ${
            isAccepted
              ? "bg-green-50 border-green-400 text-green-800"
              : isDeclined
              ? "bg-gray-50 border-gray-300 text-gray-500 line-through"
              : "bg-blue-50 border-blue-400 text-blue-800"
          }`}
        >
          {suggestion.proposedText}
        </p>
      </div>

      {/* Rationale */}
      <div className="mb-4">
        <p className="text-xs text-gray-500 mb-1">Why:</p>
        <p className="text-sm text-gray-600 italic">{suggestion.rationale}</p>
      </div>

      {/* Actions */}
      {isPending && (
        <div className="flex space-x-2">
          <button
            onClick={handleAccept}
            disabled={isLoading || localLoading}
            className="flex-1 px-3 py-2 bg-green-600 text-white text-sm font-medium rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            data-testid="accept-button"
          >
            {localLoading ? "..." : "Accept"}
          </button>
          <button
            onClick={handleDecline}
            disabled={isLoading || localLoading}
            className="flex-1 px-3 py-2 bg-white text-gray-700 text-sm font-medium rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            data-testid="decline-button"
          >
            {localLoading ? "..." : "Decline"}
          </button>
        </div>
      )}

      {/* Resolved timestamp */}
      {!isPending && suggestion.resolvedAt && (
        <p className="text-xs text-gray-400 mt-2">
          {isAccepted ? "Accepted" : "Declined"}{" "}
          {new Date(suggestion.resolvedAt).toLocaleString()}
        </p>
      )}
    </div>
  );
}

/**
 * Get human-readable label for suggestion location.
 */
function getLocationLabel(location: string): string {
  if (location === "summary") return "Summary";
  if (location.startsWith("experience")) {
    const match = location.match(/experience\.(\d+)/);
    if (match) {
      return `Experience ${parseInt(match[1]) + 1}`;
    }
    return "Experience";
  }
  if (location === "skills") return "Skills";
  if (location === "education") return "Education";
  if (location === "certifications") return "Certifications";
  return location.charAt(0).toUpperCase() + location.slice(1);
}

/**
 * List of suggestion cards.
 */
interface SuggestionListProps {
  suggestions: DraftingSuggestion[];
  onAccept: (id: string) => Promise<void>;
  onDecline: (id: string) => Promise<void>;
  isLoading?: boolean;
  showResolved?: boolean;
}

export function SuggestionList({
  suggestions,
  onAccept,
  onDecline,
  isLoading = false,
  showResolved = false,
}: SuggestionListProps) {
  const pendingSuggestions = suggestions.filter((s) => s.status === "pending");
  const resolvedSuggestions = suggestions.filter((s) => s.status !== "pending");

  return (
    <div className="space-y-4" data-testid="suggestion-list">
      {/* Pending suggestions */}
      {pendingSuggestions.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Pending ({pendingSuggestions.length})
          </h4>
          <div className="space-y-3">
            {pendingSuggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                onAccept={onAccept}
                onDecline={onDecline}
                isLoading={isLoading}
              />
            ))}
          </div>
        </div>
      )}

      {/* Resolved suggestions */}
      {showResolved && resolvedSuggestions.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-500 mb-2">
            Resolved ({resolvedSuggestions.length})
          </h4>
          <div className="space-y-3">
            {resolvedSuggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                onAccept={onAccept}
                onDecline={onDecline}
                isLoading={isLoading}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {suggestions.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <p>No suggestions available</p>
        </div>
      )}

      {/* All resolved */}
      {pendingSuggestions.length === 0 && suggestions.length > 0 && !showResolved && (
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-green-100 rounded-full mb-3">
            <svg
              className="w-6 h-6 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <p className="text-gray-600 font-medium">All suggestions resolved!</p>
          <p className="text-gray-500 text-sm mt-1">
            You can now approve your draft
          </p>
        </div>
      )}
    </div>
  );
}
