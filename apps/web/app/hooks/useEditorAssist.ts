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
  revisionId?: string;
  documentRevisionId?: string;
  targetUnit?: RevisionTarget;
  editPlan?: EditPlan;
  patch?: string;
  verification?: VerificationReport;
  canApply?: boolean;
  overrideRequired?: boolean;
  error?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface DraftingChatResult {
  suggestion: string;
  cacheHit: boolean;
  revisionId?: string;
  canApply?: boolean;
  verification?: VerificationReport;
}

export interface RevisionTarget {
  id: string;
  kind: string;
  label: string;
  text: string;
  textPreview: string;
}

export interface EditPlan {
  id: string;
  goal: string;
  targetUnitId: string;
  targetLabel: string;
  scope: "single_unit";
  assertions: Array<{ id: string; description: string; status: string }>;
  todos: Array<{ id: string; label: string; status: string }>;
}

export interface VerificationReport {
  passed: boolean;
  checks: Array<{ id: string; passed: boolean; reason: string }>;
  evidence: string;
  summary: string;
}

export interface ApplyRevisionResult {
  success: boolean;
  resumeHtml?: string;
  resumeMarkdown?: string;
  documentRevisionId?: string;
  commit?: { sha: string; message: string } | null;
  changedUnitIds?: string[];
  error?: string;
}

export interface UseEditorAssistReturn {
  suggestion: EditorSuggestion | null;
  isLoading: boolean;
  error: string | null;
  requestSuggestion: (
    action: EditorAction,
    selectedText: string,
    instructions?: string,
    editorSelection?: EditorSelectionPayload | null
  ) => Promise<void>;
  clearSuggestion: () => void;
  // New methods for enhanced drafting chat
  chatWithDraftingAgent: (
    selectedText: string,
    userMessage: string,
    chatHistory: ChatMessage[],
    editorSelection?: EditorSelectionPayload | null
  ) => Promise<DraftingChatResult | null>;
  syncEditor: (
    html: string,
    original?: string,
    suggestion?: string,
    userMessage?: string
  ) => Promise<boolean>;
  applyRevision: (
    revisionId: string,
    overrideVerification?: boolean
  ) => Promise<ApplyRevisionResult | null>;
}

export interface EditorSelectionPayload {
  from: number;
  to: number;
  context_before?: string;
  context_after?: string;
}

export function useEditorAssist(threadId: string | null): UseEditorAssistReturn {
  const [suggestion, setSuggestion] = useState<EditorSuggestion | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track pending syncs to avoid duplicate requests
  const pendingSyncRef = useRef<AbortController | null>(null);

  const actionMessage = useCallback((action: EditorAction, instructions?: string) => {
    if (action === "custom") {
      return instructions || "Revise the selected resume text.";
    }
    const messages: Record<EditorAction, string> = {
      improve: "Improve the selected resume text.",
      add_keywords: "Add relevant ATS keywords naturally.",
      quantify: "Add credible metrics or quantification where possible.",
      shorten: "Make the selected resume text more concise.",
      rewrite: "Rewrite the selected resume text with fresh language.",
      fix_tone: "Make the selected resume text more professional and confident.",
      custom: "Revise the selected resume text.",
    };
    return instructions || messages[action];
  }, []);

  const suggestionFromRevision = useCallback(
    (data: any, fallbackOriginal: string, action: EditorAction): EditorSuggestion => ({
      success: true,
      original: data.targetUnit?.text || fallbackOriginal,
      suggestion: data.proposedText || data.suggestion || "",
      action,
      revisionId: data.revisionId,
      documentRevisionId: data.documentRevisionId,
      targetUnit: data.targetUnit,
      editPlan: data.editPlan,
      patch: data.patch,
      verification: data.verification,
      canApply: data.canApply,
      overrideRequired: data.overrideRequired,
    }),
    []
  );

  const requestSuggestion = useCallback(
    async (
      action: EditorAction,
      selectedText: string,
      instructions?: string,
      editorSelection?: EditorSelectionPayload | null
    ) => {
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
        const response = await fetch(`/api/resume/documents/${threadId}/revision`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            user_message: actionMessage(action, instructions),
            selected_text: selectedText,
            instructions,
            editor_selection: editorSelection,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to get suggestion");
        }

        const data = await response.json();

        if (data.success) {
          setSuggestion(suggestionFromRevision(data, selectedText, action));
        } else {
          setError(data.error || "Failed to generate suggestion");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setIsLoading(false);
      }
    },
    [actionMessage, suggestionFromRevision, threadId]
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
      chatHistory: ChatMessage[],
      editorSelection?: EditorSelectionPayload | null
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
        const response = await fetch(`/api/resume/documents/${threadId}/revision`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            selected_text: selectedText,
            user_message: userMessage,
            action: "custom",
            editor_selection: editorSelection,
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
          setSuggestion(suggestionFromRevision(data, selectedText, "custom"));
          return {
            suggestion: data.proposedText || data.suggestion,
            cacheHit: data.cache_hit || false,
            revisionId: data.revisionId,
            canApply: data.canApply,
            verification: data.verification,
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
    [suggestionFromRevision, threadId]
  );

  const applyRevision = useCallback(
    async (
      revisionId: string,
      overrideVerification = false
    ): Promise<ApplyRevisionResult | null> => {
      if (!threadId) {
        setError("No active workflow");
        return null;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/resume/documents/${threadId}/apply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            revision_id: revisionId,
            override_verification: overrideVerification,
          }),
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Failed to apply revision");
        }
        if (!data.success) {
          throw new Error(data.error || "Failed to apply revision");
        }
        return data;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [threadId]
  );

  // Sync editor state to backend before AI revisions or final apply.
  // Also tracks accepted suggestions for preference learning
  const syncEditor = useCallback(
    async (
      html: string,
      original?: string,
      suggestion?: string,
      userMessage?: string
    ): Promise<boolean> => {
      if (!threadId) return false;

      // Cancel any pending sync
      if (pendingSyncRef.current) {
        pendingSyncRef.current.abort();
      }

      const controller = new AbortController();
      pendingSyncRef.current = controller;

      try {
        const response = await fetch(`/api/optimize/${threadId}/editor/sync`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            html,
            original: original || "",
            suggestion: suggestion || "",
            user_message: userMessage || "",
          }),
          signal: controller.signal,
        });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || "Failed to sync editor content");
        }
        return true;
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") {
          return false;
        }
        setError(e instanceof Error ? e.message : "Failed to sync editor content");
        return false;
      } finally {
        if (pendingSyncRef.current === controller) {
          pendingSyncRef.current = null;
        }
      }
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
    applyRevision,
  };
}
