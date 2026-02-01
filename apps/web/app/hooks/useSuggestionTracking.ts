"use client";

import { useCallback } from "react";
import { usePreferences, PreferenceEvent } from "./usePreferences";

/**
 * Types of suggestion events that can be tracked.
 */
export type SuggestionEventType =
  | "suggestion_accept"
  | "suggestion_reject"
  | "suggestion_dismiss"
  | "suggestion_implicit_reject";

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
   * Track when a user dismisses a suggestion without accepting or rejecting.
   * This is a weak negative signal (user didn't want to deal with it).
   */
  const trackDismiss = useCallback(
    async (suggestion: TrackedSuggestion) => {
      if (!enabled) return;

      const event: PreferenceEvent = {
        event_type: "suggestion_dismiss",
        event_data: {
          suggestion_id: suggestion.id,
          location: suggestion.location,
          original_text: suggestion.original_text.substring(0, 500),
          proposed_text: suggestion.proposed_text.substring(0, 500),
          rationale: suggestion.rationale,
          ...extractSuggestionPatterns(suggestion, "dismiss"),
        },
        thread_id: threadId,
      };

      await recordEvent(event);
    },
    [enabled, recordEvent, threadId]
  );

  /**
   * Track when a user manually edits content differently from a pending suggestion.
   * This is an implicit rejection - the user saw the suggestion but chose to do something else.
   */
  const trackImplicitReject = useCallback(
    async (suggestion: TrackedSuggestion, userEditedText: string) => {
      if (!enabled) return;

      const event: PreferenceEvent = {
        event_type: "suggestion_implicit_reject",
        event_data: {
          suggestion_id: suggestion.id,
          location: suggestion.location,
          original_text: suggestion.original_text.substring(0, 500),
          proposed_text: suggestion.proposed_text.substring(0, 500),
          user_edited_text: userEditedText.substring(0, 500),
          rationale: suggestion.rationale,
          // Compare user's choice vs suggestion to learn patterns
          ...extractImplicitRejectionPatterns(suggestion, userEditedText),
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
    trackDismiss,
    trackImplicitReject,
    wrapAcceptHandler,
    wrapRejectHandler,
  };
}

/**
 * Extract learning patterns from a suggestion interaction.
 */
function extractSuggestionPatterns(
  suggestion: TrackedSuggestion,
  action: "accept" | "reject" | "dismiss"
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
  } else if (action === "reject") {
    // If explicitly rejected, user strongly dislikes this pattern
    if (isFormal) patterns.dislikes_formal_tone = true;
    if (isConversational) patterns.dislikes_conversational_tone = true;
  }
  // For "dismiss", we don't set tone patterns - it's too weak a signal

  // Detect quantification in suggestion
  const hasQuantification = /\d+%|\d+x|\$\d+|\d+ (team|people|users|customers)/i.test(proposed_text);
  if (hasQuantification) {
    if (action === "accept") {
      patterns.prefers_quantification = true;
    } else if (action === "reject") {
      patterns.dislikes_quantification = true;
    }
    // dismiss: no strong signal
  }

  // Detect action verb usage
  const startsWithActionVerb = /^(Led|Managed|Developed|Created|Implemented|Built|Designed|Delivered|Achieved|Launched)/i.test(proposed_text);
  if (startsWithActionVerb) {
    if (action === "accept") {
      patterns.prefers_action_verbs = true;
    } else if (action === "reject") {
      patterns.dislikes_action_verbs = true;
    }
    // dismiss: no strong signal
  }

  return patterns;
}

/**
 * Extract learning patterns when user implicitly rejects a suggestion by editing differently.
 * Compares what the AI suggested vs what the user actually wrote.
 */
function extractImplicitRejectionPatterns(
  suggestion: TrackedSuggestion,
  userEditedText: string
): Record<string, unknown> {
  const patterns: Record<string, unknown> = {};
  const { proposed_text, location } = suggestion;

  patterns.suggestion_location = location;
  patterns.implicit_rejection = true;

  // Compare what AI suggested vs what user chose
  const suggestionHasMetrics = /\d+%|\d+x|\$\d+|\d+ (team|people|users|customers)/i.test(proposed_text);
  const userHasMetrics = /\d+%|\d+x|\$\d+|\d+ (team|people|users|customers)/i.test(userEditedText);

  // If AI added metrics but user removed them
  if (suggestionHasMetrics && !userHasMetrics) {
    patterns.dislikes_quantification = true;
  }
  // If AI didn't have metrics but user added them
  if (!suggestionHasMetrics && userHasMetrics) {
    patterns.prefers_quantification = true;
  }

  // Compare tone
  const suggestionFormal = /\b(implemented|executed|facilitated|spearheaded)\b/i.test(proposed_text);
  const userFormal = /\b(implemented|executed|facilitated|spearheaded)\b/i.test(userEditedText);
  const suggestionCasual = /\b(helped|worked on|got|made)\b/i.test(proposed_text);
  const userCasual = /\b(helped|worked on|got|made)\b/i.test(userEditedText);

  // User chose different tone than suggestion
  if (suggestionFormal && !userFormal && userCasual) {
    patterns.prefers_conversational_tone = true;
    patterns.dislikes_formal_tone = true;
  }
  if (suggestionCasual && !userCasual && userFormal) {
    patterns.prefers_formal_tone = true;
    patterns.dislikes_conversational_tone = true;
  }

  // Compare length preference
  const suggestionLength = proposed_text.length;
  const userLength = userEditedText.length;
  if (userLength < suggestionLength * 0.7) {
    patterns.prefers_concise = true;
  } else if (userLength > suggestionLength * 1.3) {
    patterns.prefers_detailed = true;
  }

  // Check if user kept original instead of taking suggestion
  if (userEditedText.trim() === suggestion.original_text.trim()) {
    patterns.kept_original = true;
  }

  return patterns;
}
