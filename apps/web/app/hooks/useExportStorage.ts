"use client";

import { useState, useCallback, useEffect } from "react";

const STORAGE_KEY = "resume_agent:export_session";

/**
 * Export step status.
 */
export type ExportStep =
  | "idle"
  | "optimizing"
  | "generating_pdf"
  | "generating_txt"
  | "generating_json"
  | "analyzing_ats"
  | "generating_linkedin"
  | "completed";

/**
 * ATS report from backend.
 */
export interface ATSReport {
  keyword_match_score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  formatting_issues: string[];
  recommendations: string[];
  analyzed_at: string;
}

/**
 * Experience bullets for LinkedIn.
 */
export interface ExperienceBullet {
  company: string;
  position: string;
  bullets: string[];
}

/**
 * LinkedIn suggestions from backend.
 */
export interface LinkedInSuggestion {
  headline: string;
  summary: string;
  experience_bullets: ExperienceBullet[];
  generated_at: string;
}

/**
 * Export session state.
 */
export interface ExportSession {
  threadId: string;
  currentStep: ExportStep;
  atsReport: ATSReport | null;
  linkedinSuggestions: LinkedInSuggestion | null;
  exportCompleted: boolean;
  startedAt: string;
  completedAt: string | null;
}

/**
 * All export sessions indexed by thread ID.
 */
interface ExportSessions {
  [threadId: string]: ExportSession;
}

/**
 * Hook for managing export stage localStorage persistence.
 *
 * Features:
 * - Persist export results to localStorage
 * - Track export progress
 * - Session recovery
 * - Cache ATS reports and LinkedIn suggestions
 */
export function useExportStorage() {
  const [session, setSession] = useState<ExportSession | null>(null);
  const [existingSession, setExistingSession] = useState<ExportSession | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);

  /**
   * Load sessions from localStorage.
   */
  const loadSessions = useCallback((): ExportSessions => {
    if (typeof window === "undefined") return {};
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : {};
    } catch {
      return {};
    }
  }, []);

  /**
   * Save sessions to localStorage.
   */
  const saveSessions = useCallback((sessions: ExportSessions) => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch (error) {
      console.error("Failed to save export sessions:", error);
    }
  }, []);

  /**
   * Check for existing session.
   */
  const checkExistingSession = useCallback(
    (threadId: string): ExportSession | null => {
      const sessions = loadSessions();
      const existing = sessions[threadId];
      if (existing) {
        setExistingSession(existing);
        return existing;
      }
      return null;
    },
    [loadSessions]
  );

  /**
   * Start a new export session.
   */
  const startSession = useCallback(
    (threadId: string) => {
      const newSession: ExportSession = {
        threadId,
        currentStep: "idle",
        atsReport: null,
        linkedinSuggestions: null,
        exportCompleted: false,
        startedAt: new Date().toISOString(),
        completedAt: null,
      };

      setSession(newSession);

      const sessions = loadSessions();
      sessions[threadId] = newSession;
      saveSessions(sessions);

      return newSession;
    },
    [loadSessions, saveSessions]
  );

  /**
   * Resume an existing session.
   */
  const resumeSession = useCallback(
    (existingSession: ExportSession) => {
      setSession(existingSession);
      setExistingSession(null);
    },
    []
  );

  /**
   * Update export step.
   */
  const updateStep = useCallback(
    (step: ExportStep) => {
      if (!session) return;

      const updatedSession: ExportSession = {
        ...session,
        currentStep: step,
      };

      setSession(updatedSession);

      const sessions = loadSessions();
      sessions[session.threadId] = updatedSession;
      saveSessions(sessions);
    },
    [session, loadSessions, saveSessions]
  );

  /**
   * Save ATS report.
   */
  const saveATSReport = useCallback(
    (report: ATSReport) => {
      if (!session) return;

      const updatedSession: ExportSession = {
        ...session,
        atsReport: report,
      };

      setSession(updatedSession);

      const sessions = loadSessions();
      sessions[session.threadId] = updatedSession;
      saveSessions(sessions);
    },
    [session, loadSessions, saveSessions]
  );

  /**
   * Save LinkedIn suggestions.
   */
  const saveLinkedInSuggestions = useCallback(
    (suggestions: LinkedInSuggestion) => {
      if (!session) return;

      const updatedSession: ExportSession = {
        ...session,
        linkedinSuggestions: suggestions,
      };

      setSession(updatedSession);

      const sessions = loadSessions();
      sessions[session.threadId] = updatedSession;
      saveSessions(sessions);
    },
    [session, loadSessions, saveSessions]
  );

  /**
   * Mark export as complete.
   */
  const completeExport = useCallback(() => {
    if (!session) return;

    const updatedSession: ExportSession = {
      ...session,
      currentStep: "completed",
      exportCompleted: true,
      completedAt: new Date().toISOString(),
    };

    setSession(updatedSession);

    const sessions = loadSessions();
    sessions[session.threadId] = updatedSession;
    saveSessions(sessions);
  }, [session, loadSessions, saveSessions]);

  /**
   * Sync from backend response.
   */
  const syncFromBackend = useCallback(
    (data: {
      export_step?: string;
      export_completed?: boolean;
      ats_report?: ATSReport;
      linkedin_suggestions?: LinkedInSuggestion;
    }) => {
      if (!session) return;

      const updatedSession: ExportSession = {
        ...session,
        currentStep: (data.export_step as ExportStep) || session.currentStep,
        exportCompleted: data.export_completed ?? session.exportCompleted,
        atsReport: data.ats_report || session.atsReport,
        linkedinSuggestions:
          data.linkedin_suggestions || session.linkedinSuggestions,
        completedAt: data.export_completed
          ? new Date().toISOString()
          : session.completedAt,
      };

      setSession(updatedSession);

      const sessions = loadSessions();
      sessions[session.threadId] = updatedSession;
      saveSessions(sessions);
    },
    [session, loadSessions, saveSessions]
  );

  /**
   * Clear session.
   */
  const clearSession = useCallback(
    (threadId: string) => {
      setSession(null);
      setExistingSession(null);

      const sessions = loadSessions();
      delete sessions[threadId];
      saveSessions(sessions);
    },
    [loadSessions, saveSessions]
  );

  /**
   * Check if ATS score is passing (>= 70%).
   */
  const isATSScorePassing = useCallback((): boolean => {
    if (!session?.atsReport) return false;
    return session.atsReport.keyword_match_score >= 70;
  }, [session]);

  /**
   * Get export progress percentage.
   */
  const getProgressPercentage = useCallback((): number => {
    if (!session) return 0;

    const steps: ExportStep[] = [
      "idle",
      "optimizing",
      "generating_pdf",
      "generating_txt",
      "generating_json",
      "analyzing_ats",
      "generating_linkedin",
      "completed",
    ];

    const currentIndex = steps.indexOf(session.currentStep);
    if (currentIndex === -1) return 0;

    return Math.round((currentIndex / (steps.length - 1)) * 100);
  }, [session]);

  return {
    session,
    existingSession,
    isLoading,
    checkExistingSession,
    startSession,
    resumeSession,
    updateStep,
    saveATSReport,
    saveLinkedInSuggestions,
    completeExport,
    syncFromBackend,
    clearSession,
    isATSScorePassing,
    getProgressPercentage,
  };
}
