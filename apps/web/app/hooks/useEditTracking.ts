"use client";

import { useCallback, useRef } from "react";
import { usePreferences, PreferenceEvent } from "./usePreferences";

/**
 * Edit event types that can be tracked.
 */
export type EditEventType = "text_change" | "section_reorder" | "formatting_change";

/**
 * Structure of an edit event for tracking.
 */
export interface EditEvent {
  type: EditEventType;
  before: string;
  after: string;
  section?: string;
  metadata?: Record<string, unknown>;
}

/**
 * Configuration options for the edit tracking hook.
 */
interface UseEditTrackingOptions {
  /** Debounce delay in milliseconds (default: 2000ms) */
  debounceMs?: number;
  /** Thread ID for the current workflow session */
  threadId?: string;
  /** Whether tracking is enabled (default: true) */
  enabled?: boolean;
}

/**
 * Hook for tracking user editing behavior in the resume editor.
 *
 * Captures text changes, section reordering, and formatting changes,
 * then sends them as preference events to learn user style preferences.
 *
 * Features:
 * - Debounced event batching (2 second default)
 * - Automatic section detection
 * - Style pattern extraction (tone, quantification, etc.)
 *
 * @example
 * ```tsx
 * const { trackEdit, flush } = useEditTracking({ threadId: 'abc123' });
 *
 * // In Tiptap editor onUpdate callback:
 * editor.on('update', ({ editor }) => {
 *   trackEdit({
 *     type: 'text_change',
 *     before: previousContent,
 *     after: editor.getHTML(),
 *   });
 * });
 * ```
 */
export function useEditTracking(options: UseEditTrackingOptions = {}) {
  const { debounceMs = 2000, threadId, enabled = true } = options;
  const { recordEvent } = usePreferences();

  // Pending events to batch
  const pendingEvents = useRef<EditEvent[]>([]);
  const debounceTimer = useRef<NodeJS.Timeout | null>(null);

  /**
   * Flush all pending events to the server.
   */
  const flush = useCallback(async () => {
    if (pendingEvents.current.length === 0) return;

    const events = [...pendingEvents.current];
    pendingEvents.current = [];

    // Send each event
    for (const event of events) {
      const prefEvent: PreferenceEvent = {
        event_type: "edit",
        event_data: {
          edit_type: event.type,
          before: event.before.substring(0, 500), // Truncate for storage
          after: event.after.substring(0, 500),
          section: event.section,
          ...extractStylePatterns(event),
          ...(event.metadata || {}),
        },
        thread_id: threadId,
      };

      await recordEvent(prefEvent);
    }
  }, [recordEvent, threadId]);

  /**
   * Track an edit event. Events are batched and debounced.
   */
  const trackEdit = useCallback(
    (event: EditEvent) => {
      if (!enabled) return;

      pendingEvents.current.push(event);

      // Reset debounce timer
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }

      debounceTimer.current = setTimeout(() => {
        flush();
      }, debounceMs);
    },
    [enabled, debounceMs, flush]
  );

  /**
   * Track a text change with automatic section detection.
   */
  const trackTextChange = useCallback(
    (before: string, after: string, section?: string) => {
      if (before === after) return;

      trackEdit({
        type: "text_change",
        before,
        after,
        section: section || detectSection(before, after),
      });
    },
    [trackEdit]
  );

  /**
   * Track section reordering.
   */
  const trackSectionReorder = useCallback(
    (fromSection: string, toIndex: number) => {
      trackEdit({
        type: "section_reorder",
        before: fromSection,
        after: String(toIndex),
        section: fromSection,
        metadata: { new_index: toIndex },
      });
    },
    [trackEdit]
  );

  /**
   * Track formatting changes (bold, italic, bullets, etc.).
   */
  const trackFormattingChange = useCallback(
    (formatType: string, applied: boolean, section?: string) => {
      trackEdit({
        type: "formatting_change",
        before: applied ? "none" : formatType,
        after: applied ? formatType : "none",
        section,
        metadata: { format: formatType, applied },
      });
    },
    [trackEdit]
  );

  return {
    trackEdit,
    trackTextChange,
    trackSectionReorder,
    trackFormattingChange,
    flush,
  };
}

/**
 * Detect which section of the resume was edited based on content.
 */
function detectSection(before: string, after: string): string | undefined {
  const sectionMarkers = [
    { pattern: /summary|objective|profile/i, section: "summary" },
    { pattern: /experience|employment|work history/i, section: "experience" },
    { pattern: /education|degree|university/i, section: "education" },
    { pattern: /skills|technologies|competencies/i, section: "skills" },
    { pattern: /projects|portfolio/i, section: "projects" },
    { pattern: /certifications|certificates/i, section: "certifications" },
  ];

  const changedContent = after.length > before.length ? after : before;

  for (const { pattern, section } of sectionMarkers) {
    if (pattern.test(changedContent)) {
      return section;
    }
  }

  return undefined;
}

/**
 * Extract style patterns from an edit event for preference learning.
 */
function extractStylePatterns(event: EditEvent): Record<string, unknown> {
  const patterns: Record<string, unknown> = {};
  const { after } = event;

  // Detect first person usage
  if (/\bI\b/.test(after)) {
    patterns.uses_first_person = true;
  }

  // Detect quantification style
  const hasNumbers = /\d+%|\d+\+|\$\d+|#\d+|\d+ (team|people|years|months|projects)/i.test(after);
  if (hasNumbers) {
    patterns.uses_quantification = true;
  }

  // Detect bullet vs paragraph structure
  const hasBullets = /<li>|^[-•*]\s/m.test(after);
  if (hasBullets) {
    patterns.prefers_bullets = true;
  }

  // Detect action verbs at start
  const actionVerbPattern = /^(led|managed|developed|created|implemented|designed|built|increased|reduced|improved|delivered|achieved|launched|optimized|streamlined)/im;
  if (actionVerbPattern.test(after)) {
    patterns.uses_action_verbs = true;
  }

  return patterns;
}
