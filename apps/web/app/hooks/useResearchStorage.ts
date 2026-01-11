"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * Research session data stored in localStorage.
 * Enables resuming from where user left off.
 */
export interface ResearchSession {
  // Input URLs
  linkedinUrl: string;
  jobUrl: string;

  // Backend workflow thread ID
  threadId: string;

  // Progress tracking (7 sub-tasks)
  completedSteps: ResearchStep[];
  currentStep: ResearchStep | null;

  // Cached data for each step
  data: {
    userProfile: Record<string, unknown> | null;
    jobPosting: Record<string, unknown> | null;
    companyResearch: Record<string, unknown> | null;
    similarHires: Record<string, unknown>[] | null;
    exEmployees: Record<string, unknown>[] | null;
    hiringCriteria: Record<string, unknown> | null;
    idealProfile: Record<string, unknown> | null;
  };

  // Timestamps
  startedAt: string;
  updatedAt: string;

  // Error state
  lastError: string | null;
}

/**
 * Research sub-tasks that map to the 7 research steps.
 */
export type ResearchStep =
  | "profile_fetch"
  | "job_fetch"
  | "company_research"
  | "similar_hires"
  | "ex_employees"
  | "hiring_criteria"
  | "ideal_profile";

const STORAGE_KEY = "resume_agent:research_session";

const STEP_ORDER: ResearchStep[] = [
  "profile_fetch",
  "job_fetch",
  "company_research",
  "similar_hires",
  "ex_employees",
  "hiring_criteria",
  "ideal_profile",
];

/**
 * Create a session key from LinkedIn and job URLs.
 * Used to identify unique sessions for resumption.
 */
function createSessionKey(linkedinUrl: string, jobUrl: string): string {
  return `${linkedinUrl}||${jobUrl}`;
}

/**
 * Hook for managing research session persistence in localStorage.
 *
 * Features:
 * - Saves progress after each sub-task
 * - Enables session recovery on page reload
 * - Provides "Resume from step X" or "Start fresh" options
 */
