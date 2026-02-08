"use client";

import { useState, useCallback, useRef } from "react";


export type EditorAction =
  | "improve"
  | "add_keywords"
  | "quantify"
  | "shorten"
  | "rewrite"
  | "fix_tone"
  | "custom";

export interface EditorSuggestion {
  success: boolean;
  original: string;
  suggestion: string;
  action: EditorAction;
  error?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface DraftingChatResult {
  suggestion: string;
  cacheHit: boolean;
}

export interface UseEditorAssistReturn {
  suggestion: EditorSuggestion | null;
  isLoading: boolean;
  error: string | null;
  requestSuggestion: (
    action: EditorAction,
    selectedText: string,
    instructions?: string
  ) => Promise<void>;
  clearSuggestion: () => void;
  // New methods for enhanced drafting chat
  chatWithDraftingAgent: (
    selectedText: string,
    userMessage: string,
    chatHistory: ChatMessage[]
  ) => Promise<DraftingChatResult | null>;
  syncEditor: (
    html: string,
    original?: string,
    suggestion?: string,
    userMessage?: string
  ) => void;
}

export function useEditorAssist(threadId: string | null): UseEditorAssistReturn {
  const [suggestion, setSuggestion] = useState<EditorSuggestion | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track pending syncs to avoid duplicate requests
  const pendingSyncRef = useRef<AbortController | null>(null);

  const requestSuggestion = useCallback(
    async (action: EditorAction, selectedText: string, instructions?: string) => {
      if (!threadId) {
        setError("No active workflow");
        return;
      }

      if (!selectedText.trim()) {
        setError("No text selected");
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/optimize/${threadId}/editor/assist`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            selected_text: selectedText,
            instructions,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to get suggestion");
        }

        const data = await response.json();

        if (data.success) {
          setSuggestion({
            success: true,
            original: selectedText,
            suggestion: data.suggestion,
            action,
          });
        } else {
          setError(data.error || "Failed to generate suggestion");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setIsLoading(false);
      }
    },
    [threadId]
  );

  const clearSuggestion = useCallback(() => {
    setSuggestion(null);
    setError(null);
  }, []);

  // Chat with drafting agent - uses full context with prompt caching
  // Backend uses synced state, so no HTML in request needed
  const chatWithDraftingAgent = useCallback(
    async (
      selectedText: string,
      userMessage: string,
      chatHistory: ChatMessage[]
    ): Promise<DraftingChatResult | null> => {
      if (!threadId) {
        setError("No active workflow");
        return null;
      }

      if (!selectedText.trim()) {
        setError("No text selected");
        return null;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/optimize/${threadId}/editor/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            selected_text: selectedText,
            user_message: userMessage,
            chat_history: chatHistory.map((m) => ({
              role: m.role,
              content: m.content,
            })),
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to get suggestion");
        }

        const data = await response.json();

        if (data.success) {
          // Also set as current suggestion for apply flow
          setSuggestion({
            success: true,
            original: selectedText,
            suggestion: data.suggestion,
            action: "custom",
          });
          return {
            suggestion: data.suggestion,
            cacheHit: data.cache_hit || false,
          };
        } else {
          setError(data.error || "Failed to generate suggestion");
          return null;
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [threadId]
  );

  // Sync editor state to backend (fire and forget)
  // Called after apply or undo to keep backend state in sync
  // Also tracks accepted suggestions for preference learning
  const syncEditor = useCallback(
    (
      html: string,
      original?: string,
      suggestion?: string,
      userMessage?: string
    ) => {
      if (!threadId) return;

      // Cancel any pending sync
      if (pendingSyncRef.current) {
        pendingSyncRef.current.abort();
      }

      const controller = new AbortController();
      pendingSyncRef.current = controller;

      // Fire and forget - don't await
      fetch(`/api/optimize/${threadId}/editor/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          html,
          original: original || "",
          suggestion: suggestion || "",
          user_message: userMessage || "",
        }),
        signal: controller.signal,
      }).catch(() => {
        // Ignore errors - this is best effort
      }).finally(() => {
        if (pendingSyncRef.current === controller) {
          pendingSyncRef.current = null;
        }
      });
    },
    [threadId]
  );

  return {
    suggestion,
    isLoading,
    error,
    requestSuggestion,
    clearSuggestion,
    chatWithDraftingAgent,
    syncEditor,
  };
}
