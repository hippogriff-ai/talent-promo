"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * Workflow stages as per Step 5 orchestration spec.
 * These are the 4 high-level stages, not the granular internal steps.
 */
export type WorkflowStage = "research" | "discovery" | "drafting" | "export";

export type StageStatus = "locked" | "active" | "completed" | "error";

/**
 * Unified session state across all 4 stages.
 */
export interface WorkflowSession {
  // Session identification
  sessionId: string;
  linkedinUrl: string;
  jobUrl: string;
  threadId: string;

  // Stage progress
  stages: Record<WorkflowStage, StageStatus>;
  currentStage: WorkflowStage;

  // Confirmation flags (required for transitions)
  researchComplete: boolean;
  discoveryConfirmed: boolean;
  draftApproved: boolean;
  exportComplete: boolean;

  // Error state
  lastError: string | null;
  errorStage: WorkflowStage | null;

  // Timestamps
  startedAt: string;
  updatedAt: string;
}

const STORAGE_KEY = "resume_agent:workflow_session";

// Stage order for navigation guards
const STAGE_ORDER: WorkflowStage[] = ["research", "discovery", "drafting", "export"];

/**
 * Create a session ID from LinkedIn and job URLs.
 */
function createSessionId(linkedinUrl: string, jobUrl: string): string {
  return `${linkedinUrl}||${jobUrl}`;
}

/**
 * Get initial stages state - only research is active, others locked.
 */
function getInitialStages(): Record<WorkflowStage, StageStatus> {
  return {
    research: "active",
    discovery: "locked",
    drafting: "locked",
    export: "locked",
  };
}

/**
 * Hook for managing unified workflow session across all stages.
 *
 * Features:
 * - Stage-based navigation (4 stages: Research → Discovery → Drafting → Export)
 * - Guards prevent access to future stages
 * - Session persistence in localStorage
 * - Automatic stage transitions based on completion flags
 * - Error recovery with preserved completed stages
 */
