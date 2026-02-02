"use client";

import { useState, useEffect, useCallback } from "react";
import type { ValidationResults } from "../types/guardrails";


// Custom error for rate limiting
export class RateLimitError extends Error {
  retryAfter: number;

  constructor(message: string, retryAfter: number) {
    super(message);
    this.name = "RateLimitError";
    this.retryAfter = retryAfter;
  }
}

// Types
export interface QAInteraction {
  question: string;
  answer: string | null;
  question_intent?: string;
  timestamp: string;
}

export interface UserProfile {
  name: string;
  headline?: string;
  summary?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin_url?: string;
  experience: Array<{
    company: string;
    position: string;
    location?: string;
    start_date?: string;
    end_date?: string;
    is_current: boolean;
    achievements: string[];
    technologies: string[];
    description?: string;
  }>;
  education: Array<{
    institution: string;
    degree?: string;
    field_of_study?: string;
    start_date?: string;
    end_date?: string;
  }>;
  skills: string[];
  certifications: string[];
}

export interface JobPosting {
  title: string;
  company_name: string;
  description: string;
  location?: string;
  work_type?: string;
  job_type?: string;
  experience_level?: string;
  requirements: string[];
  preferred_qualifications: string[];
  responsibilities: string[];
  tech_stack: string[];
  benefits: string[];
  salary_range?: string;
  source_url: string;
}

export interface GapAnalysis {
  strengths: string[];
  gaps: string[];
  recommended_emphasis: string[];
  transferable_skills: string[];
  keywords_to_include: string[];
  potential_concerns: string[];
}

export interface ResearchFindings {
  company_overview: string;
  company_culture: string;
  company_values: string[];
  tech_stack_details: Array<{
    technology: string;
    usage: string;
    importance: string;
  }>;
  similar_profiles: Array<{
    name: string;
    headline: string;
    url: string;
    key_skills: string[];
    current_company?: string;
    experience_highlights?: string[];
  }>;
  company_news: string[];
  industry_trends: string[];
  hiring_patterns?: string;
  // Additional research insights from backend
  hiring_criteria?: {
    must_haves: string[];
    preferred: string[];
    keywords: string[];
    ats_keywords: string[];
  };
  ideal_profile?: {
    headline: string;
    summary_focus: string[];
    experience_emphasis: string[];
    skills_priority: string[];
    differentiators: string[];
  };
}

export type WorkflowStatus = "idle" | "running" | "waiting_input" | "completed" | "error";

export type WorkflowStep =
  | "ingest"
  | "research"
  | "analysis"
  | "discovery"
  | "qa"
  | "draft"
  | "editor"
  | "completed"
  | "error";

export interface DiscoveryPrompt {
  id: string;
  question: string;
  intent: string;
  related_gaps: string[];
  priority: number;
  asked: boolean;
}

export interface DiscoveryMessage {
  role: string;
  content: string;
  timestamp: string;
  prompt_id?: string;
  experiences_extracted?: string[];
}

export interface DiscoveredExperience {
  id: string;
  description: string;
  source_quote: string;
  mapped_requirements: string[];
  discovered_at: string;
}

export type AgendaTopicStatus = "pending" | "in_progress" | "covered" | "skipped";

export interface AgendaTopic {
  id: string;
  title: string;
  goal: string;
  related_gaps: string[];
  priority: number;
  status: AgendaTopicStatus;
  prompts_asked: number;
  max_prompts: number;
  experiences_found: string[];
}

export interface DiscoveryAgenda {
  topics: AgendaTopic[];
  current_topic_id: string | null;
  total_topics: number;
  covered_topics: number;
}

export interface ProgressMessage {
  timestamp: string;
  phase: string;
  message: string;
  detail: string;
}

