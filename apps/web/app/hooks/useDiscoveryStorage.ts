"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * A message in the discovery conversation.
 */
export interface DiscoveryMessage {
  role: "agent" | "user";
  content: string;
  timestamp: string;
  promptId?: string;
  experiencesExtracted?: string[];
}

/**
 * A discovered experience from the conversation.
 */
export interface DiscoveredExperience {
  id: string;
  description: string;
  sourceQuote: string;
  mappedRequirements: string[];
  discoveredAt: string;
}

/**
 * A discovery prompt.
 */
export interface DiscoveryPrompt {
  id: string;
  question: string;
  intent: string;
  relatedGaps: string[];
  priority: number;
  asked: boolean;
}

/**
 * Discovery session data stored in localStorage.
 */
export interface DiscoverySession {
  // Backend workflow thread ID
  threadId: string;

  // Conversation data
  messages: DiscoveryMessage[];
  currentPromptIndex: number;

  // Discovered experiences
  discoveredExperiences: DiscoveredExperience[];

  // Discovery prompts from backend
  prompts: DiscoveryPrompt[];

  // State
  confirmed: boolean;
  exchanges: number;

  // Timestamps
  startedAt: string;
  updatedAt: string;

  // Error state
  lastError: string | null;
}

const STORAGE_KEY = "resume_agent:discovery_session";

/**
 * Hook for managing discovery session persistence in localStorage.
 *
 * Features:
 * - Saves conversation after each message
 * - Enables session recovery on page reload
 * - Provides "Continue conversation?" or "Start fresh?" options
 */
