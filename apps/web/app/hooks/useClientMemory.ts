"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * Client-side memory system for browser localStorage persistence.
 *
 * Two types of memory:
 * 1. EPISODIC: Records of past sessions (resumes made, gaps found, discoveries)
 * 2. SEMANTIC: Accumulated knowledge (experience union, edit preferences)
 */

const STORAGE_KEYS = {
  // Episodic memory - records of past sessions
  sessionHistory: "resume_agent:session_history",
  // Semantic memory - accumulated knowledge
  experienceUnion: "resume_agent:experience_union",
  editPreferences: "resume_agent:edit_preferences",
  // Current session edits (profile/job markdown)
  profileEdits: "resume_agent:profile_edits",
  jobEdits: "resume_agent:job_edits",
};

// ============ Types ============

export interface SessionRecord {
  id: string;
  createdAt: string;
  profileName: string | null;
  jobTitle: string | null;
  companyName: string | null;
  gaps: string[];
  discoveries: string[];
  resumeHtml: string | null;
  resumeText: string | null;
}

export interface ExperienceEntry {
  id: string;
  description: string;
  sourceQuote?: string;
  mappedSkills: string[];
  discoveredAt: string;
  sessionId: string;
}

export interface EditPreference {
  dimension: string; // e.g., "tone", "length", "format"
  value: string; // e.g., "concise", "short", "bullet-heavy"
  confidence: number; // 0-1, increases with each confirming event
  learnedAt: string;
  eventCount: number;
}

export interface ClientMemory {
  // Episodic
  sessionHistory: SessionRecord[];
  // Semantic
  experienceUnion: ExperienceEntry[];
  editPreferences: EditPreference[];
}

// ============ Hook ============