export interface WorkflowState {
  threadId: string | null;
  currentStep: WorkflowStep;
  subStep: string | null;  // Granular progress within a step
  status: WorkflowStatus;
  pendingQuestion: string | null;
  qaRound: number;
  progress: Record<string, string>;
  errors: string[];
  interruptPayload: Record<string, unknown> | null;
  data: {
    userProfile: UserProfile | null;
    jobPosting: JobPosting | null;
    // Raw markdown from EXA for display/editing
    profileMarkdown: string | null;
    jobMarkdown: string | null;
    research: ResearchFindings | null;
    gapAnalysis: GapAnalysis | null;
    qaHistory: QAInteraction[];
    resumeHtml: string | null;
    // Validation results from guardrails
    draftValidation: ValidationResults | null;
    // Discovery data
    discoveryPrompts: DiscoveryPrompt[];
    discoveryMessages: DiscoveryMessage[];
    discoveredExperiences: DiscoveredExperience[];
    discoveryConfirmed: boolean;
    discoveryExchanges: number;
    discoveryAgenda: DiscoveryAgenda | null;
    // Progress messages for real-time UI
    progressMessages: ProgressMessage[];
  };
}

export interface UserPreferences {
  tone?: string | null;
  structure?: string | null;
  sentence_length?: string | null;
  first_person?: boolean | null;
  quantification_preference?: string | null;
  achievement_focus?: boolean | null;
  custom_preferences?: Record<string, unknown>;
}

export interface UseWorkflowReturn extends WorkflowState {
  startWorkflow: (linkedinUrl?: string, jobUrl?: string, resumeText?: string, jobText?: string, userPreferences?: UserPreferences) => Promise<string>;
  resumeWorkflow: (threadId: string) => Promise<void>;
  submitAnswer: (answer: string) => Promise<void>;
  updateResume: (html: string) => Promise<void>;
  exportResume: (format: "docx" | "pdf") => Promise<Blob>;
  refreshStatus: () => Promise<void>;
  reset: () => void;
}

const initialState: WorkflowState = {
  threadId: null,
  currentStep: "ingest",
  subStep: null,
  status: "idle",
  pendingQuestion: null,
  qaRound: 0,
  progress: {},
  errors: [],
  interruptPayload: null,
  data: {
    userProfile: null,
    jobPosting: null,
    profileMarkdown: null,
    jobMarkdown: null,
    research: null,
    gapAnalysis: null,
    qaHistory: [],
    resumeHtml: null,
    draftValidation: null,
    discoveryPrompts: [],
    discoveryMessages: [],
    discoveredExperiences: [],
    discoveryConfirmed: false,
    discoveryExchanges: 0,
    discoveryAgenda: null,
    progressMessages: [],
  },
};

