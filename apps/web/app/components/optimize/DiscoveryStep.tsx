"use client";

import { useState, useEffect, useMemo } from "react";
import {
  GapAnalysis,
  DiscoveryPrompt as BackendDiscoveryPrompt,
  DiscoveryMessage as BackendDiscoveryMessage,
  DiscoveredExperience as BackendDiscoveredExperience,
} from "../../hooks/useWorkflow";
import {
  useDiscoveryStorage,
  DiscoveryPrompt,
  DiscoveredExperience,
} from "../../hooks/useDiscoveryStorage";
import GapAnalysisDisplay from "./GapAnalysisDisplay";
import DiscoveryChat from "./DiscoveryChat";
import DiscoveredExperiences from "./DiscoveredExperiences";
import SessionRecoveryPrompt from "./SessionRecoveryPrompt";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DiscoveryStepProps {
  threadId: string;
  gapAnalysis: GapAnalysis | null;
  discoveryPrompts: BackendDiscoveryPrompt[];
  discoveryMessages: BackendDiscoveryMessage[];
  discoveredExperiences: BackendDiscoveredExperience[];
  discoveryConfirmed: boolean;
  discoveryExchanges: number;
  pendingQuestion: string | null;
  onSubmitAnswer: (answer: string) => Promise<void>;
  interruptPayload: {
    message?: string;
    context?: {
      intent?: string;
      related_gaps?: string[];
      prompt_number?: number;
      total_prompts?: number;
    };
  } | null;
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
  pendingQuestion,
  onSubmitAnswer,
  interruptPayload,
}: DiscoveryStepProps) {
  const storage = useDiscoveryStorage();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showRecoveryPrompt, setShowRecoveryPrompt] = useState(false);

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
        `${API_URL}/api/optimize/${threadId}/discovery/confirm`,
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
    } catch (error) {
      console.error("Failed to confirm discovery:", error);
      storage.recordError(
        error instanceof Error ? error.message : "Failed to confirm discovery"
      );
    } finally {
      setIsSubmitting(false);
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
      {/* Gap Analysis Overview */}
      {gapAnalysis && <GapAnalysisDisplay gapAnalysis={gapAnalysis} />}

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
          />
        </div>

        {/* Sidebar - discovered experiences and context */}
        <div className="space-y-6">
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
        </div>
      </div>

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
