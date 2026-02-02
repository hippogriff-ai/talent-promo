"use client";

import { useState, useEffect, useMemo } from "react";
import {
  GapAnalysis,
  ResearchFindings,
  DiscoveryPrompt as BackendDiscoveryPrompt,
  DiscoveryMessage as BackendDiscoveryMessage,
  DiscoveredExperience as BackendDiscoveredExperience,
  DiscoveryAgenda as BackendDiscoveryAgenda,
} from "../../hooks/useWorkflow";
import { ResearchModal } from "./ResearchStep";
import {
  useDiscoveryStorage,
  DiscoveryPrompt,
  DiscoveredExperience,
} from "../../hooks/useDiscoveryStorage";
import GapAnalysisDisplay from "./GapAnalysisDisplay";
import DiscoveryChat from "./DiscoveryChat";
import DiscoveredExperiences from "./DiscoveredExperiences";
import SessionRecoveryPrompt from "./SessionRecoveryPrompt";
import DiscoveryAgendaComponent from "./DiscoveryAgenda";


interface DiscoveryStepProps {
  threadId: string;
  gapAnalysis: GapAnalysis | null;
  discoveryPrompts: BackendDiscoveryPrompt[];
  discoveryMessages: BackendDiscoveryMessage[];
  discoveredExperiences: BackendDiscoveredExperience[];
  discoveryConfirmed: boolean;
  discoveryExchanges: number;
  discoveryAgenda: BackendDiscoveryAgenda | null;
  pendingQuestion: string | null;
  onSubmitAnswer: (answer: string) => Promise<void>;
  interruptPayload: {
    message?: string;
    context?: {
      intent?: string;
      related_gaps?: string[];
      prompt_number?: number;
      total_prompts?: number;
      current_topic?: {
        id?: string;
        title?: string;
        goal?: string;
        prompts_asked?: number;
        max_prompts?: number;
      };
      agenda_progress?: {
        covered_topics?: number;
        total_topics?: number;
      };
    };
  } | null;
  // Research data for "View Research Report" modal
  research?: ResearchFindings | null;
  // Markdown content for gap analysis rerun
  profileMarkdown?: string | null;
  jobMarkdown?: string | null;
  // Called after skip/confirm so parent can immediately show loading state
  onDiscoveryDone?: () => void;
}

/**
 * Main Discovery step component.
 *
 * Features:
 * - Session recovery on page reload
 * - Gap analysis display
 * - Discovery conversation
 * - Discovered experiences list
 */
