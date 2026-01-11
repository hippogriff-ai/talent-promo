"use client";

import { useState, useCallback } from "react";
import type { DraftingSuggestion, SuggestionStatus } from "./useDraftingStorage";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseSuggestionsProps {
  threadId: string;
  onSuggestionResolved?: (
    suggestionId: string,
    action: "accept" | "decline"
  ) => void;
}

interface UseSuggestionsReturn {
  isLoading: boolean;
  error: string | null;
  acceptSuggestion: (suggestionId: string) => Promise<{ version: string } | null>;
  declineSuggestion: (suggestionId: string) => Promise<{ version: string } | null>;
}

/**
 * Hook for handling suggestion accept/decline actions via API.
 */
export function useSuggestions({
  threadId,
  onSuggestionResolved,
}: UseSuggestionsProps): UseSuggestionsReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const acceptSuggestion = useCallback(
    async (suggestionId: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${API_URL}/api/optimize/${threadId}/drafting/suggestion`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              suggestion_id: suggestionId,
              action: "accept",
            }),
          }
        );

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || "Failed to accept suggestion");
        }

        const data = await response.json();
        onSuggestionResolved?.(suggestionId, "accept");
        return { version: data.version };
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [threadId, onSuggestionResolved]
  );

  const declineSuggestion = useCallback(
    async (suggestionId: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${API_URL}/api/optimize/${threadId}/drafting/suggestion`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              suggestion_id: suggestionId,
              action: "decline",
            }),
          }
        );

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || "Failed to decline suggestion");
        }

        const data = await response.json();
        onSuggestionResolved?.(suggestionId, "decline");
        return { version: data.version };
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [threadId, onSuggestionResolved]
  );

  return {
    isLoading,
    error,
    acceptSuggestion,
    declineSuggestion,
  };
}

/**
 * Hook for fetching drafting state from API.
 */
export function useDraftingState(threadId: string) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchState = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_URL}/api/optimize/${threadId}/drafting/state`
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to fetch drafting state");
      }

      return await response.json();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [threadId]);

  const saveManually = useCallback(
    async (htmlContent: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${API_URL}/api/optimize/${threadId}/drafting/save`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ html_content: htmlContent }),
          }
        );

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || "Failed to save");
        }

        return await response.json();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [threadId]
  );

  const restoreVersion = useCallback(
    async (version: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${API_URL}/api/optimize/${threadId}/drafting/restore`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ version }),
          }
        );

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || "Failed to restore version");
        }

        return await response.json();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [threadId]
  );

  const approveDraft = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_URL}/api/optimize/${threadId}/drafting/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved: true }),
        }
      );

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to approve draft");
      }

      return await response.json();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [threadId]);

  return {
    isLoading,
    error,
    fetchState,
    saveManually,
    restoreVersion,
    approveDraft,
  };
}