export function useWorkflow(): UseWorkflowReturn {
  const [state, setState] = useState<WorkflowState>(initialState);

  // Start new workflow
  const startWorkflow = useCallback(
    async (linkedinUrl?: string, jobUrl?: string, resumeText?: string, jobText?: string, userPreferences?: UserPreferences): Promise<string> => {
      const response = await fetch(`/api/optimize/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",  // Send session cookie
        body: JSON.stringify({
          linkedin_url: linkedinUrl,
          job_url: jobUrl,
          resume_text: resumeText,
          job_text: jobText,
          user_preferences: userPreferences,
        }),
      });

      if (!response.ok) {
        const error = await response.json();

        // Special handling for rate limiting
        if (response.status === 429) {
          const retryAfter = parseInt(response.headers.get("Retry-After") || "86400", 10);
          throw new RateLimitError(error.detail || "Rate limit exceeded", retryAfter);
        }

        throw new Error(error.detail || "Failed to start workflow");
      }

      const data = await response.json();

      setState((prev) => ({
        ...prev,
        threadId: data.thread_id,
        currentStep: data.current_step as WorkflowStep,
        status: data.status as WorkflowStatus,
        progress: data.progress || {},
      }));

      return data.thread_id;
    },
    []
  );

  // Resume existing workflow by threadId
  const resumeWorkflow = useCallback(
    async (threadId: string): Promise<void> => {
      // Fetch current state
      const response = await fetch(
        `/api/optimize/status/${threadId}?include_data=true`,
        { credentials: "include" }
      );

      if (!response.ok) {
        throw new Error("Failed to resume workflow - session may have expired");
      }

      const data = await response.json();

      // Restore full state
      setState({
        threadId,
        currentStep: data.current_step as WorkflowStep,
        subStep: data.sub_step || null,
        status: data.status as WorkflowStatus,
        pendingQuestion: data.pending_question,
        qaRound: data.qa_round || 0,
        progress: data.progress || {},
        errors: data.errors || [],
        interruptPayload: data.interrupt_payload || null,
        data: {
          userProfile: data.user_profile || null,
          jobPosting: data.job_posting || null,
          profileMarkdown: data.profile_markdown || null,
          jobMarkdown: data.job_markdown || null,
          research: data.research || null,
          gapAnalysis: data.gap_analysis || null,
          qaHistory: data.qa_history || [],
          resumeHtml: data.resume_html || null,
          draftValidation: data.draft_validation || null,
          discoveryPrompts: data.discovery_prompts || [],
          discoveryMessages: data.discovery_messages || [],
          discoveredExperiences: data.discovered_experiences || [],
          discoveryConfirmed: data.discovery_confirmed ?? false,
          discoveryExchanges: data.discovery_exchanges ?? 0,
          discoveryAgenda: data.discovery_agenda || null,
          progressMessages: data.progress_messages || [],
        },
      });
    },
    []
  );

  // Poll for status updates
  useEffect(() => {
    if (!state.threadId || state.status === "completed" || state.status === "error") {
      return;
    }

    const pollStatus = async () => {
      try {
        const response = await fetch(
          `/api/optimize/status/${state.threadId}?include_data=true`,
          { credentials: "include" }
        );

        if (!response.ok) {
          console.error("Status poll failed");
          return;
        }

        const data = await response.json();

        setState((prev) => ({
          ...prev,
          currentStep: data.current_step as WorkflowStep,
          subStep: data.sub_step || null,
          status: data.status as WorkflowStatus,
          pendingQuestion: data.pending_question,
          qaRound: data.qa_round || 0,
          progress: data.progress || {},
          errors: data.errors || [],
          interruptPayload: data.interrupt_payload || null,
          data: {
            userProfile: data.user_profile || prev.data.userProfile,
            jobPosting: data.job_posting || prev.data.jobPosting,
            profileMarkdown: data.profile_markdown || prev.data.profileMarkdown,
            jobMarkdown: data.job_markdown || prev.data.jobMarkdown,
            research: data.research || prev.data.research,
            gapAnalysis: data.gap_analysis || prev.data.gapAnalysis,
            qaHistory: data.qa_history || prev.data.qaHistory,
            resumeHtml: data.resume_html || prev.data.resumeHtml,
            draftValidation: data.draft_validation || prev.data.draftValidation,
            // Discovery data - preserve messages if backend returns empty during active session
            discoveryPrompts: data.discovery_prompts || prev.data.discoveryPrompts,
            discoveryMessages: (data.discovery_messages?.length > 0)
              ? data.discovery_messages
              : (prev.data.discoveryMessages?.length > 0 && data.current_step === 'discovery')
                ? prev.data.discoveryMessages
                : data.discovery_messages || [],
            discoveredExperiences: data.discovered_experiences || prev.data.discoveredExperiences,
            discoveryConfirmed: data.discovery_confirmed ?? prev.data.discoveryConfirmed,
            discoveryExchanges: data.discovery_exchanges ?? prev.data.discoveryExchanges,
            discoveryAgenda: data.discovery_agenda || prev.data.discoveryAgenda,
            // Progress messages
            progressMessages: data.progress_messages || prev.data.progressMessages,
          },
        }));
      } catch (error) {
        console.error("Status poll error:", error);
      }
    };

    // Initial poll
    pollStatus();

    // Set up polling interval
    const interval = setInterval(pollStatus, 2000);

    return () => clearInterval(interval);
  }, [state.threadId, state.status]);

  // Submit answer to Q&A
  const submitAnswer = useCallback(
    async (answer: string) => {
      if (!state.threadId) {
        throw new Error("No active workflow");
      }

      // Optimistically update local Q&A history
      setState((prev) => {
        const updatedHistory = [...prev.data.qaHistory];
        if (updatedHistory.length > 0) {
          const lastIdx = updatedHistory.length - 1;
          if (updatedHistory[lastIdx].answer === null) {
            updatedHistory[lastIdx] = {
              ...updatedHistory[lastIdx],
              answer,
            };
          }
        }

        return {
          ...prev,
          status: "running" as WorkflowStatus,
          pendingQuestion: null,
          data: {
            ...prev.data,
            qaHistory: updatedHistory,
          },
        };
      });

      const response = await fetch(`/api/optimize/${state.threadId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ text: answer }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to submit answer");
      }
    },
    [state.threadId]
  );

  // Update resume content
  const updateResume = useCallback(
    async (html: string) => {
      if (!state.threadId) {
        throw new Error("No active workflow");
      }

      const response = await fetch(`/api/optimize/${state.threadId}/editor/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ html_content: html }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to update resume");
      }

      setState((prev) => ({
        ...prev,
        data: {
          ...prev.data,
          resumeHtml: html,
        },
      }));
    },
    [state.threadId]
  );

  // Export resume
  const exportResume = useCallback(
    async (format: "docx" | "pdf"): Promise<Blob> => {
      if (!state.threadId) {
        throw new Error("No active workflow");
      }

      const response = await fetch(`/api/optimize/${state.threadId}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ format }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to export resume");
      }

      return response.blob();
    },
    [state.threadId]
  );

  // Manually refresh status
  const refreshStatus = useCallback(async () => {
    if (!state.threadId) return;

    const response = await fetch(
      `/api/optimize/status/${state.threadId}?include_data=true`,
      { credentials: "include" }
    );

    if (response.ok) {
      const data = await response.json();
      setState((prev) => ({
        ...prev,
        currentStep: data.current_step as WorkflowStep,
        subStep: data.sub_step || null,
        status: data.status as WorkflowStatus,
        pendingQuestion: data.pending_question,
        qaRound: data.qa_round || 0,
        progress: data.progress || {},
        errors: data.errors || [],
        interruptPayload: data.interrupt_payload || null,
        data: {
          userProfile: data.user_profile || prev.data.userProfile,
          jobPosting: data.job_posting || prev.data.jobPosting,
          profileMarkdown: data.profile_markdown || prev.data.profileMarkdown,
          jobMarkdown: data.job_markdown || prev.data.jobMarkdown,
          research: data.research || prev.data.research,
          gapAnalysis: data.gap_analysis || prev.data.gapAnalysis,
          qaHistory: data.qa_history || prev.data.qaHistory,
          resumeHtml: data.resume_html || prev.data.resumeHtml,
          draftValidation: data.draft_validation || prev.data.draftValidation,
          discoveryPrompts: data.discovery_prompts || prev.data.discoveryPrompts,
          discoveryMessages: data.discovery_messages || prev.data.discoveryMessages,
          discoveredExperiences: data.discovered_experiences || prev.data.discoveredExperiences,
          discoveryConfirmed: data.discovery_confirmed ?? prev.data.discoveryConfirmed,
          discoveryExchanges: data.discovery_exchanges ?? prev.data.discoveryExchanges,
          discoveryAgenda: data.discovery_agenda || prev.data.discoveryAgenda,
          progressMessages: data.progress_messages || prev.data.progressMessages,
        },
      }));
    }
  }, [state.threadId]);

  // Reset workflow state
  const reset = useCallback(() => {
    setState(initialState);
  }, []);

  return {
    ...state,
    startWorkflow,
    resumeWorkflow,
    submitAnswer,
    updateResume,
    exportResume,
    refreshStatus,
    reset,
  };
}