export default function DiscoveryStep({
  threadId,
  gapAnalysis,
  discoveryPrompts,
  discoveryMessages,
  discoveredExperiences,
  discoveryConfirmed,
  discoveryExchanges,
  discoveryAgenda,
  pendingQuestion,
  onSubmitAnswer,
  interruptPayload,
  research,
  profileMarkdown,
  jobMarkdown,
  onDiscoveryDone,
}: DiscoveryStepProps) {
  const storage = useDiscoveryStorage();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showRecoveryPrompt, setShowRecoveryPrompt] = useState(false);
  const [isRerunningGapAnalysis, setIsRerunningGapAnalysis] = useState(false);
  const [researchModalOpen, setResearchModalOpen] = useState(false);

  // Convert backend data to frontend format - memoized to prevent infinite re-renders
  const messages = useMemo(() => discoveryMessages.map((m) => ({
    role: m.role as "agent" | "user",
    content: m.content,
    timestamp: m.timestamp,
    promptId: m.prompt_id,
    experiencesExtracted: m.experiences_extracted,
  })), [discoveryMessages]);

  const experiences: DiscoveredExperience[] = useMemo(() => discoveredExperiences.map(
    (e) => ({
      id: e.id,
      description: e.description,
      sourceQuote: e.source_quote,
      mappedRequirements: e.mapped_requirements,
      discoveredAt: e.discovered_at,
    })
  ), [discoveredExperiences]);

  const prompts: DiscoveryPrompt[] = useMemo(() => discoveryPrompts.map((p) => ({
    id: p.id,
    question: p.question,
    intent: p.intent,
    relatedGaps: p.related_gaps || [],
    priority: p.priority,
    asked: p.asked,
  })), [discoveryPrompts]);

  // Get current prompt from interrupt payload or find next unasked
  const currentPrompt: DiscoveryPrompt | null = pendingQuestion
    ? {
        id: "pending",
        question: pendingQuestion,
        intent: interruptPayload?.context?.intent || "",
        relatedGaps: interruptPayload?.context?.related_gaps || [],
        priority: interruptPayload?.context?.prompt_number || 1,
        asked: false,
      }
    : null;

  const totalPrompts =
    interruptPayload?.context?.total_prompts ?? prompts.length ?? 5;
  const currentPromptNumber =
    interruptPayload?.context?.prompt_number ?? messages.filter((m) => m.role === "agent").length;

  // Initialize/sync storage on mount
  useEffect(() => {
    if (threadId && !storage.session) {
      // Check for existing session
      const existing = storage.checkExistingSession(threadId);
      if (existing) {
        setShowRecoveryPrompt(true);
      } else {
        storage.startSession(threadId, prompts);
      }
    }
    // Only depend on threadId and session existence, not the entire storage object
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, storage.session, prompts]);

  // Sync from backend when data changes
  useEffect(() => {
    if (storage.session && threadId === storage.session.threadId) {
      storage.syncFromBackend({
        discovery_messages: discoveryMessages,
        discovered_experiences: discoveredExperiences,
        discovery_prompts: discoveryPrompts,
        discovery_confirmed: discoveryConfirmed,
        discovery_exchanges: discoveryExchanges,
      });
    }
    // Only depend on actual data changes, not the storage object reference
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    threadId,
    storage.session?.threadId,
    discoveryMessages,
    discoveredExperiences,
    discoveryPrompts,
    discoveryConfirmed,
    discoveryExchanges,
  ]);

  const handleSubmitResponse = async (response: string) => {
    setIsSubmitting(true);
    try {
      await onSubmitAnswer(response);
    } catch (error) {
      console.error("Failed to submit response:", error);
      storage.recordError(
        error instanceof Error ? error.message : "Failed to submit response"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmComplete = async () => {
    if (discoveryExchanges < 3) {
      alert("Please complete at least 3 conversation exchanges before confirming.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(
        `/api/optimize/${threadId}/discovery/confirm`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to confirm discovery");
      }

      storage.confirmDiscovery();
      onDiscoveryDone?.();
    } catch (error) {
      console.error("Failed to confirm discovery:", error);
      storage.recordError(
        error instanceof Error ? error.message : "Failed to confirm discovery"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkipDiscovery = async () => {
    if (!confirm("Are you sure you want to skip the discovery phase? The AI will create your resume based solely on what you provided initially.")) {
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(
        `/api/optimize/${threadId}/discovery/skip`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to skip discovery");
      }

      storage.confirmDiscovery();
      onDiscoveryDone?.();
    } catch (error) {
      console.error("Failed to skip discovery:", error);
      storage.recordError(
        error instanceof Error ? error.message : "Failed to skip discovery"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRerunGapAnalysis = async () => {
    setIsRerunningGapAnalysis(true);
    try {
      // Send current profile/job markdown to backend so it uses the
      // latest content (including any user edits from the modal)
      const response = await fetch(
        `/api/optimize/${threadId}/gap-analysis/rerun`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            profile_markdown: profileMarkdown || undefined,
            job_markdown: jobMarkdown || undefined,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to re-run gap analysis");
      }

      // The workflow will update the gap analysis and trigger a re-render
      // through the parent component's state update
    } catch (error) {
      console.error("Failed to re-run gap analysis:", error);
      storage.recordError(
        error instanceof Error ? error.message : "Failed to re-run gap analysis"
      );
    } finally {
      setIsRerunningGapAnalysis(false);
    }
  };

  const handleResumeSession = () => {
    if (storage.existingSession) {
      storage.resumeSession(storage.existingSession);
    }
    setShowRecoveryPrompt(false);
  };

  const handleStartFresh = () => {
    storage.clearSession(threadId);
    storage.startSession(threadId, prompts);
    setShowRecoveryPrompt(false);
  };

  // Show recovery prompt if we have an existing incomplete session
  if (showRecoveryPrompt && storage.existingSession) {
    return (
      <SessionRecoveryPrompt
        session={{
          ...storage.existingSession,
          linkedinUrl: "",
          jobUrl: "",
          completedSteps: [],
          currentStep: null,
          data: {
            userProfile: null,
            jobPosting: null,
            companyResearch: null,
            similarHires: null,
            exEmployees: null,
            hiringCriteria: null,
            idealProfile: null,
          },
        }}
        onResume={handleResumeSession}
        onStartFresh={handleStartFresh}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Research Report + Gap Analysis Overview */}
      {gapAnalysis && (
        <div className="space-y-4">
          {/* View Research Report Button */}
          {research && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <svg className="w-5 h-5 text-blue-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <div>
                  <p className="text-sm font-medium text-blue-800">Research Report Available</p>
                  <p className="text-xs text-blue-600">Company overview, culture, tech stack, hiring criteria, and more</p>
                </div>
              </div>
              <button
                onClick={() => setResearchModalOpen(true)}
                className="px-4 py-2 text-sm font-medium text-blue-700 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors flex items-center"
              >
                View Full Research Report
                <svg className="w-4 h-4 ml-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </button>
            </div>
          )}

          <GapAnalysisDisplay
            gapAnalysis={gapAnalysis}
            onRerun={handleRerunGapAnalysis}
            isRerunning={isRerunningGapAnalysis}
          />
        </div>
      )}

      {/* Main content area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chat area - takes 2 columns on large screens */}
        <div className="lg:col-span-2 h-[600px]">
          <DiscoveryChat
            messages={messages}
            pendingPrompt={currentPrompt}
            totalPrompts={totalPrompts}
            currentPromptNumber={currentPromptNumber}
            exchanges={discoveryExchanges}
            canConfirm={discoveryExchanges >= 3}
            onSubmitResponse={handleSubmitResponse}
            onConfirmComplete={handleConfirmComplete}
            isSubmitting={isSubmitting}
            currentTopic={interruptPayload?.context?.current_topic}
          />
        </div>

        {/* Sidebar - agenda, discovered experiences and context */}
        <div className="space-y-6">
          {/* Discovery Agenda */}
          {discoveryAgenda && (
            <DiscoveryAgendaComponent agenda={discoveryAgenda} />
          )}

          <DiscoveredExperiences experiences={experiences} />

          {/* Context sidebar */}
          {gapAnalysis && (
            <div className="bg-white rounded-lg shadow p-4">
              <h4 className="font-medium text-gray-900 mb-3">
                What We&apos;re Looking For
              </h4>
              <GapAnalysisDisplay gapAnalysis={gapAnalysis} compact />
            </div>
          )}

          {/* Tips */}
          <div className="bg-purple-50 rounded-lg p-4">
            <h4 className="font-medium text-purple-900 mb-2">Tips</h4>
            <ul className="text-sm text-purple-800 space-y-2">
              <li className="flex items-start">
                <span className="mr-2">1.</span>
                <span>
                  Think about side projects, volunteer work, or informal
                  leadership roles
                </span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">2.</span>
                <span>
                  Include specific metrics or outcomes when possible
                </span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">3.</span>
                <span>
                  Don&apos;t dismiss experiences from different industries
                </span>
              </li>
            </ul>
          </div>

          {/* Skip Discovery Option */}
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <h4 className="font-medium text-gray-700 mb-2">Short on time?</h4>
            <p className="text-sm text-gray-600 mb-3">
              You can skip the discovery phase and proceed directly to resume drafting.
              The AI will use solely what you provided initially.
            </p>
            <button
              onClick={handleSkipDiscovery}
              disabled={isSubmitting}
              className="w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:bg-gray-100 disabled:text-gray-400 transition-colors"
            >
              {isSubmitting ? "Skipping..." : "Skip Discovery & Draft Resume"}
            </button>
          </div>
        </div>
      </div>

      {/* Research Report Modal */}
      <ResearchModal
        isOpen={researchModalOpen}
        onClose={() => setResearchModalOpen(false)}
        research={research ?? null}
        gapAnalysis={gapAnalysis}
      />

      {/* Warning if no experiences after completion */}
      {discoveryConfirmed && experiences.length === 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start space-x-3">
          <svg
            className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <div>
            <p className="text-amber-800 font-medium">
              No additional experiences found
            </p>
            <p className="text-amber-700 text-sm mt-1">
              You can still proceed, but the resume optimization will be based
              solely on your existing profile information.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
