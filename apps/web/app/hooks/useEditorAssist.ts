"use client";

import { useState, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export interface UseEditorAssistReturn {
  suggestion: EditorSuggestion | null;
  isLoading: boolean;
  error: string | null;
  requestSuggestion: (
    action: EditorAction,
    selectedText: string,
    instructions?: string
  ) => Promise<void>;
  regenerateSection: (section: string, currentContent: string) => Promise<string>;
  clearSuggestion: () => void;
}

export function useEditorAssist(threadId: string | null): UseEditorAssistReturn {
  const [suggestion, setSuggestion] = useState<EditorSuggestion | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        const response = await fetch(`${API_URL}/api/optimize/${threadId}/editor/assist`, {
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

  const regenerateSection = useCallback(
    async (section: string, currentContent: string): Promise<string> => {
      if (!threadId) {
        throw new Error("No active workflow");
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_URL}/api/optimize/${threadId}/editor/regenerate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            section,
            current_content: currentContent,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to regenerate section");
        }

        const data = await response.json();

        if (data.success) {
          return data.content;
        } else {
          throw new Error(data.error || "Failed to regenerate section");
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : "Unknown error";
        setError(message);
        throw e;
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

  return {
    suggestion,
    isLoading,
    error,
    requestSuggestion,
    regenerateSection,
    clearSuggestion,
  };
}
