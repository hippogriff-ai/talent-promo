"use client";

import { useState, useEffect, useCallback } from "react";

const API_URL = "";

const STORAGE_KEYS = {
  preferences: "resume_agent:preferences",
  pendingEvents: "resume_agent:pending_events",
  anonymousId: "resume_agent:anonymous_id",
};

// Minimum events before triggering learning
const MIN_EVENTS_FOR_LEARNING = 5;

export interface UserPreferences {
  tone: string | null;
  structure: string | null;
  sentence_length: string | null;
  first_person: boolean | null;
  quantification_preference: string | null;
  achievement_focus: boolean | null;
  custom_preferences: Record<string, unknown>;
}

export interface PreferenceEvent {
  event_type: "edit" | "suggestion_accept" | "suggestion_reject" | "suggestion_dismiss" | "suggestion_implicit_reject";
  event_data: Record<string, unknown>;
  thread_id?: string;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  tone: null,
  structure: null,
  sentence_length: null,
  first_person: null,
  quantification_preference: null,
  achievement_focus: null,
  custom_preferences: {},
};

export function usePreferences() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPreferences = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Always load from localStorage (anonymous mode)
      const stored = localStorage.getItem(STORAGE_KEYS.preferences);
      if (stored) {
        setPreferences(JSON.parse(stored));
      } else {
        setPreferences(DEFAULT_PREFERENCES);
      }
    } catch (err) {
      console.error("Failed to fetch preferences:", err);
      setError("Failed to load preferences");
      setPreferences(DEFAULT_PREFERENCES);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPreferences();
  }, [fetchPreferences]);

  const updatePreferences = useCallback(
    async (updates: Partial<UserPreferences>) => {
      try {
        // Save to localStorage (anonymous mode)
        const newPrefs = { ...preferences, ...updates };
        setPreferences(newPrefs);
        localStorage.setItem(STORAGE_KEYS.preferences, JSON.stringify(newPrefs));
        return true;
      } catch (err) {
        console.error("Failed to update preferences:", err);
        return false;
      }
    },
    [preferences]
  );

  const resetPreferences = useCallback(async () => {
    try {
      setPreferences(DEFAULT_PREFERENCES);
      localStorage.removeItem(STORAGE_KEYS.preferences);
      return true;
    } catch (err) {
      console.error("Failed to reset preferences:", err);
      return false;
    }
  }, []);

  const recordEvent = useCallback(
    async (event: PreferenceEvent) => {
      try {
        // Store locally (anonymous mode)
        const stored = localStorage.getItem(STORAGE_KEYS.pendingEvents);
        const events = stored ? JSON.parse(stored) : [];
        events.push({ ...event, created_at: new Date().toISOString() });
        localStorage.setItem(STORAGE_KEYS.pendingEvents, JSON.stringify(events));

        // Ensure anonymous ID exists
        if (!localStorage.getItem(STORAGE_KEYS.anonymousId)) {
          localStorage.setItem(STORAGE_KEYS.anonymousId, crypto.randomUUID());
        }
      } catch (err) {
        console.error("Failed to record event:", err);
      }
    },
    []
  );

  /**
   * Learn preferences from accumulated events.
   * Sends events to backend for LLM analysis and updates preferences.
   * Clears pending events after successful learning.
   *
   * @param forceLearn - If true, learn even with fewer than MIN_EVENTS_FOR_LEARNING events
   * @returns Learning result with learned preferences and whether they were applied
   */
  const learnFromEvents = useCallback(
    async (forceLearn = false): Promise<{
      learned: Partial<UserPreferences>;
      applied: boolean;
      reasoning: string;
    } | null> => {
      try {
        // Get pending events
        const stored = localStorage.getItem(STORAGE_KEYS.pendingEvents);
        const events = stored ? JSON.parse(stored) : [];

        // Check if we have enough events
        if (!forceLearn && events.length < MIN_EVENTS_FOR_LEARNING) {
          console.log(
            `Not enough events for learning: ${events.length}/${MIN_EVENTS_FOR_LEARNING}`
          );
          return null;
        }

        if (events.length === 0) {
          return null;
        }

        // Get anonymous ID
        const anonymousId = localStorage.getItem(STORAGE_KEYS.anonymousId);

        // Call backend to learn preferences
        const response = await fetch(`${API_URL}/api/preferences/learn`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(anonymousId ? { "X-Anonymous-ID": anonymousId } : {}),
          },
          body: JSON.stringify({
            events,
            apply_threshold: 0.5,
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || "Failed to learn preferences");
        }

        const result = await response.json();

        // Update local preferences if learning was applied
        if (result.applied && result.final_preferences) {
          const finalPrefs = result.final_preferences;
          setPreferences({
            tone: finalPrefs.tone,
            structure: finalPrefs.structure,
            sentence_length: finalPrefs.sentence_length,
            first_person: finalPrefs.first_person,
            quantification_preference: finalPrefs.quantification_preference,
            achievement_focus: finalPrefs.achievement_focus,
            custom_preferences: finalPrefs.custom_preferences || {},
          });
          localStorage.setItem(
            STORAGE_KEYS.preferences,
            JSON.stringify({
              tone: finalPrefs.tone,
              structure: finalPrefs.structure,
              sentence_length: finalPrefs.sentence_length,
              first_person: finalPrefs.first_person,
              quantification_preference: finalPrefs.quantification_preference,
              achievement_focus: finalPrefs.achievement_focus,
              custom_preferences: finalPrefs.custom_preferences || {},
            })
          );
        }

        // Clear pending events after successful learning
        localStorage.removeItem(STORAGE_KEYS.pendingEvents);

        return {
          learned: result.learned_preferences,
          applied: result.applied,
          reasoning: result.reasoning,
        };
      } catch (err) {
        console.error("Failed to learn from events:", err);
        return null;
      }
    },
    []
  );

  /**
   * Get the count of pending events waiting to be learned from.
   */
  const getPendingEventCount = useCallback((): number => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.pendingEvents);
      const events = stored ? JSON.parse(stored) : [];
      return events.length;
    } catch {
      return 0;
    }
  }, []);

  return {
    preferences,
    isLoading,
    error,
    updatePreferences,
    resetPreferences,
    recordEvent,
    learnFromEvents,
    getPendingEventCount,
    refresh: fetchPreferences,
  };
}
