"use client";

import { useState, useEffect, useCallback, useRef } from "react";

/**
 * Suggestion status.
 */
export type SuggestionStatus = "pending" | "accepted" | "declined";

/**
 * Version trigger type.
 */
export type VersionTrigger =
  | "initial"
  | "accept"
  | "decline"
  | "edit"
  | "manual_save"
  | "auto_checkpoint"
  | "restore";

/**
 * A suggestion for improving the resume draft.
 */
export interface DraftingSuggestion {
  id: string;
  location: string;
  originalText: string;
  proposedText: string;
  rationale: string;
  status: SuggestionStatus;
  createdAt: string;
  resolvedAt?: string;
}

/**
 * A change log entry.
 */
export interface ChangeLogEntry {
  id: string;
  location: string;
  changeType: string;
  originalText?: string;
  newText?: string;
  suggestionId?: string;
  timestamp: string;
}

/**
 * A version snapshot.
 */
export interface DraftVersion {
  version: string;
  htmlContent: string;
  trigger: VersionTrigger;
  description: string;
  changeLog: ChangeLogEntry[];
  createdAt: string;
}

/**
 * Validation result for the draft.
 */
export interface DraftValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  checks: Record<string, boolean>;
}

/**
 * Drafting session data stored in localStorage.
 */
export interface DraftingSession {
  threadId: string;
  resumeHtml: string;
  suggestions: DraftingSuggestion[];
  versions: DraftVersion[];
  currentVersion: string;
  changeLog: ChangeLogEntry[];
  approved: boolean;
  startedAt: string;
  updatedAt: string;
  lastAutoCheckpoint?: string;
}

const STORAGE_KEY = "resume_agent:drafting_session";
const AUTO_CHECKPOINT_INTERVAL = 5 * 60 * 1000; // 5 minutes
const MAX_VERSIONS = 5;

/**
 * Helper to save a session to localStorage.
 */
function saveSessionToStorage(
  threadId: string,
  session: DraftingSession
): void {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    const sessions: Record<string, DraftingSession> = stored
      ? JSON.parse(stored)
      : {};
    sessions[threadId] = session;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch (error) {
    console.error("Failed to save session:", error);
  }
}

/**
 * Helper to get all sessions from localStorage.
 */
function getSessionsFromStorage(): Record<string, DraftingSession> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch (error) {
    console.error("Failed to read sessions:", error);
    return {};
  }
}

/**
 * Hook for managing drafting session persistence in localStorage.
 *
 * Features:
 * - Saves draft after each change
 * - Version control (max 5 versions)
 * - Auto-checkpoint every 5 minutes
 * - Session recovery on page reload
 */
