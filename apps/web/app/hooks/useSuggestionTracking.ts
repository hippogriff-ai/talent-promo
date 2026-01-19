"use client";

import { useCallback } from "react";
import { usePreferences, PreferenceEvent } from "./usePreferences";

/**
 * Types of suggestion events that can be tracked.
 */
export type SuggestionEventType = "suggestion_accept" | "suggestion_reject";

/**
 * Structure of a suggestion for tracking purposes.
 */
export interface TrackedSuggestion {
  id: string;
  location: string;
  original_text: string;
  proposed_text: string;
  rationale?: string;
}

/**
 * Configuration options for the suggestion tracking hook.
 */
interface UseSuggestionTrackingOptions {
  /** Thread ID for the current workflow session */
  threadId?: string;
  /** Whether tracking is enabled (default: true) */
  enabled?: boolean;
}

/**
 * Hook for tracking user responses to AI suggestions.
 *
 * Captures when users accept, reject, or modify AI-generated suggestions
 * to learn their preferences for future draft generation.
 *
 * Features:
 * - Track accepted suggestions (learn what user likes)
 * - Track rejected suggestions (learn what user dislikes)
 * - Track modifications (learn user's preferred phrasing)
 *
 * @example
 * ```tsx
 * const { trackAccept, trackReject } = useSuggestionTracking({ threadId: 'abc123' });
 *
 * // When user accepts a suggestion:
 * const handleAccept = (suggestion) => {
 *   trackAccept(suggestion);
 *   // ... apply suggestion to editor
 * };
 * ```
 */
export function useSuggestionTracking(options: UseSuggestionTrackingOptions = {}) {
  const { threadId, enabled = true } = options;
  const { recordEvent } = usePreferences();

  /**
   * Track when a user accepts an AI suggestion.
   */
  const trackAccept = useCallback(
    async (suggestion: TrackedSuggestion, modifiedText?: string) => {
      if (!enabled) return;

      const wasModified = Boolean(modifiedText && modifiedText !== suggestion.proposed_text);

      const event: PreferenceEvent = {
        event_type: "suggestion_accept",
        event_data: {
          suggestion_id: suggestion.id,
          location: suggestion.location,
          original_text: suggestion.original_text.substring(0, 500),
          proposed_text: suggestion.proposed_text.substring(0, 500),
          rationale: suggestion.rationale,
          was_modified: wasModified,
          final_text: modifiedText?.substring(0, 500),
          ...extractSuggestionPatterns(suggestion, "accept"),
        },
        thread_id: threadId,
      };

      await recordEvent(event);
    },
    [enabled, recordEvent, threadId]
  );

  /**
   * Track when a user rejects an AI suggestion.
   */
  const trackReject = useCallback(
    async (suggestion: TrackedSuggestion, reason?: string) => {
      if (!enabled) return;

      const event: PreferenceEvent = {
        event_type: "suggestion_reject",
        event_data: {
          suggestion_id: suggestion.id,
          location: suggestion.location,
          original_text: suggestion.original_text.substring(0, 500),
          proposed_text: suggestion.proposed_text.substring(0, 500),
          rationale: suggestion.rationale,
          rejection_reason: reason,
          ...extractSuggestionPatterns(suggestion, "reject"),
        },
        thread_id: threadId,
      };

      await recordEvent(event);
    },
    [enabled, recordEvent, threadId]
  );

  /**
   * Create a wrapped accept handler for use with existing suggestion UI.
   */
  const wrapAcceptHandler = useCallback(
    <T extends TrackedSuggestion>(
      originalHandler: (suggestion: T) => void | Promise<void>
    ) => {
      return async (suggestion: T, modifiedText?: string) => {
        await trackAccept(suggestion, modifiedText);
        await originalHandler(suggestion);
      };
    },
    [trackAccept]
  );

  /**
   * Create a wrapped reject handler for use with existing suggestion UI.
   */
  const wrapRejectHandler = useCallback(
    <T extends TrackedSuggestion>(
      originalHandler: (suggestion: T) => void | Promise<void>
    ) => {
      return async (suggestion: T, reason?: string) => {
        await trackReject(suggestion, reason);
        await originalHandler(suggestion);
      };
    },
    [trackReject]
  );

  return {
    trackAccept,
    trackReject,
    wrapAcceptHandler,
    wrapRejectHandler,
  };
}

/**
 * Extract learning patterns from a suggestion interaction.
 */
function extractSuggestionPatterns(
  suggestion: TrackedSuggestion,
  action: "accept" | "reject"
): Record<string, unknown> {
  const patterns: Record<string, unknown> = {};
  const { proposed_text, location } = suggestion;

  // Track location preferences
  patterns.suggestion_location = location;

  // Detect tone changes
  const isFormal = /\b(implemented|executed|facilitated|spearheaded)\b/i.test(proposed_text);
  const isConversational = /\b(helped|worked on|got|made)\b/i.test(proposed_text);

  if (action === "accept") {
    if (isFormal) patterns.prefers_formal_tone = true;
    if (isConversational) patterns.prefers_conversational_tone = true;
  } else {
    // If rejected, user might prefer the opposite
    if (isFormal) patterns.dislikes_formal_tone = true;
    if (isConversational) patterns.dislikes_conversational_tone = true;
  }

  // Detect quantification in suggestion
  const hasQuantification = /\d+%|\d+x|\$\d+|\d+ (team|people|users|customers)/i.test(proposed_text);
  if (hasQuantification) {
    patterns[action === "accept" ? "prefers_quantification" : "dislikes_quantification"] = true;
  }

  // Detect action verb usage
  const startsWithActionVerb = /^(Led|Managed|Developed|Created|Implemented|Built|Designed|Delivered|Achieved|Launched)/i.test(proposed_text);
  if (startsWithActionVerb) {
    patterns[action === "accept" ? "prefers_action_verbs" : "dislikes_action_verbs"] = true;
  }

  return patterns;
}
