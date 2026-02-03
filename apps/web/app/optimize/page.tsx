"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useWorkflow } from "../hooks/useWorkflow";
import { useWorkflowSession, WorkflowStage, getStageLabel } from "../hooks/useWorkflowSession";
import { usePreferences } from "../hooks/usePreferences";
import { useExportStorage } from "../hooks/useExportStorage";
import { useClientMemory } from "../hooks/useClientMemory";
import WorkflowStepper from "../components/optimize/WorkflowStepper";
import SessionRecoveryModal from "../components/optimize/SessionRecoveryModal";
import StartNewSessionDialog from "../components/optimize/StartNewSessionDialog";
import ErrorRecovery from "../components/optimize/ErrorRecovery";
import ResearchStep, { ResearchModal } from "../components/optimize/ResearchStep";
import { ProfileEditorModal } from "../components/optimize/ProfileEditorModal";
import DiscoveryStep from "../components/optimize/DiscoveryStep";
import QAChat from "../components/optimize/QAChat";
import ResumeEditor from "../components/optimize/ResumeEditor";
import ExportStep from "../components/optimize/ExportStep";
import CompletionScreen from "../components/optimize/CompletionScreen";

const PENDING_INPUT_KEY = "talent_promo:pending_input";

/**
 * Map internal workflow steps to 4-stage orchestration.
 */
function mapStepToStage(step: string): WorkflowStage {
  switch (step) {
    case "ingest":
    case "research":
    case "analysis":
      return "research";
    case "discovery":
    case "qa":
      return "discovery";
    case "draft":
    case "editor":
      return "drafting";
    case "completed":
      return "export";
    default:
      return "research";
  }
}

