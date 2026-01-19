"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "./useAuth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STORAGE_KEYS = {
  preferences: "resume_agent:preferences",
  pendingEvents: "resume_agent:pending_events",
  anonymousId: "resume_agent:anonymous_id",
};

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
  event_type: "edit" | "suggestion_accept" | "suggestion_reject";
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
  const { isAuthenticated } = useAuth();
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPreferences = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      if (isAuthenticated) {
        const response = await fetch(`${API_URL}/api/preferences`, {
          credentials: "include",
        });

        if (response.ok) {
          const data = await response.json();
          setPreferences(data.preferences);
        } else {
          setPreferences(DEFAULT_PREFERENCES);
        }
      } else {
        // Load from localStorage
        const stored = localStorage.getItem(STORAGE_KEYS.preferences);
        if (stored) {
          setPreferences(JSON.parse(stored));
        } else {
          setPreferences(DEFAULT_PREFERENCES);
        }
      }
    } catch (err) {
      console.error("Failed to fetch preferences:", err);
      setError("Failed to load preferences");
      setPreferences(DEFAULT_PREFERENCES);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchPreferences();
  }, [fetchPreferences]);

  const updatePreferences = useCallback(
    async (updates: Partial<UserPreferences>) => {
      try {
        if (isAuthenticated) {
          const response = await fetch(`${API_URL}/api/preferences`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updates),
            credentials: "include",
          });

          if (response.ok) {
            const data = await response.json();
            setPreferences(data.preferences);
            return true;
          }
          return false;
        } else {
          // Save to localStorage
          const newPrefs = { ...preferences, ...updates };
          setPreferences(newPrefs);
          localStorage.setItem(STORAGE_KEYS.preferences, JSON.stringify(newPrefs));
          return true;
        }
      } catch (err) {
        console.error("Failed to update preferences:", err);
        return false;
      }
    },
    [isAuthenticated, preferences]
  );

  const resetPreferences = useCallback(async () => {
    try {
      if (isAuthenticated) {
        const response = await fetch(`${API_URL}/api/preferences/reset`, {
          method: "POST",
          credentials: "include",
        });

        if (response.ok) {
          setPreferences(DEFAULT_PREFERENCES);
          return true;
        }
        return false;
      } else {
        setPreferences(DEFAULT_PREFERENCES);
        localStorage.removeItem(STORAGE_KEYS.preferences);
        return true;
      }
    } catch (err) {
      console.error("Failed to reset preferences:", err);
      return false;
    }
  }, [isAuthenticated]);

  const recordEvent = useCallback(
    async (event: PreferenceEvent) => {
      try {
        if (isAuthenticated) {
          await fetch(`${API_URL}/api/preferences/events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(event),
            credentials: "include",
          });
        } else {
          // Store locally for later migration
          const stored = localStorage.getItem(STORAGE_KEYS.pendingEvents);
          const events = stored ? JSON.parse(stored) : [];
          events.push({ ...event, created_at: new Date().toISOString() });
          localStorage.setItem(STORAGE_KEYS.pendingEvents, JSON.stringify(events));

          // Ensure anonymous ID exists
          if (!localStorage.getItem(STORAGE_KEYS.anonymousId)) {
            localStorage.setItem(STORAGE_KEYS.anonymousId, crypto.randomUUID());
          }
        }
      } catch (err) {
        console.error("Failed to record event:", err);
      }
    },
    [isAuthenticated]
  );

  return {
    preferences,
    isLoading,
    error,
    updatePreferences,
    resetPreferences,
    recordEvent,
    refresh: fetchPreferences,
  };
}
