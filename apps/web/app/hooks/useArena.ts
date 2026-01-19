/**
 * Hook for managing arena A/B comparisons.
 */

import { useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ArenaComparison {
  arena_id: string;
  variant_a_thread_id: string;
  variant_b_thread_id: string;
  status: string;
  sync_point?: string;
  winner?: string;
  created_at: string;
  completed_at?: string;
}

export interface VariantStatus {
  thread_id: string;
  status: string;
  current_step: string;
  progress_messages?: Array<{ message: string; timestamp: string }>;
  user_profile?: Record<string, unknown>;
  job_posting?: Record<string, unknown>;
  research?: Record<string, unknown>;
  gap_analysis?: Record<string, unknown>;
  resume_html?: string;
}

export interface VariantMetrics {
  variant: string;
  thread_id: string;
  total_duration_ms: number;
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  ats_score?: number;
}

export interface ArenaStatus {
  arena_id: string;
  status: string;
  sync_point?: string;
  variant_a?: VariantStatus;
  variant_b?: VariantStatus;
  ratings: Array<{
    rating_id: string;
    step: string;
    aspect: string;
    preference: string;
    reason?: string;
  }>;
  metrics: Record<string, VariantMetrics>;
}

export interface Analytics {
  total_comparisons: number;
  total_ratings: number;
  variant_a_wins: number;
  variant_b_wins: number;
  ties: number;
  win_rate_a: number;
  win_rate_b: number;
  by_step: Record<string, { A: number; B: number; tie: number }>;
  by_aspect: Record<string, { A: number; B: number; tie: number }>;
}

interface StartComparisonResponse {
  arena_id: string;
  variant_a_thread_id: string;
  variant_b_thread_id: string;
}

interface ListComparisonsResponse {
  comparisons: ArenaComparison[];
  count: number;
}

export interface ArenaStreamEvent {
  type: "step_update" | "progress" | "sync" | "complete" | "error" | "timeout";
  variant?: "A" | "B";
  step?: string;
  timestamp?: string;
  message?: string;
  phase?: string;
  detail?: string;
  variant_a?: string;
  variant_b?: string;
}

export function useArena(adminToken: string) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const headers = useCallback(
    (): HeadersInit => ({
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken,
    }),
    [adminToken]
  );

  const request = useCallback(
    async <T>(
      path: string,
      errorMessage: string,
      options?: { method?: string; body?: unknown }
    ): Promise<T | null> => {
      try {
        const res = await fetch(`${API_BASE}${path}`, {
          method: options?.method || "GET",
          headers: headers(),
          body: options?.body ? JSON.stringify(options.body) : undefined,
        });
        if (!res.ok) throw new Error(errorMessage);
        return (await res.json()) as T;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
        return null;
      }
    },
    [headers]
  );

  const startComparison = useCallback(
    async (input: {
      linkedin_url?: string;
      job_url?: string;
      resume_text?: string;
      job_text?: string;
    }): Promise<StartComparisonResponse | null> => {
      setLoading(true);
      setError(null);
      const result = await request<StartComparisonResponse>(
        "/api/arena/start",
        "Failed to start comparison",
        { method: "POST", body: input }
      );
      setLoading(false);
      return result;
    },
    [request]
  );

  const getStatus = useCallback(
    (arenaId: string): Promise<ArenaStatus | null> =>
      request<ArenaStatus>(`/api/arena/${arenaId}/status`, "Failed to get status"),
    [request]
  );

  const submitAnswer = useCallback(
    async (arenaId: string, text: string): Promise<boolean> => {
      const result = await request<{ success: boolean }>(
        `/api/arena/${arenaId}/answer`,
        "Failed to submit answer",
        { method: "POST", body: { text } }
      );
      return result !== null;
    },
    [request]
  );

  const submitRating = useCallback(
    async (
      arenaId: string,
      step: string,
      aspect: string,
      preference: "A" | "B" | "tie",
      reason?: string
    ): Promise<boolean> => {
      const result = await request<{ success: boolean }>(
        `/api/arena/${arenaId}/rate`,
        "Failed to submit rating",
        { method: "POST", body: { step, aspect, preference, reason } }
      );
      return result !== null;
    },
    [request]
  );

  const getAnalytics = useCallback(
    (): Promise<Analytics | null> =>
      request<Analytics>("/api/arena/analytics", "Failed to get analytics"),
    [request]
  );

  const listComparisons = useCallback(
    (limit = 20, offset = 0): Promise<ListComparisonsResponse | null> =>
      request<ListComparisonsResponse>(
        `/api/arena/comparisons?limit=${limit}&offset=${offset}`,
        "Failed to list comparisons"
      ),
    [request]
  );

  const exportComparison = useCallback(
    async (arenaId: string, format: "json" | "csv" = "json"): Promise<Blob | null> => {
      try {
        const res = await fetch(
          `${API_BASE}/api/arena/${arenaId}/export?format=${format}`,
          { headers: headers() }
        );
        if (!res.ok) throw new Error("Failed to export comparison");
        return await res.blob();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Export failed");
        return null;
      }
    },
    [headers]
  );

  const exportAnalytics = useCallback(
    async (format: "json" | "csv" = "json"): Promise<Blob | null> => {
      try {
        const res = await fetch(
          `${API_BASE}/api/arena/export/analytics?format=${format}`,
          { headers: headers() }
        );
        if (!res.ok) throw new Error("Failed to export analytics");
        return await res.blob();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Export failed");
        return null;
      }
    },
    [headers]
  );

  const getSSEToken = useCallback(
    async (arenaId: string): Promise<string | null> => {
      try {
        const res = await fetch(`${API_BASE}/api/arena/${arenaId}/sse-token`, {
          method: "POST",
          headers: headers(),
        });
        if (!res.ok) {
          console.error(`Failed to get SSE token: ${res.status} ${res.statusText}`);
          return null;
        }
        const data = await res.json();
        return data.token;
      } catch (e) {
        console.error("SSE token fetch error:", e);
        return null;
      }
    },
    [headers]
  );

  const subscribeToStream = useCallback(
    (
      arenaId: string,
      onEvent: (event: ArenaStreamEvent) => void,
      onError?: (error: Event) => void
    ): (() => void) => {
      let eventSource: EventSource | null = null;
      let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
      let isComplete = false;
      let reconnectAttempts = 0;
      const maxReconnectAttempts = 3;
      let sseToken: string | null = null;

      const connect = async () => {
        if (isComplete) return;

        // Get fresh short-lived SSE token (tokens are single-use)
        sseToken = await getSSEToken(arenaId);
        if (!sseToken) {
          console.error("Failed to obtain SSE token, aborting connection");
          onError?.(new Event("token_error"));
          return;
        }

        eventSource = new EventSource(
          `${API_BASE}/api/arena/${arenaId}/stream?token=${sseToken}`
        );

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as ArenaStreamEvent;
            onEvent(data);

            // Mark complete on terminal events
            if (data.type === "complete" || data.type === "timeout") {
              isComplete = true;
            }
            // Reset reconnect counter on successful message
            reconnectAttempts = 0;
          } catch (e) {
            console.error("Failed to parse SSE event:", e, event.data);
          }
        };

        eventSource.onerror = (error) => {
          console.error("SSE connection error:", error);
          eventSource?.close();
          eventSource = null;
          onError?.(error);

          // Attempt reconnect if not complete and under max attempts
          if (!isComplete && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            reconnectTimeout = setTimeout(connect, 3000);
          }
        };
      };

      void connect();

      // Return cleanup function
      return () => {
        isComplete = true;
        sseToken = null;
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        eventSource?.close();
      };
    },
    [getSSEToken]
  );

  return {
    loading,
    error,
    startComparison,
    getStatus,
    submitAnswer,
    submitRating,
    getAnalytics,
    listComparisons,
    exportComparison,
    exportAnalytics,
    subscribeToStream,
  };
}