export function useClientMemory() {
  const [memory, setMemory] = useState<ClientMemory>({
    sessionHistory: [],
    experienceUnion: [],
    editPreferences: [],
  });
  const [isLoaded, setIsLoaded] = useState(false);

  // Load memory from localStorage on mount
  useEffect(() => {
    try {
      const sessionHistory = localStorage.getItem(STORAGE_KEYS.sessionHistory);
      const experienceUnion = localStorage.getItem(STORAGE_KEYS.experienceUnion);
      const editPreferences = localStorage.getItem(STORAGE_KEYS.editPreferences);

      setMemory({
        sessionHistory: sessionHistory ? JSON.parse(sessionHistory) : [],
        experienceUnion: experienceUnion ? JSON.parse(experienceUnion) : [],
        editPreferences: editPreferences ? JSON.parse(editPreferences) : [],
      });
    } catch (err) {
      console.error("Failed to load client memory:", err);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  // ============ Profile/Job Edits ============

  /**
   * Save profile markdown edit to localStorage.
   * Key is threadId-based so different sessions don't overwrite each other.
   */
  const saveProfileEdit = useCallback((threadId: string, markdown: string) => {
    try {
      const edits = JSON.parse(localStorage.getItem(STORAGE_KEYS.profileEdits) || "{}");
      edits[threadId] = { markdown, savedAt: new Date().toISOString() };
      localStorage.setItem(STORAGE_KEYS.profileEdits, JSON.stringify(edits));
      return true;
    } catch (err) {
      console.error("Failed to save profile edit:", err);
      return false;
    }
  }, []);

  /**
   * Get saved profile edit for a thread.
   */
  const getProfileEdit = useCallback((threadId: string): string | null => {
    try {
      const edits = JSON.parse(localStorage.getItem(STORAGE_KEYS.profileEdits) || "{}");
      return edits[threadId]?.markdown || null;
    } catch {
      return null;
    }
  }, []);

  /**
   * Save job markdown edit to localStorage.
   */
  const saveJobEdit = useCallback((threadId: string, markdown: string) => {
    try {
      const edits = JSON.parse(localStorage.getItem(STORAGE_KEYS.jobEdits) || "{}");
      edits[threadId] = { markdown, savedAt: new Date().toISOString() };
      localStorage.setItem(STORAGE_KEYS.jobEdits, JSON.stringify(edits));
      return true;
    } catch (err) {
      console.error("Failed to save job edit:", err);
      return false;
    }
  }, []);

  /**
   * Get saved job edit for a thread.
   */
  const getJobEdit = useCallback((threadId: string): string | null => {
    try {
      const edits = JSON.parse(localStorage.getItem(STORAGE_KEYS.jobEdits) || "{}");
      return edits[threadId]?.markdown || null;
    } catch {
      return null;
    }
  }, []);

  // ============ Episodic Memory ============

  /**
   * Record a completed session.
   * Called when user completes the workflow (export step).
   */
  const recordSession = useCallback((session: Omit<SessionRecord, "id" | "createdAt">) => {
    try {
      const record: SessionRecord = {
        ...session,
        id: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
      };

      const history = JSON.parse(localStorage.getItem(STORAGE_KEYS.sessionHistory) || "[]");
      // Keep last 20 sessions to avoid localStorage bloat
      const updatedHistory = [record, ...history].slice(0, 20);
      localStorage.setItem(STORAGE_KEYS.sessionHistory, JSON.stringify(updatedHistory));

      setMemory((prev) => ({
        ...prev,
        sessionHistory: updatedHistory,
      }));

      return record.id;
    } catch (err) {
      console.error("Failed to record session:", err);
      return null;
    }
  }, []);

  /**
   * Get past sessions for display or pre-loading.
   */
  const getSessionHistory = useCallback((): SessionRecord[] => {
    return memory.sessionHistory;
  }, [memory.sessionHistory]);

  /**
   * Get the most recent session (for "continue where you left off").
   */
  const getLastSession = useCallback((): SessionRecord | null => {
    return memory.sessionHistory[0] || null;
  }, [memory.sessionHistory]);

  // ============ Semantic Memory ============

  /**
   * Add discovered experiences to the union (deduped).
   * This builds a growing pool of user's experiences across sessions.
   */
  const addExperiences = useCallback((experiences: Omit<ExperienceEntry, "id" | "discoveredAt">[], sessionId: string) => {
    try {
      const existing = JSON.parse(localStorage.getItem(STORAGE_KEYS.experienceUnion) || "[]");

      // Add new experiences with IDs
      const newEntries: ExperienceEntry[] = experiences.map((exp) => ({
        ...exp,
        id: crypto.randomUUID(),
        discoveredAt: new Date().toISOString(),
        sessionId,
      }));

      // Simple deduplication by description similarity
      const combined = [...existing];
      for (const newExp of newEntries) {
        const isDuplicate = combined.some(
          (e) => e.description.toLowerCase() === newExp.description.toLowerCase()
        );
        if (!isDuplicate) {
          combined.push(newExp);
        }
      }

      // Keep last 100 experiences
      const trimmed = combined.slice(-100);
      localStorage.setItem(STORAGE_KEYS.experienceUnion, JSON.stringify(trimmed));

      setMemory((prev) => ({
        ...prev,
        experienceUnion: trimmed,
      }));

      return newEntries.length;
    } catch (err) {
      console.error("Failed to add experiences:", err);
      return 0;
    }
  }, []);

  /**
   * Get all accumulated experiences.
   * Can be used to pre-populate the first version of a resume.
   */
  const getExperienceUnion = useCallback((): ExperienceEntry[] => {
    return memory.experienceUnion;
  }, [memory.experienceUnion]);

  /**
   * Get experiences as markdown for loading into a new resume.
   */
  const getExperiencesAsMarkdown = useCallback((): string => {
    if (memory.experienceUnion.length === 0) {
      return "";
    }

    const grouped: Record<string, ExperienceEntry[]> = {};
    for (const exp of memory.experienceUnion) {
      const skills = exp.mappedSkills.join(", ") || "General";
      if (!grouped[skills]) {
        grouped[skills] = [];
      }
      grouped[skills].push(exp);
    }

    let markdown = "## Your Experience Library\n\n";
    markdown += "*These experiences were discovered in your previous sessions.*\n\n";

    for (const [skills, exps] of Object.entries(grouped)) {
      markdown += `### ${skills}\n`;
      for (const exp of exps) {
        markdown += `- ${exp.description}\n`;
        if (exp.sourceQuote) {
          markdown += `  *"${exp.sourceQuote}"*\n`;
        }
      }
      markdown += "\n";
    }

    return markdown;
  }, [memory.experienceUnion]);

  /**
   * Learn an edit preference from user behavior.
   */
  const learnEditPreference = useCallback((dimension: string, value: string) => {
    try {
      const prefs: EditPreference[] = JSON.parse(
        localStorage.getItem(STORAGE_KEYS.editPreferences) || "[]"
      );

      // Find existing preference for this dimension
      const existingIndex = prefs.findIndex((p) => p.dimension === dimension);

      if (existingIndex >= 0) {
        const existing = prefs[existingIndex];
        if (existing.value === value) {
          // Same preference - increase confidence
          prefs[existingIndex] = {
            ...existing,
            confidence: Math.min(1, existing.confidence + 0.1),
            eventCount: existing.eventCount + 1,
          };
        } else {
          // Different preference - decrease confidence or replace
          if (existing.confidence < 0.3) {
            prefs[existingIndex] = {
              dimension,
              value,
              confidence: 0.2,
              learnedAt: new Date().toISOString(),
              eventCount: 1,
            };
          } else {
            prefs[existingIndex] = {
              ...existing,
              confidence: existing.confidence - 0.15,
            };
          }
        }
      } else {
        // New preference
        prefs.push({
          dimension,
          value,
          confidence: 0.2,
          learnedAt: new Date().toISOString(),
          eventCount: 1,
        });
      }

      localStorage.setItem(STORAGE_KEYS.editPreferences, JSON.stringify(prefs));

      setMemory((prev) => ({
        ...prev,
        editPreferences: prefs,
      }));
    } catch (err) {
      console.error("Failed to learn edit preference:", err);
    }
  }, []);

  /**
   * Get learned edit preferences (high confidence only).
   */
  const getEditPreferences = useCallback(
    (minConfidence = 0.5): EditPreference[] => {
      return memory.editPreferences.filter((p) => p.confidence >= minConfidence);
    },
    [memory.editPreferences]
  );

  /**
   * Get edit preferences as a summary string for prompts.
   */
  const getPreferencesSummary = useCallback((): string => {
    const highConfidence = memory.editPreferences.filter((p) => p.confidence >= 0.5);
    if (highConfidence.length === 0) {
      return "";
    }

    return highConfidence
      .map((p) => `${p.dimension}: ${p.value}`)
      .join(", ");
  }, [memory.editPreferences]);

  // ============ Cleanup ============

  /**
   * Delete a specific session from history.
   */
  const deleteSession = useCallback((sessionId: string) => {
    try {
      const history = memory.sessionHistory.filter((s) => s.id !== sessionId);
      localStorage.setItem(STORAGE_KEYS.sessionHistory, JSON.stringify(history));
      setMemory((prev) => ({ ...prev, sessionHistory: history }));
      return true;
    } catch (err) {
      console.error("Failed to delete session:", err);
      return false;
    }
  }, [memory.sessionHistory]);

  /**
   * Delete a specific experience from the union.
   */
  const deleteExperience = useCallback((experienceId: string) => {
    try {
      const experiences = memory.experienceUnion.filter((e) => e.id !== experienceId);
      localStorage.setItem(STORAGE_KEYS.experienceUnion, JSON.stringify(experiences));
      setMemory((prev) => ({ ...prev, experienceUnion: experiences }));
      return true;
    } catch (err) {
      console.error("Failed to delete experience:", err);
      return false;
    }
  }, [memory.experienceUnion]);

  /**
   * Delete a specific edit preference.
   */
  const deleteEditPreference = useCallback((dimension: string) => {
    try {
      const prefs = memory.editPreferences.filter((p) => p.dimension !== dimension);
      localStorage.setItem(STORAGE_KEYS.editPreferences, JSON.stringify(prefs));
      setMemory((prev) => ({ ...prev, editPreferences: prefs }));
      return true;
    } catch (err) {
      console.error("Failed to delete preference:", err);
      return false;
    }
  }, [memory.editPreferences]);

  /**
   * Delete a saved profile edit.
   */
  const deleteProfileEdit = useCallback((threadId: string) => {
    try {
      const edits = JSON.parse(localStorage.getItem(STORAGE_KEYS.profileEdits) || "{}");
      delete edits[threadId];
      localStorage.setItem(STORAGE_KEYS.profileEdits, JSON.stringify(edits));
      return true;
    } catch (err) {
      console.error("Failed to delete profile edit:", err);
      return false;
    }
  }, []);

  /**
   * Delete a saved job edit.
   */
  const deleteJobEdit = useCallback((threadId: string) => {
    try {
      const edits = JSON.parse(localStorage.getItem(STORAGE_KEYS.jobEdits) || "{}");
      delete edits[threadId];
      localStorage.setItem(STORAGE_KEYS.jobEdits, JSON.stringify(edits));
      return true;
    } catch (err) {
      console.error("Failed to delete job edit:", err);
      return false;
    }
  }, []);

  /**
   * Get all saved profile edits (for management UI).
   */
  const getAllProfileEdits = useCallback((): Record<string, { markdown: string; savedAt: string }> => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.profileEdits) || "{}");
    } catch {
      return {};
    }
  }, []);

  /**
   * Get all saved job edits (for management UI).
   */
  const getAllJobEdits = useCallback((): Record<string, { markdown: string; savedAt: string }> => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.jobEdits) || "{}");
    } catch {
      return {};
    }
  }, []);

  /**
   * Clear all client memory (for privacy/reset).
   */
  const clearAllMemory = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEYS.sessionHistory);
      localStorage.removeItem(STORAGE_KEYS.experienceUnion);
      localStorage.removeItem(STORAGE_KEYS.editPreferences);
      localStorage.removeItem(STORAGE_KEYS.profileEdits);
      localStorage.removeItem(STORAGE_KEYS.jobEdits);

      setMemory({
        sessionHistory: [],
        experienceUnion: [],
        editPreferences: [],
      });
    } catch (err) {
      console.error("Failed to clear memory:", err);
    }
  }, []);

  /**
   * Clear old profile/job edits (older than 7 days).
   */
  const cleanupOldEdits = useCallback(() => {
    try {
      const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

      for (const key of [STORAGE_KEYS.profileEdits, STORAGE_KEYS.jobEdits]) {
        const edits = JSON.parse(localStorage.getItem(key) || "{}");
        const cleaned: Record<string, { markdown: string; savedAt: string }> = {};

        for (const [threadId, data] of Object.entries(edits)) {
          const edit = data as { markdown: string; savedAt: string };
          if (new Date(edit.savedAt).getTime() > sevenDaysAgo) {
            cleaned[threadId] = edit;
          }
        }

        localStorage.setItem(key, JSON.stringify(cleaned));
      }
    } catch (err) {
      console.error("Failed to cleanup old edits:", err);
    }
  }, []);

  // Run cleanup on mount
  useEffect(() => {
    cleanupOldEdits();
  }, [cleanupOldEdits]);

  return {
    isLoaded,
    memory,
    // Profile/Job edits
    saveProfileEdit,
    getProfileEdit,
    saveJobEdit,
    getJobEdit,
    getAllProfileEdits,
    getAllJobEdits,
    deleteProfileEdit,
    deleteJobEdit,
    // Episodic memory
    recordSession,
    getSessionHistory,
    getLastSession,
    deleteSession,
    // Semantic memory
    addExperiences,
    getExperienceUnion,
    getExperiencesAsMarkdown,
    deleteExperience,
    learnEditPreference,
    getEditPreferences,
    getPreferencesSummary,
    deleteEditPreference,
    // Cleanup
    clearAllMemory,
    cleanupOldEdits,
  };
}