export function useDiscoveryStorage() {
  const [session, setSession] = useState<DiscoverySession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [existingSession, setExistingSession] =
    useState<DiscoverySession | null>(null);

  // Load session from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Record<string, DiscoverySession>;
        // Find the most recent session
        const sessions = Object.values(parsed);
        if (sessions.length > 0) {
          // Sort by updatedAt descending
          sessions.sort(
            (a, b) =>
              new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          );
          setSession(sessions[0]);
        }
      }
    } catch (error) {
      console.error("Failed to load discovery session:", error);
    }
    setIsLoading(false);
  }, []);

  /**
   * Check if there's an existing session for the given thread ID.
   */
  const checkExistingSession = useCallback(
    (threadId: string): DiscoverySession | null => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return null;

        const sessions = JSON.parse(stored) as Record<string, DiscoverySession>;
        const existing = sessions[threadId];

        if (existing && existing.messages.length > 0 && !existing.confirmed) {
          setExistingSession(existing);
          return existing;
        }
      } catch (error) {
        console.error("Failed to check existing session:", error);
      }
      return null;
    },
    []
  );

  /**
   * Start a new discovery session.
   */
  const startSession = useCallback(
    (threadId: string, prompts: DiscoveryPrompt[] = []): DiscoverySession => {
      const now = new Date().toISOString();
      const newSession: DiscoverySession = {
        threadId,
        messages: [],
        currentPromptIndex: 0,
        discoveredExperiences: [],
        prompts,
        confirmed: false,
        exchanges: 0,
        startedAt: now,
        updatedAt: now,
        lastError: null,
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, DiscoverySession> = stored
          ? JSON.parse(stored)
          : {};
        sessions[threadId] = newSession;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error("Failed to save session:", error);
      }

      setSession(newSession);
      setExistingSession(null);
      return newSession;
    },
    []
  );

  /**
   * Add a message to the conversation.
   */
  const addMessage = useCallback(
    (message: DiscoveryMessage) => {
      if (!session) return;

      const updatedSession: DiscoverySession = {
        ...session,
        messages: [...session.messages, message],
        exchanges:
          message.role === "user" ? session.exchanges + 1 : session.exchanges,
        updatedAt: new Date().toISOString(),
        lastError: null,
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, DiscoverySession> = stored
          ? JSON.parse(stored)
          : {};
        sessions[session.threadId] = updatedSession;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error("Failed to update session:", error);
      }

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Add a discovered experience.
   */
  const addExperience = useCallback(
    (experience: DiscoveredExperience) => {
      if (!session) return;

      const updatedSession: DiscoverySession = {
        ...session,
        discoveredExperiences: [...session.discoveredExperiences, experience],
        updatedAt: new Date().toISOString(),
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, DiscoverySession> = stored
          ? JSON.parse(stored)
          : {};
        sessions[session.threadId] = updatedSession;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error("Failed to update session:", error);
      }

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Update session from backend state.
   */
  const syncFromBackend = useCallback(
    (backendData: {
      discovery_messages?: Array<{
        role: string;
        content: string;
        timestamp: string;
        prompt_id?: string;
        experiences_extracted?: string[];
      }>;
      discovered_experiences?: Array<{
        id: string;
        description: string;
        source_quote: string;
        mapped_requirements: string[];
        discovered_at: string;
      }>;
      discovery_prompts?: Array<{
        id: string;
        question: string;
        intent: string;
        related_gaps: string[];
        priority: number;
        asked: boolean;
      }>;
      discovery_confirmed?: boolean;
      discovery_exchanges?: number;
    }) => {
      if (!session) return;

      const messages: DiscoveryMessage[] = (
        backendData.discovery_messages || []
      ).map((m) => ({
        role: m.role as "agent" | "user",
        content: m.content,
        timestamp: m.timestamp,
        promptId: m.prompt_id,
        experiencesExtracted: m.experiences_extracted,
      }));

      const experiences: DiscoveredExperience[] = (
        backendData.discovered_experiences || []
      ).map((e) => ({
        id: e.id,
        description: e.description,
        sourceQuote: e.source_quote,
        mappedRequirements: e.mapped_requirements,
        discoveredAt: e.discovered_at,
      }));

      const prompts: DiscoveryPrompt[] = (
        backendData.discovery_prompts || []
      ).map((p) => ({
        id: p.id,
        question: p.question,
        intent: p.intent,
        relatedGaps: p.related_gaps,
        priority: p.priority,
        asked: p.asked,
      }));

      const updatedSession: DiscoverySession = {
        ...session,
        messages,
        discoveredExperiences: experiences,
        prompts,
        confirmed: backendData.discovery_confirmed || false,
        exchanges: backendData.discovery_exchanges || 0,
        updatedAt: new Date().toISOString(),
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, DiscoverySession> = stored
          ? JSON.parse(stored)
          : {};
        sessions[session.threadId] = updatedSession;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error("Failed to sync session:", error);
      }

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Mark discovery as confirmed.
   */
  const confirmDiscovery = useCallback(() => {
    if (!session) return;

    const updatedSession: DiscoverySession = {
      ...session,
      confirmed: true,
      updatedAt: new Date().toISOString(),
    };

    // Save to localStorage
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      const sessions: Record<string, DiscoverySession> = stored
        ? JSON.parse(stored)
        : {};
      sessions[session.threadId] = updatedSession;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch (error) {
      console.error("Failed to confirm session:", error);
    }

    setSession(updatedSession);
  }, [session]);

  /**
   * Record an error.
   */
  const recordError = useCallback(
    (error: string) => {
      if (!session) return;

      const updatedSession: DiscoverySession = {
        ...session,
        lastError: error,
        updatedAt: new Date().toISOString(),
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, DiscoverySession> = stored
          ? JSON.parse(stored)
          : {};
        sessions[session.threadId] = updatedSession;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error("Failed to record error:", error);
      }

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Resume from an existing session.
   */
  const resumeSession = useCallback((existingSession: DiscoverySession) => {
    setSession(existingSession);
    setExistingSession(null);
  }, []);

  /**
   * Clear existing session and start fresh.
   */
  const clearSession = useCallback((threadId: string) => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const sessions = JSON.parse(stored) as Record<string, DiscoverySession>;
        delete sessions[threadId];
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      }
    } catch (error) {
      console.error("Failed to clear session:", error);
    }
    setSession(null);
    setExistingSession(null);
  }, []);

  /**
   * Check if minimum exchanges for confirmation met.
   */
  const canConfirm = useCallback(() => {
    if (!session) return false;
    return session.exchanges >= 3;
  }, [session]);

  return {
    session,
    existingSession,
    isLoading,
    checkExistingSession,
    startSession,
    addMessage,
    addExperience,
    syncFromBackend,
    confirmDiscovery,
    recordError,
    resumeSession,
    clearSession,
    canConfirm,
  };
}