export function useDraftingStorage() {
  const [session, setSession] = useState<DraftingSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [existingSession, setExistingSession] =
    useState<DraftingSession | null>(null);
  const autoCheckpointRef = useRef<NodeJS.Timeout | null>(null);

  // Load session from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Record<string, DraftingSession>;
        // Find the most recent session
        const sessions = Object.values(parsed);
        if (sessions.length > 0) {
          sessions.sort(
            (a, b) =>
              new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          );
          setSession(sessions[0]);
        }
      }
    } catch (error) {
      console.error("Failed to load drafting session:", error);
    }
    setIsLoading(false);
  }, []);

  // Auto-checkpoint timer
  useEffect(() => {
    if (!session || session.approved) return;

    const startAutoCheckpoint = () => {
      autoCheckpointRef.current = setInterval(() => {
        const now = new Date();
        const lastCheckpoint = session.lastAutoCheckpoint
          ? new Date(session.lastAutoCheckpoint)
          : new Date(session.startedAt);

        if (now.getTime() - lastCheckpoint.getTime() >= AUTO_CHECKPOINT_INTERVAL) {
          // Create auto-checkpoint
          createVersion("auto_checkpoint", "Auto-checkpoint");
        }
      }, 60000); // Check every minute
    };

    startAutoCheckpoint();

    return () => {
      if (autoCheckpointRef.current) {
        clearInterval(autoCheckpointRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  /**
   * Check if there's an existing session for the given thread ID.
   */
  const checkExistingSession = useCallback(
    (threadId: string): DraftingSession | null => {
      const sessions = getSessionsFromStorage();
      const existing = sessions[threadId];

      if (existing && !existing.approved) {
        setExistingSession(existing);
        return existing;
      }
      return null;
    },
    []
  );

  /**
   * Start a new drafting session.
   */
  const startSession = useCallback(
    (
      threadId: string,
      initialHtml: string,
      initialSuggestions: DraftingSuggestion[] = []
    ): DraftingSession => {
      const now = new Date().toISOString();

      const initialVersion: DraftVersion = {
        version: "1.0",
        htmlContent: initialHtml,
        trigger: "initial",
        description: "Initial draft",
        changeLog: [],
        createdAt: now,
      };

      const newSession: DraftingSession = {
        threadId,
        resumeHtml: initialHtml,
        suggestions: initialSuggestions,
        versions: [initialVersion],
        currentVersion: "1.0",
        changeLog: [],
        approved: false,
        startedAt: now,
        updatedAt: now,
      };

      saveSessionToStorage(threadId, newSession);
      setSession(newSession);
      setExistingSession(null);
      return newSession;
    },
    []
  );

  /**
   * Increment version number.
   */
  const incrementVersion = useCallback((currentVersion: string): string => {
    try {
      const [major, minor] = currentVersion.split(".").map(Number);
      const newMinor = minor + 1;
      if (newMinor >= 10) {
        return `${major + 1}.0`;
      }
      return `${major}.${newMinor}`;
    } catch {
      return "1.1";
    }
  }, []);

  /**
   * Create a new version.
   */
  const createVersion = useCallback(
    (trigger: VersionTrigger, description: string, changeEntry?: ChangeLogEntry) => {
      // Use functional update to get latest session state
      let newVersionNumber = "";

      setSession((currentSession) => {
        if (!currentSession) return null;

        newVersionNumber = incrementVersion(currentSession.currentVersion);

        const newVersion: DraftVersion = {
          version: newVersionNumber,
          htmlContent: currentSession.resumeHtml,
          trigger,
          description,
          changeLog: changeEntry ? [changeEntry] : [],
          createdAt: new Date().toISOString(),
        };

        let versions = [...currentSession.versions, newVersion];

        // Keep only last MAX_VERSIONS
        if (versions.length > MAX_VERSIONS) {
          versions = versions.slice(-MAX_VERSIONS);
        }

        const updatedSession: DraftingSession = {
          ...currentSession,
          versions,
          currentVersion: newVersionNumber,
          updatedAt: new Date().toISOString(),
          lastAutoCheckpoint:
            trigger === "auto_checkpoint"
              ? new Date().toISOString()
              : currentSession.lastAutoCheckpoint,
        };

        saveSessionToStorage(currentSession.threadId, updatedSession);
        return updatedSession;
      });

      return newVersionNumber;
    },
    [incrementVersion]
  );

  /**
   * Update resume HTML.
   */
  const updateResumeHtml = useCallback(
    (html: string) => {
      if (!session) return;

      const updatedSession: DraftingSession = {
        ...session,
        resumeHtml: html,
        updatedAt: new Date().toISOString(),
      };

      saveSessionToStorage(session.threadId, updatedSession);
      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Accept a suggestion.
   */
  const acceptSuggestion = useCallback(
    (suggestionId: string) => {
      if (!session) return;

      const suggestion = session.suggestions.find((s) => s.id === suggestionId);
      if (!suggestion || suggestion.status !== "pending") return;

      // Apply the change
      const newHtml = session.resumeHtml.replace(
        suggestion.originalText,
        suggestion.proposedText
      );

      // Update suggestion status
      const updatedSuggestions = session.suggestions.map((s) =>
        s.id === suggestionId
          ? { ...s, status: "accepted" as SuggestionStatus, resolvedAt: new Date().toISOString() }
          : s
      );

      // Create change log entry
      const changeEntry: ChangeLogEntry = {
        id: `chg_${Date.now().toString(36)}`,
        location: suggestion.location,
        changeType: "accept",
        originalText: suggestion.originalText,
        newText: suggestion.proposedText,
        suggestionId,
        timestamp: new Date().toISOString(),
      };

      const updatedSession: DraftingSession = {
        ...session,
        resumeHtml: newHtml,
        suggestions: updatedSuggestions,
        changeLog: [...session.changeLog, changeEntry],
        updatedAt: new Date().toISOString(),
      };

      saveSessionToStorage(session.threadId, updatedSession);
      setSession(updatedSession);

      // Create new version
      setTimeout(() => {
        createVersion(
          "accept",
          `Accepted suggestion: ${suggestion.rationale.substring(0, 50)}...`,
          changeEntry
        );
      }, 0);
    },
    [session, createVersion]
  );

  /**
   * Decline a suggestion.
   */
  const declineSuggestion = useCallback(
    (suggestionId: string) => {
      if (!session) return;

      const suggestion = session.suggestions.find((s) => s.id === suggestionId);
      if (!suggestion || suggestion.status !== "pending") return;

      // Update suggestion status
      const updatedSuggestions = session.suggestions.map((s) =>
        s.id === suggestionId
          ? { ...s, status: "declined" as SuggestionStatus, resolvedAt: new Date().toISOString() }
          : s
      );

      // Create change log entry
      const changeEntry: ChangeLogEntry = {
        id: `chg_${Date.now().toString(36)}`,
        location: suggestion.location,
        changeType: "decline",
        originalText: suggestion.originalText,
        suggestionId,
        timestamp: new Date().toISOString(),
      };

      const updatedSession: DraftingSession = {
        ...session,
        suggestions: updatedSuggestions,
        changeLog: [...session.changeLog, changeEntry],
        updatedAt: new Date().toISOString(),
      };

      saveSessionToStorage(session.threadId, updatedSession);
      setSession(updatedSession);

      // Create new version
      setTimeout(() => {
        createVersion(
          "decline",
          `Declined suggestion: ${suggestion.rationale.substring(0, 50)}...`,
          changeEntry
        );
      }, 0);
    },
    [session, createVersion]
  );

  /**
   * Record a direct edit.
   */
  const recordEdit = useCallback(
    (location: string, originalText: string, newText: string) => {
      if (!session) return;

      const changeEntry: ChangeLogEntry = {
        id: `chg_${Date.now().toString(36)}`,
        location,
        changeType: "edit",
        originalText,
        newText,
        timestamp: new Date().toISOString(),
      };

      const updatedSession: DraftingSession = {
        ...session,
        changeLog: [...session.changeLog, changeEntry],
        updatedAt: new Date().toISOString(),
      };

      saveSessionToStorage(session.threadId, updatedSession);
      setSession(updatedSession);

      // Create new version
      createVersion("edit", `Manual edit at ${location}`, changeEntry);
    },
    [session, createVersion]
  );

  /**
   * Manual save.
   */
  const manualSave = useCallback(() => {
    if (!session) return null;

    const newVersion = createVersion("manual_save", "Manual save");
    return newVersion;
  }, [session, createVersion]);

  /**
   * Restore a previous version.
   */
  const restoreVersion = useCallback(
    (versionNumber: string) => {
      if (!session) return;

      const targetVersion = session.versions.find(
        (v) => v.version === versionNumber
      );
      if (!targetVersion) return;

      const updatedSession: DraftingSession = {
        ...session,
        resumeHtml: targetVersion.htmlContent,
        updatedAt: new Date().toISOString(),
      };

      saveSessionToStorage(session.threadId, updatedSession);
      setSession(updatedSession);

      // Create new version as restore point
      createVersion("restore", `Restored from v${versionNumber}`);
    },
    [session, createVersion]
  );

  /**
   * Approve the draft.
   */
  const approveDraft = useCallback(() => {
    if (!session) return;

    const updatedSession: DraftingSession = {
      ...session,
      approved: true,
      updatedAt: new Date().toISOString(),
    };

    saveSessionToStorage(session.threadId, updatedSession);
    setSession(updatedSession);
  }, [session]);

  /**
   * Resume from an existing session.
   */
  const resumeSession = useCallback((existingSession: DraftingSession) => {
    setSession(existingSession);
    setExistingSession(null);
  }, []);

  /**
   * Clear existing session and start fresh.
   */
  const clearSession = useCallback((threadId: string) => {
    const sessions = getSessionsFromStorage();
    delete sessions[threadId];
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch (error) {
      console.error("Failed to clear session:", error);
    }
    setSession(null);
    setExistingSession(null);
  }, []);

  /**
   * Sync from backend state.
   */
  const syncFromBackend = useCallback(
    (backendData: {
      resume_html?: string;
      draft_suggestions?: Array<{
        id: string;
        location: string;
        original_text: string;
        proposed_text: string;
        rationale: string;
        status: string;
        created_at: string;
        resolved_at?: string;
      }>;
      draft_versions?: Array<{
        version: string;
        html_content: string;
        trigger: string;
        description: string;
        change_log?: Array<{
          id: string;
          location: string;
          change_type: string;
          original_text?: string;
          new_text?: string;
          suggestion_id?: string;
          timestamp: string;
        }>;
        created_at: string;
      }>;
      draft_current_version?: string;
      draft_approved?: boolean;
    }) => {
      if (!session) return;

      const suggestions: DraftingSuggestion[] = (
        backendData.draft_suggestions || []
      ).map((s) => ({
        id: s.id,
        location: s.location,
        originalText: s.original_text,
        proposedText: s.proposed_text,
        rationale: s.rationale,
        status: s.status as SuggestionStatus,
        createdAt: s.created_at,
        resolvedAt: s.resolved_at,
      }));

      const versions: DraftVersion[] = (backendData.draft_versions || []).map(
        (v) => ({
          version: v.version,
          htmlContent: v.html_content,
          trigger: v.trigger as VersionTrigger,
          description: v.description,
          changeLog: (v.change_log || []).map((c) => ({
            id: c.id,
            location: c.location,
            changeType: c.change_type,
            originalText: c.original_text,
            newText: c.new_text,
            suggestionId: c.suggestion_id,
            timestamp: c.timestamp,
          })),
          createdAt: v.created_at,
        })
      );

      const updatedSession: DraftingSession = {
        ...session,
        resumeHtml: backendData.resume_html || session.resumeHtml,
        suggestions,
        versions: versions.length > 0 ? versions : session.versions,
        currentVersion:
          backendData.draft_current_version || session.currentVersion,
        approved: backendData.draft_approved || false,
        updatedAt: new Date().toISOString(),
      };

      saveSessionToStorage(session.threadId, updatedSession);
      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Check if all suggestions are resolved.
   */
  const allSuggestionsResolved = useCallback(() => {
    if (!session) return true;
    return session.suggestions.every((s) => s.status !== "pending");
  }, [session]);

  /**
   * Get pending suggestions count.
   */
  const pendingSuggestionsCount = useCallback(() => {
    if (!session) return 0;
    return session.suggestions.filter((s) => s.status === "pending").length;
  }, [session]);

  return {
    session,
    existingSession,
    isLoading,
    checkExistingSession,
    startSession,
    updateResumeHtml,
    acceptSuggestion,
    declineSuggestion,
    recordEdit,
    manualSave,
    restoreVersion,
    approveDraft,
    resumeSession,
    clearSession,
    syncFromBackend,
    allSuggestionsResolved,
    pendingSuggestionsCount,
  };
}