export function useWorkflowSession() {
  const [session, setSession] = useState<WorkflowSession | null>(null);
  const [existingSession, setExistingSession] = useState<WorkflowSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load session from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as WorkflowSession;
        // Check if session is still valid (has threadId)
        if (parsed.threadId) {
          setExistingSession(parsed);
        }
      }
    } catch (error) {
      console.error("Failed to load workflow session:", error);
    }
    setIsLoading(false);
  }, []);

  // Persist session whenever it changes
  useEffect(() => {
    if (session) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
      } catch (error) {
        console.error("Failed to save workflow session:", error);
      }
    }
  }, [session]);

  /**
   * Check if there's an existing session for given URLs.
   */
  const checkExistingSession = useCallback(
    (linkedinUrl: string, jobUrl: string): WorkflowSession | null => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return null;

        const parsed = JSON.parse(stored) as WorkflowSession;
        const expectedId = createSessionId(linkedinUrl, jobUrl);

        if (parsed.sessionId === expectedId && parsed.threadId) {
          setExistingSession(parsed);
          return parsed;
        }
      } catch (error) {
        console.error("Failed to check existing session:", error);
      }
      return null;
    },
    []
  );

  /**
   * Start a new workflow session.
   */
  const startSession = useCallback(
    (linkedinUrl: string, jobUrl: string, threadId: string): WorkflowSession => {
      const now = new Date().toISOString();
      const newSession: WorkflowSession = {
        sessionId: createSessionId(linkedinUrl, jobUrl),
        linkedinUrl,
        jobUrl,
        threadId,
        stages: getInitialStages(),
        currentStage: "research",
        researchComplete: false,
        discoveryConfirmed: false,
        draftApproved: false,
        exportComplete: false,
        lastError: null,
        errorStage: null,
        startedAt: now,
        updatedAt: now,
      };

      localStorage.setItem(STORAGE_KEY, JSON.stringify(newSession));
      setSession(newSession);
      setExistingSession(null);
      return newSession;
    },
    []
  );

  /**
   * Resume from existing session.
   */
  const resumeSession = useCallback(() => {
    if (existingSession) {
      setSession(existingSession);
      setExistingSession(null);
    }
  }, [existingSession]);

  /**
   * Get flag updates for a stage completion.
   */
  function getCompletionFlagForStage(stage: WorkflowStage): keyof WorkflowSession {
    const flagMap: Record<WorkflowStage, keyof WorkflowSession> = {
      research: "researchComplete",
      discovery: "discoveryConfirmed",
      drafting: "draftApproved",
      export: "exportComplete",
    };
    return flagMap[stage];
  }

  /**
   * Mark a stage as completed and unlock next stage.
   */
  const completeStage = useCallback(
    (stage: WorkflowStage) => {
      if (!session) return;

      const stageIdx = STAGE_ORDER.indexOf(stage);
      const nextStage = stageIdx < STAGE_ORDER.length - 1 ? STAGE_ORDER[stageIdx + 1] : null;

      const updatedStages = { ...session.stages };
      updatedStages[stage] = "completed";

      if (nextStage) {
        updatedStages[nextStage] = "active";
      }

      const updatedSession: WorkflowSession = {
        ...session,
        [getCompletionFlagForStage(stage)]: true,
        stages: updatedStages,
        currentStage: nextStage || stage,
        updatedAt: new Date().toISOString(),
        lastError: null,
        errorStage: null,
      };

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Set current active stage (for manual navigation within allowed stages).
   */
  const setActiveStage = useCallback(
    (stage: WorkflowStage): boolean => {
      if (!session) return false;

      // Only allow navigation to completed or active stages
      const status = session.stages[stage];
      if (status === "locked") {
        return false;
      }

      const updatedSession: WorkflowSession = {
        ...session,
        currentStage: stage,
        updatedAt: new Date().toISOString(),
      };

      setSession(updatedSession);
      return true;
    },
    [session]
  );

  /**
   * Get the earliest incomplete stage for redirection.
   */
  const getEarliestIncompleteStage = useCallback((): WorkflowStage => {
    if (!session) return "research";

    for (const stage of STAGE_ORDER) {
      if (session.stages[stage] !== "completed") {
        return stage;
      }
    }
    return "export";
  }, [session]);

  /**
   * Check if a stage can be accessed (not locked).
   */
  const canAccessStage = useCallback(
    (stage: WorkflowStage): boolean => {
      if (!session) return stage === "research";
      return session.stages[stage] !== "locked";
    },
    [session]
  );

  /**
   * Record an error for recovery.
   */
  const recordError = useCallback(
    (error: string, stage?: WorkflowStage) => {
      if (!session) return;

      const errorStage = stage || session.currentStage;
      const updatedStages = { ...session.stages };
      updatedStages[errorStage] = "error";

      const updatedSession: WorkflowSession = {
        ...session,
        stages: updatedStages,
        lastError: error,
        errorStage,
        updatedAt: new Date().toISOString(),
      };

      setSession(updatedSession);
    },
    [session]
  );

  /**
   * Retry from error state - reset error stage to active.
   */
  const retryFromError = useCallback(() => {
    if (!session || !session.errorStage) return;

    const updatedStages = { ...session.stages };
    updatedStages[session.errorStage] = "active";

    const updatedSession: WorkflowSession = {
      ...session,
      stages: updatedStages,
      currentStage: session.errorStage,
      lastError: null,
      errorStage: null,
      updatedAt: new Date().toISOString(),
    };

    setSession(updatedSession);
  }, [session]);

  /**
   * Start fresh - clear completed stages and restart from error stage.
   * Preserves stages completed before the error.
   */
  const startFreshFromError = useCallback(() => {
    if (!session) return;

    // Reset current and future stages
    const errorIdx = session.errorStage
      ? STAGE_ORDER.indexOf(session.errorStage)
      : STAGE_ORDER.indexOf(session.currentStage);

    const updatedStages = { ...session.stages };
    for (let i = errorIdx; i < STAGE_ORDER.length; i++) {
      updatedStages[STAGE_ORDER[i]] = i === errorIdx ? "active" : "locked";
    }

    // Reset confirmation flags for affected stages
    const flagUpdates: Partial<WorkflowSession> = {};
    if (errorIdx <= 0) flagUpdates.researchComplete = false;
    if (errorIdx <= 1) flagUpdates.discoveryConfirmed = false;
    if (errorIdx <= 2) flagUpdates.draftApproved = false;
    if (errorIdx <= 3) flagUpdates.exportComplete = false;

    const updatedSession: WorkflowSession = {
      ...session,
      ...flagUpdates,
      stages: updatedStages,
      currentStage: STAGE_ORDER[errorIdx],
      lastError: null,
      errorStage: null,
      updatedAt: new Date().toISOString(),
    };

    setSession(updatedSession);
  }, [session]);

  /**
   * Clear all session data and start completely fresh.
   */
  const clearAllSessions = useCallback(() => {
    // Clear unified session
    localStorage.removeItem(STORAGE_KEY);

    // Clear individual stage storage
    localStorage.removeItem("resume_agent:research_session");
    localStorage.removeItem("resume_agent:discovery_session");
    localStorage.removeItem("resume_agent:drafting_session");
    localStorage.removeItem("resume_agent:export_session");

    setSession(null);
    setExistingSession(null);
  }, []);

  /**
   * Prompt user before starting a new session (when existing session exists).
   */
  const hasExistingSession = useCallback(
    (linkedinUrl: string, jobUrl: string): boolean => {
      const existing = checkExistingSession(linkedinUrl, jobUrl);
      return existing !== null && existing.researchComplete;
    },
    [checkExistingSession]
  );

  /**
   * Check if workflow is fully complete.
   */
  const isWorkflowComplete = useCallback((): boolean => {
    if (!session) return false;
    return session.exportComplete;
  }, [session]);

  /**
   * Get completion percentage (0-100).
   */
  const getCompletionPercentage = useCallback((): number => {
    if (!session) return 0;

    let completed = 0;
    if (session.researchComplete) completed++;
    if (session.discoveryConfirmed) completed++;
    if (session.draftApproved) completed++;
    if (session.exportComplete) completed++;

    return Math.round((completed / 4) * 100);
  }, [session]);

  /**
   * Sync session state from backend status.
   */
  const syncFromBackend = useCallback(
    (backendData: {
      current_step?: string;
      discovery_confirmed?: boolean;
      draft_approved?: boolean;
      export_complete?: boolean;
      research_complete?: boolean;
    }) => {
      if (!session) return;

      const updates: Partial<WorkflowSession> = {
        updatedAt: new Date().toISOString(),
      };

      // Map backend step to stage
      const stepToStage: Record<string, WorkflowStage> = {
        ingest: "research",
        research: "research",
        analysis: "research",
        discovery: "discovery",
        qa: "discovery",
        draft: "drafting",
        editor: "drafting",
        completed: "export",
      };

      const currentStep = backendData.current_step || "";
      const mappedStage = stepToStage[currentStep];

      if (mappedStage) {
        updates.currentStage = mappedStage;
      }

      // Update completion flags
      if (backendData.research_complete !== undefined) {
        updates.researchComplete = backendData.research_complete;
      }
      if (backendData.discovery_confirmed !== undefined) {
        updates.discoveryConfirmed = backendData.discovery_confirmed;
      }
      if (backendData.draft_approved !== undefined) {
        updates.draftApproved = backendData.draft_approved;
      }
      if (backendData.export_complete !== undefined) {
        updates.exportComplete = backendData.export_complete;
      }

      // Recalculate stages based on flags AND current step
      // The current step helps determine if we've truly moved past a stage
      const isResearchComplete = updates.researchComplete || session.researchComplete;
      const isDiscoveryConfirmed = updates.discoveryConfirmed || session.discoveryConfirmed;
      const isDraftApproved = updates.draftApproved || session.draftApproved;
      const isExportComplete = updates.exportComplete || session.exportComplete;

      // Steps that indicate we've moved past discovery phase
      const pastDiscoverySteps = ["draft", "editor", "completed"];
      const isPastDiscovery = pastDiscoverySteps.includes(currentStep);

      // Steps that indicate we've moved past drafting phase
      const pastDraftingSteps = ["completed"];
      const isPastDrafting = pastDraftingSteps.includes(currentStep);

      const updatedStages: Record<WorkflowStage, StageStatus> = {
        research: isResearchComplete ? "completed" : "active",
        // Discovery is only "completed" if confirmed AND we've moved to a later step
        discovery: isResearchComplete
          ? (isDiscoveryConfirmed && isPastDiscovery ? "completed" : "active")
          : "locked",
        // Drafting is only "active" if we're actually in or past the drafting step
        drafting: (isDiscoveryConfirmed && isPastDiscovery)
          ? (isDraftApproved && isPastDrafting ? "completed" : "active")
          : "locked",
        export: isDraftApproved && isPastDrafting
          ? (isExportComplete ? "completed" : "active")
          : "locked",
      };

      updates.stages = updatedStages;

      const updatedSession: WorkflowSession = {
        ...session,
        ...updates,
      };

      setSession(updatedSession);
    },
    [session]
  );

  return {
    // State
    session,
    existingSession,
    isLoading,
    stageOrder: STAGE_ORDER,

    // Session management
    checkExistingSession,
    startSession,
    resumeSession,
    clearAllSessions,
    hasExistingSession,

    // Stage management
    completeStage,
    setActiveStage,
    getEarliestIncompleteStage,
    canAccessStage,

    // Error recovery
    recordError,
    retryFromError,
    startFreshFromError,

    // Status helpers
    isWorkflowComplete,
    getCompletionPercentage,
    syncFromBackend,
  };
}

/**
 * Human-readable stage labels for UI.
 */
export function getStageLabel(stage: WorkflowStage): string {
  const labels: Record<WorkflowStage, string> = {
    research: "Research",
    discovery: "Discovery",
    drafting: "Drafting",
    export: "Export",
  };
  return labels[stage];
}

/**
 * Get stage description for tooltips.
 */
export function getStageDescription(stage: WorkflowStage): string {
  const descriptions: Record<WorkflowStage, string> = {
    research: "Analyzing profile, job posting, and company",
    discovery: "Finding hidden experiences through conversation",
    drafting: "Creating and editing tailored resume",
    export: "Generating optimized files for ATS",
  };
  return descriptions[stage];
}