export default function OptimizePage() {
  const router = useRouter();
  const workflow = useWorkflow();
  const workflowSession = useWorkflowSession();
  const { preferences } = usePreferences();
  const exportStorage = useExportStorage();
  const clientMemory = useClientMemory();

  const [inputData, setInputData] = useState<{
    linkedinUrl?: string;
    jobUrl?: string;
    resumeText?: string;
    jobText?: string;
    turnstileToken?: string;
  }>({});

  // Dialog states
  const [showRecoveryModal, setShowRecoveryModal] = useState(false);
  const [showStartNewDialog, setShowStartNewDialog] = useState(false);
  const [showCompletionScreen, setShowCompletionScreen] = useState(false);
  const userRequestedEditRef = useRef(false);
  const [stepOverride, setStepOverride] = useState<string | null>(null);
  const [discoveryDone, setDiscoveryDone] = useState(false);
  const [isAutoStarting, setIsAutoStarting] = useState(false);
  const [hasCheckedPending, setHasCheckedPending] = useState(false);

  // Research review state - pause before Discovery to let user review results
  const [showResearchReview, setShowResearchReview] = useState(false);
  const [hasAcknowledgedResearch, setHasAcknowledgedResearch] = useState(false);

  // Stage navigation - for viewing completed stages (read-only review mode)
  const [viewingStage, setViewingStage] = useState<WorkflowStage | null>(null);
  const [researchReviewModalOpen, setResearchReviewModalOpen] = useState(false);
  const [researchReviewSection, setResearchReviewSection] = useState<string | null>(null);

  const openResearchReviewModal = (section?: string) => {
    setResearchReviewSection(section || null);
    setResearchReviewModalOpen(true);
  };
  const closeResearchReviewModal = () => {
    setResearchReviewModalOpen(false);
    setResearchReviewSection(null);
  };

  // Modal states for viewing profile and job markdown
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [jobModalOpen, setJobModalOpen] = useState(false);

  // Edited markdown state (persisted to localStorage via clientMemory)
  const [editedProfileMarkdown, setEditedProfileMarkdown] = useState<string | null>(null);
  const [editedJobMarkdown, setEditedJobMarkdown] = useState<string | null>(null);

  // Load saved edits from localStorage when thread changes
  useEffect(() => {
    if (workflow.threadId && clientMemory.isLoaded) {
      const savedProfile = clientMemory.getProfileEdit(workflow.threadId);
      const savedJob = clientMemory.getJobEdit(workflow.threadId);
      if (savedProfile) setEditedProfileMarkdown(savedProfile);
      if (savedJob) setEditedJobMarkdown(savedJob);
    }
  }, [workflow.threadId, clientMemory.isLoaded, clientMemory]);

  // Check for pending input from landing page and auto-start
  useEffect(() => {
    if (hasCheckedPending) return;

    const pendingInput = localStorage.getItem(PENDING_INPUT_KEY);
    if (pendingInput) {
      try {
        const data = JSON.parse(pendingInput);
        setInputData(data);
        localStorage.removeItem(PENDING_INPUT_KEY);

        // Auto-start the workflow
        setIsAutoStarting(true);
        (async () => {
          try {
            const threadId = await workflow.startWorkflow(
              data.linkedinUrl,
              data.jobUrl,
              data.resumeText,
              data.jobText,
              preferences,
              data.turnstileToken
            );
            workflowSession.startSession(
              data.linkedinUrl || "",
              data.jobUrl || "",
              threadId
            );
          } catch (error) {
            console.error("Failed to auto-start workflow:", error);
          } finally {
            setIsAutoStarting(false);
          }
        })();
      } catch (e) {
        console.error("Failed to parse pending input:", e);
        localStorage.removeItem(PENDING_INPUT_KEY);
      }
    }
    setHasCheckedPending(true);
  }, [hasCheckedPending, workflow, workflowSession, preferences]);

  // Check for existing session on mount
  useEffect(() => {
    if (!workflowSession.isLoading && workflowSession.existingSession) {
      // Show recovery modal if there's an existing session
      setShowRecoveryModal(true);
    }
  }, [workflowSession.isLoading, workflowSession.existingSession]);

  // Sync session state from workflow status
  // Note: workflowSession excluded from deps intentionally — syncFromBackend depends on session,
  // which it updates, so including it would risk a re-render loop. The effect triggers on
  // workflow changes which are the actual reactive signals.
  useEffect(() => {
    if (workflow.threadId && workflowSession.session) {
      // Update session based on workflow progress
      workflowSession.syncFromBackend({
        current_step: workflow.currentStep,
        research_complete: ["discovery", "qa", "draft", "editor", "completed"].includes(workflow.currentStep),
        discovery_confirmed: workflow.data.discoveryConfirmed,
        draft_approved: ["completed"].includes(workflow.currentStep),
        export_complete: workflow.currentStep === "completed" && workflow.status === "completed",
      });

      // Show completion screen when workflow is done (unless user explicitly went back to edit)
      if (workflow.currentStep === "completed" && workflow.status === "completed") {
        if (!userRequestedEditRef.current) {
          setShowCompletionScreen(true);
        }
      } else {
        // Reset the flag and step override once backend has reverted from "completed"
        userRequestedEditRef.current = false;
        if (stepOverride) setStepOverride(null);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow.threadId, workflow.currentStep, workflow.status, workflow.data.discoveryConfirmed, stepOverride]);

  // Detect research completion and show review screen
  useEffect(() => {
    // When we have all research data and workflow moves to discovery/qa but user hasn't acknowledged
    const researchComplete = !!(
      workflow.data.userProfile &&
      workflow.data.jobPosting &&
      workflow.data.gapAnalysis
    );

    if (
      researchComplete &&
      !hasAcknowledgedResearch &&
      (workflow.currentStep === "discovery" || workflow.currentStep === "qa")
    ) {
      setShowResearchReview(true);
    }
  }, [
    workflow.data.userProfile,
    workflow.data.jobPosting,
    workflow.data.gapAnalysis,
    workflow.currentStep,
    hasAcknowledgedResearch,
  ]);

  // Handle continuing from research review to discovery
  const handleContinueToDiscovery = () => {
    setShowResearchReview(false);
    setHasAcknowledgedResearch(true);
  };

  // Handle workflow start
  const handleStart = async () => {
    if (!inputData.jobUrl && !inputData.jobText) {
      alert("Please enter a job URL or paste the job description");
      return;
    }
    if (!inputData.linkedinUrl && !inputData.resumeText) {
      alert("Please enter a LinkedIn URL or paste your resume");
      return;
    }

    try {
      const threadId = await workflow.startWorkflow(
        inputData.linkedinUrl,
        inputData.jobUrl,
        inputData.resumeText,
        inputData.jobText,
        preferences
      );

      // Initialize session
      workflowSession.startSession(
        inputData.linkedinUrl || "",
        inputData.jobUrl || "",
        threadId
      );
    } catch (error) {
      console.error("Failed to start workflow:", error);

      // Save error state
      if (workflowSession.session) {
        workflowSession.recordError(
          error instanceof Error ? error.message : "Failed to start workflow"
        );
      }
    }
  };

  // Handle session recovery
  const handleResumeSession = async () => {
    workflowSession.resumeSession();
    setShowRecoveryModal(false);

    // If session has a threadId, resume the workflow
    if (workflowSession.existingSession?.threadId) {
      try {
        await workflow.resumeWorkflow(workflowSession.existingSession.threadId);
        console.log("Session resumed successfully");
      } catch (error) {
        console.error("Failed to resume session:", error);
        // Show error to user
        workflowSession.recordError(
          error instanceof Error ? error.message : "Failed to resume session"
        );
      }
    }
  };

  const handleStartFresh = () => {
    workflowSession.clearAllSessions();
    workflow.reset();
    setShowRecoveryModal(false);
    setShowResearchReview(false);
    setHasAcknowledgedResearch(false);
    setViewingStage(null);
    setInputData({});
    // Redirect to home page to start fresh
    router.push("/");
  };

  // Handle "Start New" button click
  const handleStartNewClick = () => {
    if (workflowSession.session?.researchComplete) {
      // Show confirmation if any work has been done
      setShowStartNewDialog(true);
    } else {
      // Just reset if nothing done
      handleConfirmStartNew();
    }
  };

  const handleConfirmStartNew = () => {
    workflowSession.clearAllSessions();
    workflow.reset();
    setShowStartNewDialog(false);
    setShowCompletionScreen(false);
    setShowResearchReview(false);
    setHasAcknowledgedResearch(false);
    setDiscoveryDone(false);
    setViewingStage(null);
    setInputData({});
    // Redirect to home page to start fresh
    router.push("/");
  };

  // Handle error recovery
  const handleRetry = () => {
    workflowSession.retryFromError();
    // Workflow will continue from last known state
    workflow.refreshStatus();
  };

  const handleStartFreshFromError = () => {
    workflowSession.clearAllSessions();
    workflow.reset();
    setViewingStage(null);
    // Redirect to home page to start fresh
    router.push("/");
  };

  // Handle paste resume option (for LinkedIn fetch failures)
  const handlePasteResume = () => {
    workflowSession.clearAllSessions();
    workflow.reset();
    setViewingStage(null);
    // Redirect to home page with paste mode pre-selected
    router.push("/?mode=paste");
  };

  // Handle stage click in stepper
  const handleStageClick = async (stage: WorkflowStage) => {
    if (!workflowSession.canAccessStage(stage)) {
      // Cannot access locked stages
      return;
    }

    // Get current workflow stage
    const currentWorkflowStage = mapStepToStage(workflow.currentStep);

    // If clicking the current active stage, clear viewing mode
    if (stage === currentWorkflowStage) {
      setViewingStage(null);
      return;
    }

    // If clicking a completed stage that is BEFORE the current stage, offer to go back
    const stageStatus = workflowSession.session?.stages[stage];
    if (stageStatus === "completed") {
      // Going back to discovery from drafting
      if (stage === "discovery" && (currentWorkflowStage === "drafting" || currentWorkflowStage === "export")) {
        if (!confirm("Go back to Discovery? Your current draft will be discarded and regenerated after you finish.")) {
          return;
        }
        await handleRevertToDiscovery();
        return;
      }
      // Going back to research — just view it (read-only)
      setViewingStage(stage);
      workflowSession.setActiveStage(stage);
    }
  };

  // Revert from drafting back to discovery
  const handleRevertToDiscovery = async () => {
    if (!workflow.threadId) return;
    try {
      const response = await fetch(
        `/api/optimize/${workflow.threadId}/discovery/revert`,
        { method: "POST", headers: { "Content-Type": "application/json" } }
      );
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to revert to discovery");
      }
      setViewingStage(null);
      setDiscoveryDone(false);
      await workflow.refreshStatus();
    } catch (error) {
      console.error("Failed to revert to discovery:", error);
    }
  };

  // Return to current workflow step (exit viewing mode)
  const handleReturnToCurrentStep = () => {
    setViewingStage(null);
    const currentWorkflowStage = mapStepToStage(workflow.currentStep);
    workflowSession.setActiveStage(currentWorkflowStage);
  };

  // Go back from Export to Drafting to make corrections
  const handleGoBackToDrafting = async () => {
    if (!workflow.threadId) return;

    // Immediately hide completion screen, show editor, prevent useEffect from re-showing completion
    userRequestedEditRef.current = true;
    setShowCompletionScreen(false);
    setStepOverride("editor");
    setViewingStage(null);

    // Clear the export storage for this thread
    if (typeof window !== "undefined") {
      localStorage.removeItem("resume_agent:export_session");
    }

    try {
      const response = await fetch(
        `/api/optimize/${workflow.threadId}/drafting/revert`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        console.error("Failed to revert to drafting:", error);
      }

      // Refresh workflow status to get updated state from backend
      await workflow.refreshStatus();
    } catch (error) {
      console.error("Error reverting to drafting:", error);
    }
  };

  // Calculate completed stages for error recovery
  const getCompletedStages = (): WorkflowStage[] => {
    if (!workflowSession.session) return [];
    const stages: WorkflowStage[] = [];
    if (workflowSession.session.researchComplete) stages.push("research");
    if (workflowSession.session.discoveryConfirmed) stages.push("discovery");
    if (workflowSession.session.draftApproved) stages.push("drafting");
    if (workflowSession.session.exportComplete) stages.push("export");
    return stages;
  };

  // Build download links for completion screen
  const getDownloadLinks = () => {
    if (!workflow.threadId) return [];
    return [
      { format: "pdf", label: "Resume (PDF)", url: `/api/optimize/${workflow.threadId}/export/download/pdf` },
      { format: "docx", label: "Resume (Word)", url: `/api/optimize/${workflow.threadId}/export/download/docx` },
      { format: "txt", label: "Resume (Plain Text)", url: `/api/optimize/${workflow.threadId}/export/download/txt` },
      { format: "json", label: "Data Export (JSON)", url: `/api/optimize/${workflow.threadId}/export/download/json` },
    ];
  };

  // Save research data (profile/job) to backend
  const saveResearchData = async (data: { user_profile?: Record<string, unknown>; job_posting?: Record<string, unknown> }) => {
    if (!workflow.threadId) return;
    try {
      const response = await fetch(`/api/optimize/${workflow.threadId}/research/data`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        console.error("Failed to save research data:", await response.text());
      }
    } catch (error) {
      console.error("Error saving research data:", error);
    }
  };

  // Get stages for stepper
  const getStages = () => {
    if (!workflowSession.session) {
      return {
        research: "active" as const,
        discovery: "locked" as const,
        drafting: "locked" as const,
        export: "locked" as const,
      };
    }
    const stages = { ...workflowSession.session.stages };
    // When discovery is done (skipped or confirmed), override stages immediately
    // so the stepper shows drafting as active before backend polling catches up
    if (discoveryDone) {
      stages.discovery = "completed";
      stages.drafting = "active";
    }
    return stages;
  };

  // Get current stage (for stepper display)
  const getCurrentStage = (): WorkflowStage => {
    // If viewing a completed stage, highlight that in the stepper
    if (viewingStage) return viewingStage;
    // If discovery was just skipped/confirmed, show drafting as active immediately
    // (backend is generating the draft but currentStep hasn't updated yet)
    if (discoveryDone && workflowSession.session?.currentStage === "discovery") return "drafting";
    if (!workflowSession.session) return "research";
    return workflowSession.session.currentStage;
  };

  // Check if we're viewing a completed stage (not the active workflow step)
  const isViewingCompletedStage = (): boolean => {
    return viewingStage !== null;
  };

  // Render a read-only review of a completed stage
  const renderCompletedStageReview = (stage: WorkflowStage) => {
    const currentWorkflowStage = mapStepToStage(workflow.currentStep);

    return (
      <div className="space-y-6">
        {/* Return to current step banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-blue-800">
                  Viewing: {getStageLabel(stage)} (Completed)
                </h3>
                <p className="text-blue-700 text-sm">
                  This stage has been completed. You&apos;re reviewing it in read-only mode.
                </p>
              </div>
            </div>
            <button
              onClick={handleReturnToCurrentStep}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center"
            >
              Return to {getStageLabel(currentWorkflowStage)}
              <svg className="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>
          </div>
        </div>

        {/* Render stage-specific review content */}
        {stage === "research" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Profile Card */}
              {workflow.data.userProfile && (
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                    <svg className="w-5 h-5 mr-2 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    Your Profile
                  </h3>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium text-lg">{workflow.data.userProfile.name}</span>
                      {workflow.data.userProfile.headline && (
                        <p className="text-gray-600">{workflow.data.userProfile.headline}</p>
                      )}
                    </div>
                    {workflow.data.userProfile.experience?.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-2">Experience ({workflow.data.userProfile.experience.length} roles)</p>
                        <ul className="text-sm text-gray-600 space-y-1">
                          {workflow.data.userProfile.experience.slice(0, 3).map((exp, idx) => (
                            <li key={idx}>
                              <span className="font-medium">{exp.position}</span> at {exp.company}
                            </li>
                          ))}
                          {workflow.data.userProfile.experience.length > 3 && (
                            <li className="text-gray-400">+{workflow.data.userProfile.experience.length - 3} more</li>
                          )}
                        </ul>
                      </div>
                    )}
                    {workflow.data.userProfile.skills?.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-2">Skills</p>
                        <div className="flex flex-wrap gap-1">
                          {workflow.data.userProfile.skills.slice(0, 8).map((skill, idx) => (
                            <span key={idx} className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">{skill}</span>
                          ))}
                          {workflow.data.userProfile.skills.length > 8 && (
                            <span className="px-2 py-0.5 text-gray-400 text-xs">+{workflow.data.userProfile.skills.length - 8}</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Job Card */}
              {workflow.data.jobPosting && (
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                    <svg className="w-5 h-5 mr-2 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    Target Job
                  </h3>
                  <div className="space-y-3">
                    <div>
                      <span className="font-medium text-lg">{workflow.data.jobPosting.title}</span>
                      <p className="text-gray-600">at {workflow.data.jobPosting.company_name}</p>
                    </div>
                    {workflow.data.jobPosting.tech_stack?.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-2">Tech Stack</p>
                        <div className="flex flex-wrap gap-1">
                          {workflow.data.jobPosting.tech_stack.map((tech, idx) => (
                            <span key={idx} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">{tech}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {workflow.data.jobPosting.requirements?.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-2">Key Requirements</p>
                        <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
                          {workflow.data.jobPosting.requirements.slice(0, 4).map((req, idx) => (
                            <li key={idx}>{req}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Research Insights (completed stage review) */}
            {workflow.data.research && (
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                    <svg className="w-5 h-5 mr-2 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    Research Insights
                  </h3>
                  <button
                    onClick={() => openResearchReviewModal()}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
                  >
                    Show More
                    <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </button>
                </div>
                <div className="space-y-3">
                  {workflow.data.research.company_overview && (
                    <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                      <p className="text-sm font-medium text-blue-800 mb-1">Company Overview</p>
                      <p className="text-sm text-blue-700">{workflow.data.research.company_overview}</p>
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {workflow.data.research.company_culture && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">Company Culture</p>
                        <p className="text-sm text-gray-600">{workflow.data.research.company_culture}</p>
                      </div>
                    )}
                    {workflow.data.research.company_values && workflow.data.research.company_values.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-2">Company Values</p>
                        <div className="flex flex-wrap gap-1">
                          {workflow.data.research.company_values.map((v, idx) => (
                            <span key={idx} className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">{v}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  {workflow.data.research.similar_profiles && workflow.data.research.similar_profiles.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Similar Profiles</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {workflow.data.research.similar_profiles.slice(0, 3).map((p, idx) => (
                          <div key={idx} className="text-sm border-l-2 border-blue-300 pl-3 py-1">
                            <p className="font-medium text-gray-800">{p.name}</p>
                            <p className="text-xs text-gray-500 truncate">{p.headline}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-center">
                    <button onClick={() => openResearchReviewModal()} className="text-blue-600 hover:text-blue-800 font-medium">
                      View full research report →
                    </button>
                  </p>
                </div>
              </div>
            )}

            {/* Gap Analysis */}
            {workflow.data.gapAnalysis && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Gap Analysis</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="text-sm font-semibold text-green-700 mb-2">Strengths</h4>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {workflow.data.gapAnalysis.strengths?.map((s, idx) => (
                        <li key={idx} className="flex items-start">
                          <span className="text-green-500 mr-2">+</span>{s}
                        </li>
                      ))}
                      {(!workflow.data.gapAnalysis.strengths || workflow.data.gapAnalysis.strengths.length === 0) && (
                        <li className="text-sm text-gray-500 italic">No matching strengths identified</li>
                      )}
                    </ul>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-amber-700 mb-2">Gaps to Address</h4>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {workflow.data.gapAnalysis.gaps?.map((g, idx) => (
                        <li key={idx} className="flex items-start">
                          <span className="text-amber-500 mr-2">!</span>{g}
                        </li>
                      ))}
                      {(!workflow.data.gapAnalysis.gaps || workflow.data.gapAnalysis.gaps.length === 0) && (
                        <li className="text-sm text-gray-500 italic">No gaps identified — strong match!</li>
                      )}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {stage === "discovery" && (
          <div className="space-y-6">
            {/* Discovered Experiences */}
            {workflow.data.discoveredExperiences && workflow.data.discoveredExperiences.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <svg className="w-5 h-5 mr-2 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Discovered Experiences ({workflow.data.discoveredExperiences.length})
                </h3>
                <div className="space-y-3">
                  {workflow.data.discoveredExperiences.map((exp, idx) => (
                    <div key={idx} className="p-4 bg-green-50 border border-green-200 rounded-lg">
                      <p className="text-gray-800 mb-2">{exp.description}</p>
                      {exp.mapped_requirements?.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {exp.mapped_requirements.map((req, ridx) => (
                            <span key={ridx} className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">{req}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Discovery Conversation Summary */}
            {workflow.data.discoveryMessages && workflow.data.discoveryMessages.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Discovery Conversation</h3>
                <p className="text-sm text-gray-600 mb-4">
                  {workflow.data.discoveryExchanges} exchanges completed
                </p>
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {workflow.data.discoveryMessages.slice(-6).map((msg, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg ${
                        msg.role === "assistant"
                          ? "bg-gray-100 ml-0 mr-8"
                          : "bg-blue-50 ml-8 mr-0"
                      }`}
                    >
                      <p className="text-xs text-gray-500 mb-1">
                        {msg.role === "assistant" ? "AI" : "You"}
                      </p>
                      <p className="text-sm text-gray-700">{msg.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {stage === "drafting" && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <svg className="w-5 h-5 mr-2 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Draft Resume Preview
            </h3>
            {workflow.data.resumeHtml ? (
              <div
                className="prose prose-sm max-w-none border border-gray-200 rounded-lg p-4 bg-gray-50"
                dangerouslySetInnerHTML={{ __html: workflow.data.resumeHtml }}
              />
            ) : (
              <p className="text-gray-600">Resume draft content is available in the editor.</p>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderCurrentStep = () => {
    // If viewing a completed stage, show read-only review
    if (viewingStage !== null) {
      return renderCompletedStageReview(viewingStage);
    }

    // Show completion screen if workflow is done
    if (showCompletionScreen) {
      return (
        <CompletionScreen
          downloads={getDownloadLinks()}
          onStartNew={handleStartNewClick}
          onGoBackToEdit={handleGoBackToDrafting}
          atsScore={exportStorage.session?.atsReport?.keyword_match_score}
          atsReport={exportStorage.session?.atsReport}
          linkedinOptimized={true}
          threadId={workflow.threadId || undefined}
          jobTitle={workflow.data.jobPosting?.title}
          companyName={workflow.data.jobPosting?.company_name}
          resumePreviewHtml={workflow.data.resumeHtml ?? undefined}
        />
      );
    }

    // Show error recovery if in error state
    if (workflow.currentStep === "error" || workflowSession.session?.lastError) {
      return (
        <ErrorRecovery
          error={workflowSession.session?.lastError || workflow.errors[0] || "An error occurred"}
          errorStage={workflowSession.session?.errorStage || null}
          completedStages={getCompletedStages()}
          onRetry={handleRetry}
          onStartFresh={handleStartFreshFromError}
          onPasteResume={handlePasteResume}
        />
      );
    }

    // Show research review screen - pause before Discovery to let user review
    if (showResearchReview && workflow.data.userProfile && workflow.data.jobPosting && workflow.data.gapAnalysis) {
      return (
        <div className="space-y-6">
          {/* Success Banner */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center space-x-3">
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-green-800">Research Complete!</h3>
                <p className="text-green-700 text-sm">Review the information below before continuing to Discovery.</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Profile Card - Full Details */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                  <svg className="w-5 h-5 mr-2 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  Your Profile
                </h3>
                <button
                  onClick={() => setProfileModalOpen(true)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
                >
                  Show More
                  <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </button>
              </div>
              <div className="space-y-3">
                <div>
                  <span className="font-medium text-lg">{workflow.data.userProfile.name}</span>
                  {workflow.data.userProfile.headline && (
                    <p className="text-gray-600">{workflow.data.userProfile.headline}</p>
                  )}
                </div>
                {workflow.data.userProfile.experience?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Experience ({workflow.data.userProfile.experience.length} roles)</p>
                    <ul className="text-sm text-gray-600 space-y-2">
                      {workflow.data.userProfile.experience.slice(0, 5).map((exp, idx) => (
                        <li key={idx} className="border-l-2 border-indigo-200 pl-3">
                          <span className="font-medium">{exp.position}</span> at {exp.company}
                          {exp.start_date && <span className="text-gray-400 text-xs ml-1">({exp.start_date} - {exp.end_date || 'Present'})</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {workflow.data.userProfile.skills?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Skills ({workflow.data.userProfile.skills.length})</p>
                    <div className="flex flex-wrap gap-1">
                      {workflow.data.userProfile.skills.slice(0, 12).map((skill, idx) => (
                        <span key={idx} className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">{skill}</span>
                      ))}
                      {workflow.data.userProfile.skills.length > 12 && (
                        <span className="px-2 py-0.5 text-gray-400 text-xs">+{workflow.data.userProfile.skills.length - 12} more</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Job Card - Full Details */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                  <svg className="w-5 h-5 mr-2 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  Target Job
                </h3>
                <button
                  onClick={() => setJobModalOpen(true)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
                >
                  Show More
                  <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </button>
              </div>
              <div className="space-y-3">
                <div>
                  <span className="font-medium text-lg">{workflow.data.jobPosting.title}</span>
                  {workflow.data.jobPosting.location && (
                    <p className="text-gray-500 text-sm">{workflow.data.jobPosting.location}</p>
                  )}
                </div>
                {workflow.data.jobPosting.tech_stack?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Tech Stack</p>
                    <div className="flex flex-wrap gap-1">
                      {workflow.data.jobPosting.tech_stack.map((tech, idx) => (
                        <span key={idx} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">{tech}</span>
                      ))}
                    </div>
                  </div>
                )}
                {workflow.data.jobPosting.requirements?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Key Requirements</p>
                    <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
                      {workflow.data.jobPosting.requirements.slice(0, 5).map((req, idx) => (
                        <li key={idx}>{req}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Gap Analysis - Prominent Display */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <svg className="w-5 h-5 mr-2 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Gap Analysis
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-green-700 mb-2 flex items-center">
                    <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Your Strengths
                  </h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    {workflow.data.gapAnalysis.strengths?.map((s, idx) => (
                      <li key={idx} className="flex items-start">
                        <span className="text-green-500 mr-2">+</span>
                        {s}
                      </li>
                    ))}
                    {(!workflow.data.gapAnalysis.strengths || workflow.data.gapAnalysis.strengths.length === 0) && (
                      <li className="text-sm text-gray-500 italic">No matching strengths identified</li>
                    )}
                  </ul>
                </div>
                {workflow.data.gapAnalysis.transferable_skills?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-blue-700 mb-2">Transferable Skills</h4>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {workflow.data.gapAnalysis.transferable_skills.map((s, idx) => (
                        <li key={idx} className="flex items-start">
                          <span className="text-blue-500 mr-2">→</span>
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-amber-700 mb-2 flex items-center">
                    <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    Gaps to Address
                  </h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    {workflow.data.gapAnalysis.gaps?.map((g, idx) => (
                      <li key={idx} className="flex items-start">
                        <span className="text-amber-500 mr-2">!</span>
                        {g}
                      </li>
                    ))}
                    {(!workflow.data.gapAnalysis.gaps || workflow.data.gapAnalysis.gaps.length === 0) && (
                      <li className="text-sm text-gray-500 italic">No gaps identified — strong match!</li>
                    )}
                  </ul>
                </div>
                {workflow.data.gapAnalysis.keywords_to_include?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-purple-700 mb-2">Keywords to Include</h4>
                    <div className="flex flex-wrap gap-1">
                      {workflow.data.gapAnalysis.keywords_to_include.slice(0, 10).map((k, idx) => (
                        <span key={idx} className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">{k}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Research Insights */}
          {workflow.data.research && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                  <svg className="w-5 h-5 mr-2 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  Research Insights
                </h3>
                <button
                  onClick={() => openResearchReviewModal()}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
                >
                  Show More
                  <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                {/* Company Overview */}
                {workflow.data.research.company_overview && (
                  <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                    <p className="text-sm font-medium text-blue-800 mb-1">Company Overview</p>
                    <p className="text-sm text-blue-700">{workflow.data.research.company_overview}</p>
                  </div>
                )}

                {/* Culture + Values row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {workflow.data.research.company_culture && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-1">Company Culture</p>
                      <p className="text-sm text-gray-600">{workflow.data.research.company_culture}</p>
                    </div>
                  )}
                  {workflow.data.research.company_values && workflow.data.research.company_values.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Company Values</p>
                      <div className="flex flex-wrap gap-1">
                        {workflow.data.research.company_values.map((v, idx) => (
                          <span key={idx} className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">{v}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Tech Stack */}
                {workflow.data.research.tech_stack_details && workflow.data.research.tech_stack_details.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Tech Stack</p>
                    <div className="flex flex-wrap gap-2">
                      {workflow.data.research.tech_stack_details.slice(0, 8).map((tech, idx) => (
                        <span key={idx} className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded border border-gray-200">
                          {tech.technology}
                        </span>
                      ))}
                      {workflow.data.research.tech_stack_details.length > 8 && (
                        <button onClick={() => openResearchReviewModal("section-tech-stack")} className="px-2 py-1 text-xs text-blue-600 hover:text-blue-800">
                          +{workflow.data.research.tech_stack_details.length - 8} more
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* Similar Profiles */}
                {workflow.data.research.similar_profiles && workflow.data.research.similar_profiles.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Similar Profiles at Company</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {workflow.data.research.similar_profiles.slice(0, 4).map((p, idx) => (
                        <div key={idx} className="text-sm border-l-2 border-blue-300 pl-3 py-1">
                          <p className="font-medium text-gray-800">{p.name}</p>
                          <p className="text-xs text-gray-500 truncate">{p.headline}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Hiring Patterns + Company News */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {workflow.data.research.hiring_patterns && (
                    <div className="bg-amber-50/50 p-3 rounded-lg border border-amber-100">
                      <p className="text-sm font-medium text-amber-800 mb-1">Hiring Patterns</p>
                      <p className="text-xs text-amber-700">{workflow.data.research.hiring_patterns}</p>
                    </div>
                  )}
                  {workflow.data.research.company_news && workflow.data.research.company_news.length > 0 && (
                    <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                      <p className="text-sm font-medium text-gray-700 mb-2">Recent News</p>
                      <ul className="text-xs text-gray-600 space-y-1">
                        {workflow.data.research.company_news.slice(0, 3).map((news, idx) => (
                          <li key={idx} className="flex items-start">
                            <span className="text-gray-400 mr-1.5">•</span>
                            <span className="line-clamp-2">{news}</span>
                          </li>
                        ))}
                        {workflow.data.research.company_news.length > 3 && (
                          <li>
                            <button onClick={() => openResearchReviewModal("section-company-news")} className="text-blue-600 hover:text-blue-800 ml-3">
                              +{workflow.data.research.company_news.length - 3} more
                            </button>
                          </li>
                        )}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Hiring Criteria + Ideal Profile previews */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {workflow.data.research.hiring_criteria && (
                    <div className="bg-amber-50/50 p-3 rounded-lg border border-amber-200">
                      <p className="text-sm font-medium text-amber-800 mb-1">Hiring Criteria</p>
                      {workflow.data.research.hiring_criteria.must_haves && workflow.data.research.hiring_criteria.must_haves.length > 0 && (
                        <ul className="text-xs text-gray-600 space-y-0.5">
                          {workflow.data.research.hiring_criteria.must_haves.slice(0, 3).map((item, idx) => (
                            <li key={idx} className="flex items-start">
                              <span className="text-red-400 mr-1">•</span>
                              <span className="line-clamp-1">{item}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      <button onClick={() => openResearchReviewModal("section-hiring-criteria")} className="text-xs text-blue-600 hover:text-blue-800 mt-1">
                        View full criteria →
                      </button>
                    </div>
                  )}
                  {workflow.data.research.ideal_profile && (
                    <div className="bg-green-50/50 p-3 rounded-lg border border-green-200">
                      <p className="text-sm font-medium text-green-800 mb-1">Ideal Profile</p>
                      {workflow.data.research.ideal_profile.headline && (
                        <p className="text-xs text-gray-700 bg-white rounded px-2 py-1 border border-green-100 line-clamp-2">
                          {workflow.data.research.ideal_profile.headline}
                        </p>
                      )}
                      <button onClick={() => openResearchReviewModal("section-ideal-profile")} className="text-xs text-blue-600 hover:text-blue-800 mt-1">
                        View full profile →
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Research Review Modal */}
          {workflow.data.research && (
            <ResearchModal
              isOpen={researchReviewModalOpen}
              onClose={closeResearchReviewModal}
              research={workflow.data.research}
              gapAnalysis={workflow.data.gapAnalysis}
              scrollToSection={researchReviewSection}
            />
          )}

          {/* Continue Button */}
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-6 text-center">
            <p className="text-indigo-800 mb-4">
              Ready to continue? In the Discovery phase, we&apos;ll ask you questions to uncover additional experiences that can help address the gaps identified above.
            </p>
            <button
              onClick={handleContinueToDiscovery}
              className="px-8 py-3 bg-indigo-600 text-white rounded-lg font-semibold hover:bg-indigo-700 transition-colors inline-flex items-center"
            >
              Continue to Discovery
              <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>
          </div>

          {/* Profile Markdown Modal */}
          <ProfileEditorModal
            isOpen={profileModalOpen}
            onClose={() => setProfileModalOpen(false)}
            title="Your Profile"
            markdown={editedProfileMarkdown || workflow.data.profileMarkdown}
            onSave={(updatedMarkdown) => {
              setEditedProfileMarkdown(updatedMarkdown);
              if (workflow.threadId) {
                clientMemory.saveProfileEdit(workflow.threadId, updatedMarkdown);
              }
              setProfileModalOpen(false);
            }}
          />

          {/* Job Markdown Modal */}
          <ProfileEditorModal
            isOpen={jobModalOpen}
            onClose={() => setJobModalOpen(false)}
            title="Target Job"
            markdown={editedJobMarkdown || workflow.data.jobMarkdown}
            onSave={(updatedMarkdown) => {
              setEditedJobMarkdown(updatedMarkdown);
              if (workflow.threadId) {
                clientMemory.saveJobEdit(workflow.threadId, updatedMarkdown);
              }
              setJobModalOpen(false);
            }}
          />
        </div>
      );
    }

    // Show loading state when auto-starting
    if (isAutoStarting) {
      return (
        <div className="max-w-2xl mx-auto text-center py-20">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 rounded-full mb-6">
            <svg className="animate-spin h-8 w-8 text-indigo-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Starting Optimization</h2>
          <p className="text-gray-600">Analyzing your profile and job posting...</p>
        </div>
      );
    }

    // If no workflow started and not recovering, redirect to home
    if (!workflow.threadId || workflow.status === "idle") {
      if (!workflowSession.existingSession && !showRecoveryModal && hasCheckedPending) {
        return (
          <div className="max-w-2xl mx-auto text-center py-20">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-6">
              <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">No Active Workflow</h2>
            <p className="text-gray-600 mb-6">Start a new optimization from the home page.</p>
            <Link
              href="/"
              className="inline-flex items-center px-6 py-3 bg-indigo-600 text-white rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
            >
              Go to Home
              <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
          </div>
        );
      }
      return (
        <div className="max-w-2xl mx-auto text-center py-20">
          <div className="animate-pulse">
            <div className="h-16 w-16 bg-gray-200 rounded-full mx-auto mb-6" />
            <div className="h-6 bg-gray-200 rounded w-48 mx-auto mb-2" />
            <div className="h-4 bg-gray-200 rounded w-64 mx-auto" />
          </div>
        </div>
      );
    }

    // Show step based on current workflow step (stepOverride takes priority)
    const effectiveStep = stepOverride || workflow.currentStep;
    switch (effectiveStep) {
      case "ingest":
      case "research":
      case "analysis":
        return (
          <ResearchStep
            currentStep={workflow.currentStep}
            userProfile={workflow.data.userProfile}
            jobPosting={workflow.data.jobPosting}
            profileMarkdown={workflow.data.profileMarkdown}
            jobMarkdown={workflow.data.jobMarkdown}
            research={workflow.data.research}
            gapAnalysis={workflow.data.gapAnalysis}
            progressMessages={workflow.data.progressMessages}
          />
        );

      case "discovery":
        // If discovery is confirmed/skipped but we're still on discovery step,
        // show a loading state as draft is being generated.
        // Check both backend state AND local session state (local updates immediately on skip/confirm)
        if (workflow.data.discoveryConfirmed || workflowSession.session?.discoveryConfirmed || discoveryDone) {
          return (
            <div className="flex flex-col items-center justify-center min-h-[400px] space-y-6">
              <div className="relative">
                <div className="w-16 h-16 border-4 border-purple-200 rounded-full"></div>
                <div className="absolute top-0 left-0 w-16 h-16 border-4 border-purple-600 rounded-full animate-spin border-t-transparent"></div>
              </div>
              <div className="text-center space-y-2">
                <h3 className="text-xl font-semibold text-gray-900">
                  Generating Your Tailored Resume
                </h3>
                <p className="text-gray-600 max-w-md">
                  Our AI is crafting a personalized resume based on your profile and the target job.
                  This typically takes 30-60 seconds.
                </p>
              </div>
              <div className="flex items-center space-x-2 text-sm text-gray-500">
                <svg className="w-4 h-4 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                </svg>
                <span>Please wait...</span>
              </div>
            </div>
          );
        }
        return (
          <DiscoveryStep
            threadId={workflow.threadId || ""}
            gapAnalysis={workflow.data.gapAnalysis}
            discoveryPrompts={workflow.data.discoveryPrompts}
            discoveryMessages={workflow.data.discoveryMessages}
            discoveredExperiences={workflow.data.discoveredExperiences}
            discoveryConfirmed={workflow.data.discoveryConfirmed}
            discoveryExchanges={workflow.data.discoveryExchanges}
            discoveryAgenda={workflow.data.discoveryAgenda}
            pendingQuestion={workflow.pendingQuestion}
            onSubmitAnswer={workflow.submitAnswer}
            research={workflow.data.research}
            interruptPayload={workflow.interruptPayload as {
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
            } | null}
            profileMarkdown={editedProfileMarkdown || workflow.data.profileMarkdown}
            jobMarkdown={editedJobMarkdown || workflow.data.jobMarkdown}
            onDiscoveryDone={() => setDiscoveryDone(true)}
          />
        );

      case "qa":
        return (
          <QAChat
            qaHistory={workflow.data.qaHistory}
            pendingQuestion={workflow.pendingQuestion}
            qaRound={workflow.qaRound}
            onSubmitAnswer={workflow.submitAnswer}
            gapAnalysis={workflow.data.gapAnalysis}
          />
        );

      case "draft":
        // Show a dedicated drafting loading state
        return (
          <div className="flex flex-col items-center justify-center min-h-[400px] space-y-6">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-purple-200 rounded-full"></div>
              <div className="absolute top-0 left-0 w-16 h-16 border-4 border-purple-600 rounded-full animate-spin border-t-transparent"></div>
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-xl font-semibold text-gray-900">
                Creating Your Resume Draft
              </h3>
              <p className="text-gray-600 max-w-md">
                The AI is writing a tailored resume that highlights your strengths
                and aligns with the job requirements.
              </p>
            </div>
            {workflow.data.progressMessages && workflow.data.progressMessages.length > 0 && (
              <div className="bg-gray-50 rounded-lg p-4 max-w-md w-full">
                <p className="text-sm text-gray-600">
                  {workflow.data.progressMessages[workflow.data.progressMessages.length - 1]?.message || "Processing..."}
                </p>
              </div>
            )}
          </div>
        );

      case "editor":
        return (
          <ResumeEditor
            threadId={workflow.threadId}
            initialContent={workflow.data.resumeHtml || ""}
            jobPosting={workflow.data.jobPosting}
            gapAnalysis={workflow.data.gapAnalysis}
            onSave={workflow.updateResume}
            onApprove={async () => {
              await workflow.submitAnswer("approve");
            }}
          />
        );

      case "completed":
        return (
          <ExportStep
            threadId={workflow.threadId}
            draftApproved={true}
            onComplete={() => setShowCompletionScreen(true)}
            onGoBackToDrafting={handleGoBackToDrafting}
          />
        );

      default:
        return <div>Loading...</div>;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Session Recovery Modal */}
      {showRecoveryModal && workflowSession.existingSession && (
        <SessionRecoveryModal
          session={workflowSession.existingSession}
          onResume={handleResumeSession}
          onStartFresh={handleStartFresh}
        />
      )}

      {/* Start New Session Dialog */}
      {showStartNewDialog && (
        <StartNewSessionDialog
          onConfirm={handleConfirmStartNew}
          onCancel={() => setShowStartNewDialog(false)}
        />
      )}

      {/* Header */}
      <header className="bg-white border-b px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Resume Optimizer
            </h1>
            <p className="text-sm text-gray-500">
              AI-powered resume tailoring for your target job
            </p>
          </div>
          {(workflow.threadId || workflowSession.session) && (
            <button
              onClick={handleStartNewClick}
              className="text-sm text-gray-500 hover:text-gray-700 flex items-center"
            >
              <svg
                className="w-4 h-4 mr-1"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Start New
            </button>
          )}
        </div>
      </header>

      {/* Workflow Stepper - 4 stages */}
      {(workflow.threadId || workflowSession.session) && !showCompletionScreen && (
        <div className="bg-white border-b px-6 py-4">
          <div className="max-w-3xl mx-auto">
            <WorkflowStepper
              stages={getStages()}
              currentStage={getCurrentStage()}
              onStageClick={handleStageClick}
            />
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {renderCurrentStep()}
      </main>
    </div>
  );
}