export function useResearchStorage() {
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [existingSession, setExistingSession] = useState<ResearchSession | null>(null);

  // Load session from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Record<string, ResearchSession>;
        // Find the most recent session
        const sessions = Object.values(parsed);
        if (sessions.length > 0) {
          // Sort by updatedAt descending
          sessions.sort((a, b) =>
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          );
          setSession(sessions[0]);
        }
      }
    } catch (error) {
      console.error("Failed to load research session:", error);
    }
    setIsLoading(false);
  }, []);

  /**
   * Check if there's an existing session for the given URLs.
   */
  const checkExistingSession = useCallback(
    (linkedinUrl: string, jobUrl: string): ResearchSession | null => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return null;

        const sessions = JSON.parse(stored) as Record<string, ResearchSession>;
        const key = createSessionKey(linkedinUrl, jobUrl);
        const existing = sessions[key];

        if (existing && existing.completedSteps.length > 0) {
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
   * Start a new research session.
   */
  const startSession = useCallback(
    (linkedinUrl: string, jobUrl: string, threadId: string): ResearchSession => {
      const now = new Date().toISOString();
      const newSession: ResearchSession = {
        linkedinUrl,
        jobUrl,
        threadId,
        completedSteps: [],
        currentStep: "profile_fetch",
        data: {
          userProfile: null,
          jobPosting: null,
          companyResearch: null,
          similarHires: null,
          exEmployees: null,
          hiringCriteria: null,
          idealProfile: null,
        },
        startedAt: now,
        updatedAt: now,
        lastError: null,
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, ResearchSession> = stored
          ? JSON.parse(stored)
          : {};
        const key = createSessionKey(linkedinUrl, jobUrl);
        sessions[key] = newSession;
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
   * Update session with completed step and data.
   */
  const completeStep = useCallback(
    (step: ResearchStep, data: Record<string, unknown>) => {
      if (!session) return;

      const updatedSession: ResearchSession = {
        ...session,
        completedSteps: [...session.completedSteps, step],
        currentStep: getNextStep(step),
        updatedAt: new Date().toISOString(),
        data: {
          ...session.data,
          [stepToDataKey(step)]: data,
        },
        lastError: null,
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, ResearchSession> = stored
          ? JSON.parse(stored)
          : {};
        const key = createSessionKey(session.linkedinUrl, session.jobUrl);
        sessions[key] = updatedSession;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error("Failed to update session:", error);
      }

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Mark current step as in-progress.
   */
  const setCurrentStep = useCallback(
    (step: ResearchStep) => {
      if (!session) return;

      const updatedSession: ResearchSession = {
        ...session,
        currentStep: step,
        updatedAt: new Date().toISOString(),
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, ResearchSession> = stored
          ? JSON.parse(stored)
          : {};
        const key = createSessionKey(session.linkedinUrl, session.jobUrl);
        sessions[key] = updatedSession;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
      } catch (error) {
        console.error("Failed to update current step:", error);
      }

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Record an error for the current step.
   */
  const recordError = useCallback(
    (error: string) => {
      if (!session) return;

      const updatedSession: ResearchSession = {
        ...session,
        lastError: error,
        updatedAt: new Date().toISOString(),
      };

      // Save to localStorage
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        const sessions: Record<string, ResearchSession> = stored
          ? JSON.parse(stored)
          : {};
        const key = createSessionKey(session.linkedinUrl, session.jobUrl);
        sessions[key] = updatedSession;
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
  const resumeSession = useCallback(
    (existingSession: ResearchSession) => {
      setSession(existingSession);
      setExistingSession(null);
    },
    []
  );

  /**
   * Clear existing session and start fresh.
   */
  const clearSession = useCallback(
    (linkedinUrl: string, jobUrl: string) => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const sessions = JSON.parse(stored) as Record<string, ResearchSession>;
          const key = createSessionKey(linkedinUrl, jobUrl);
          delete sessions[key];
          localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
        }
      } catch (error) {
        console.error("Failed to clear session:", error);
      }
      setSession(null);
      setExistingSession(null);
    },
    []
  );

  /**
   * Get progress percentage (0-100).
   */
  const getProgress = useCallback(() => {
    if (!session) return 0;
    return Math.round((session.completedSteps.length / STEP_ORDER.length) * 100);
  }, [session]);

  /**
   * Check if all steps are complete.
   */
  const isComplete = useCallback(() => {
    if (!session) return false;
    return session.completedSteps.length === STEP_ORDER.length;
  }, [session]);

  return {
    session,
    existingSession,
    isLoading,
    checkExistingSession,
    startSession,
    completeStep,
    setCurrentStep,
    recordError,
    resumeSession,
    clearSession,
    getProgress,
    isComplete,
    stepOrder: STEP_ORDER,
  };
}

// Helper functions

function getNextStep(currentStep: ResearchStep): ResearchStep | null {
  const idx = STEP_ORDER.indexOf(currentStep);
  if (idx === -1 || idx >= STEP_ORDER.length - 1) return null;
  return STEP_ORDER[idx + 1];
}

function stepToDataKey(step: ResearchStep): keyof ResearchSession["data"] {
  const mapping: Record<ResearchStep, keyof ResearchSession["data"]> = {
    profile_fetch: "userProfile",
    job_fetch: "jobPosting",
    company_research: "companyResearch",
    similar_hires: "similarHires",
    ex_employees: "exEmployees",
    hiring_criteria: "hiringCriteria",
    ideal_profile: "idealProfile",
  };
  return mapping[step];
}

/**
 * Human-readable step labels for UI.
 */
export function getStepLabel(step: ResearchStep): string {
  const labels: Record<ResearchStep, string> = {
    profile_fetch: "Fetching profile",
    job_fetch: "Fetching job listing",
    company_research: "Researching company",
    similar_hires: "Finding similar hires",
    ex_employees: "Finding ex-employees",
    hiring_criteria: "Extracting hiring criteria",
    ideal_profile: "Generating ideal profile",
  };
  return labels[step];
}
