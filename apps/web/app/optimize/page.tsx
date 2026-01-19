"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useWorkflow } from "../hooks/useWorkflow";
import { useWorkflowSession, WorkflowStage } from "../hooks/useWorkflowSession";
import { usePreferences } from "../hooks/usePreferences";
import { useExportStorage } from "../hooks/useExportStorage";
import WorkflowStepper from "../components/optimize/WorkflowStepper";
import SessionRecoveryModal from "../components/optimize/SessionRecoveryModal";
import StartNewSessionDialog from "../components/optimize/StartNewSessionDialog";
import ErrorRecovery from "../components/optimize/ErrorRecovery";
import ResearchStep from "../components/optimize/ResearchStep";
import DiscoveryStep from "../components/optimize/DiscoveryStep";
import QAChat from "../components/optimize/QAChat";
import ResumeEditor from "../components/optimize/ResumeEditor";
import ExportStep from "../components/optimize/ExportStep";
import CompletionScreen from "../components/optimize/CompletionScreen";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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

  const [inputData, setInputData] = useState<{
    linkedinUrl?: string;
    jobUrl?: string;
    resumeText?: string;
    jobText?: string;
  }>({});

  // Dialog states
  const [showRecoveryModal, setShowRecoveryModal] = useState(false);
  const [showStartNewDialog, setShowStartNewDialog] = useState(false);
  const [showCompletionScreen, setShowCompletionScreen] = useState(false);
  const [isAutoStarting, setIsAutoStarting] = useState(false);
  const [hasCheckedPending, setHasCheckedPending] = useState(false);

  // Research review state - pause before Discovery to let user review results
  const [showResearchReview, setShowResearchReview] = useState(false);
  const [hasAcknowledgedResearch, setHasAcknowledgedResearch] = useState(false);

  // Modal states for viewing/editing profile and job
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [jobModalOpen, setJobModalOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<typeof workflow.data.userProfile | null>(null);
  const [editingJob, setEditingJob] = useState<typeof workflow.data.jobPosting | null>(null);

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
              preferences
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
  }, [hasCheckedPending, workflow, workflowSession]);

  // Check for existing session on mount
  useEffect(() => {
    if (!workflowSession.isLoading && workflowSession.existingSession) {
      // Show recovery modal if there's an existing session
      setShowRecoveryModal(true);
    }
  }, [workflowSession.isLoading, workflowSession.existingSession]);

  // Sync session state from workflow status
  useEffect(() => {
    if (workflow.threadId && workflowSession.session) {
      // Map workflow status to session
      const currentStage = mapStepToStage(workflow.currentStep);

      // Update session based on workflow progress
      workflowSession.syncFromBackend({
        current_step: workflow.currentStep,
        research_complete: ["discovery", "qa", "draft", "editor", "completed"].includes(workflow.currentStep),
        discovery_confirmed: workflow.data.discoveryConfirmed,
        draft_approved: ["completed"].includes(workflow.currentStep),
        export_complete: workflow.currentStep === "completed" && workflow.status === "completed",
      });

      // Show completion screen when workflow is done
      if (workflow.currentStep === "completed" && workflow.status === "completed") {
        setShowCompletionScreen(true);
      }
    }
  }, [workflow.threadId, workflow.currentStep, workflow.status, workflow.data.discoveryConfirmed]);

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
    setInputData({});
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
    setInputData({});
  };

  // Handle error recovery
  const handleRetry = () => {
    workflowSession.retryFromError();
    // Workflow will continue from last known state
    workflow.refreshStatus();
  };

  const handleStartFreshFromError = () => {
    workflowSession.startFreshFromError();
  };

  // Handle stage click in stepper
  const handleStageClick = (stage: WorkflowStage) => {
    if (!workflowSession.canAccessStage(stage)) {
      // Redirect to earliest incomplete stage
      const targetStage = workflowSession.getEarliestIncompleteStage();
      console.log(`Cannot access ${stage}, redirecting to ${targetStage}`);
      return;
    }

    workflowSession.setActiveStage(stage);
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
      { format: "pdf", label: "Resume (PDF)", url: `${API_URL}/api/optimize/${workflow.threadId}/export/download/pdf` },
      { format: "docx", label: "Resume (Word)", url: `${API_URL}/api/optimize/${workflow.threadId}/export/download/docx` },
      { format: "txt", label: "Resume (Plain Text)", url: `${API_URL}/api/optimize/${workflow.threadId}/export/download/txt` },
      { format: "json", label: "Data Export (JSON)", url: `${API_URL}/api/optimize/${workflow.threadId}/export/download/json` },
    ];
  };

  // Save research data (profile/job) to backend
  const saveResearchData = async (data: { user_profile?: Record<string, unknown>; job_posting?: Record<string, unknown> }) => {
    if (!workflow.threadId) return;
    try {
      const response = await fetch(`${API_URL}/api/optimize/${workflow.threadId}/research/data`, {
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
    return workflowSession.session.stages;
  };

  // Get current stage
  const getCurrentStage = (): WorkflowStage => {
    if (!workflowSession.session) return "research";
    return workflowSession.session.currentStage;
  };

  const renderCurrentStep = () => {
    // Show completion screen if workflow is done
    if (showCompletionScreen) {
      return (
        <CompletionScreen
          downloads={getDownloadLinks()}
          onStartNew={handleStartNewClick}
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
                  onClick={() => {
                    setEditingProfile(JSON.parse(JSON.stringify(workflow.data.userProfile)));
                    setProfileModalOpen(true);
                  }}
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
                  onClick={() => {
                    setEditingJob(JSON.parse(JSON.stringify(workflow.data.jobPosting)));
                    setJobModalOpen(true);
                  }}
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
                  <p className="text-gray-600">at {workflow.data.jobPosting.company_name}</p>
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
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <svg className="w-5 h-5 mr-2 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Research Insights
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {workflow.data.research.company_culture && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-1">Company Culture</p>
                    <p className="text-sm text-gray-600">{workflow.data.research.company_culture.slice(0, 300)}...</p>
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
            </div>
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

          {/* Profile Edit Modal */}
          {profileModalOpen && editingProfile && (
            <div className="fixed inset-0 z-50 overflow-y-auto">
              <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center">
                <div
                  className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
                  onClick={() => setProfileModalOpen(false)}
                />
                <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[85vh] flex flex-col">
                  <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">Your Profile - Full Details</h3>
                    <button onClick={() => setProfileModalOpen(false)} className="text-gray-400 hover:text-gray-500">
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
                    {/* Basic Info */}
                    <div className="space-y-4">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Basic Information</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                          <input
                            type="text"
                            value={editingProfile.name || ""}
                            onChange={(e) => setEditingProfile({...editingProfile, name: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                          <input
                            type="email"
                            value={editingProfile.email || ""}
                            onChange={(e) => setEditingProfile({...editingProfile, email: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                          <input
                            type="text"
                            value={editingProfile.phone || ""}
                            onChange={(e) => setEditingProfile({...editingProfile, phone: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                          <input
                            type="text"
                            value={editingProfile.location || ""}
                            onChange={(e) => setEditingProfile({...editingProfile, location: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Headline</label>
                        <input
                          type="text"
                          value={editingProfile.headline || ""}
                          onChange={(e) => setEditingProfile({...editingProfile, headline: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Summary</label>
                        <textarea
                          value={editingProfile.summary || ""}
                          onChange={(e) => setEditingProfile({...editingProfile, summary: e.target.value})}
                          rows={3}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>

                    {/* Experience */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between border-b pb-2">
                        <h4 className="font-medium text-gray-900">Experience ({editingProfile.experience?.length || 0})</h4>
                        <button
                          onClick={() => setEditingProfile({
                            ...editingProfile,
                            experience: [...(editingProfile.experience || []), { company: "", position: "", is_current: false, achievements: [], technologies: [] }]
                          })}
                          className="text-sm text-blue-600 hover:text-blue-800"
                        >
                          + Add Role
                        </button>
                      </div>
                      {editingProfile.experience?.map((exp, idx) => (
                        <div key={idx} className="bg-gray-50 rounded-lg p-4 space-y-3">
                          <div className="flex justify-between items-start">
                            <span className="text-sm font-medium text-gray-500">Role {idx + 1}</span>
                            <button
                              onClick={() => setEditingProfile({
                                ...editingProfile,
                                experience: editingProfile.experience?.filter((_, i) => i !== idx)
                              })}
                              className="text-red-500 hover:text-red-700 text-sm"
                            >
                              Remove
                            </button>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">Company</label>
                              <input
                                type="text"
                                value={exp.company}
                                onChange={(e) => {
                                  const newExp = [...(editingProfile.experience || [])];
                                  newExp[idx] = {...exp, company: e.target.value};
                                  setEditingProfile({...editingProfile, experience: newExp});
                                }}
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">Position</label>
                              <input
                                type="text"
                                value={exp.position}
                                onChange={(e) => {
                                  const newExp = [...(editingProfile.experience || [])];
                                  newExp[idx] = {...exp, position: e.target.value};
                                  setEditingProfile({...editingProfile, experience: newExp});
                                }}
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">Start Date</label>
                              <input
                                type="text"
                                value={exp.start_date || ""}
                                onChange={(e) => {
                                  const newExp = [...(editingProfile.experience || [])];
                                  newExp[idx] = {...exp, start_date: e.target.value};
                                  setEditingProfile({...editingProfile, experience: newExp});
                                }}
                                placeholder="e.g., Jan 2020"
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">End Date</label>
                              <input
                                type="text"
                                value={exp.end_date || ""}
                                onChange={(e) => {
                                  const newExp = [...(editingProfile.experience || [])];
                                  newExp[idx] = {...exp, end_date: e.target.value};
                                  setEditingProfile({...editingProfile, experience: newExp});
                                }}
                                placeholder="Present or e.g., Dec 2023"
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="block text-xs text-gray-600 mb-1">Achievements (one per line)</label>
                            <textarea
                              value={exp.achievements?.join("\n") || ""}
                              onChange={(e) => {
                                const newExp = [...(editingProfile.experience || [])];
                                newExp[idx] = {...exp, achievements: e.target.value.split("\n").filter(a => a.trim())};
                                setEditingProfile({...editingProfile, experience: newExp});
                              }}
                              rows={2}
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Skills */}
                    <div className="space-y-3">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Skills</h4>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Enter skills separated by commas</label>
                        <textarea
                          value={editingProfile.skills?.join(", ") || ""}
                          onChange={(e) => setEditingProfile({
                            ...editingProfile,
                            skills: e.target.value.split(",").map(s => s.trim()).filter(s => s)
                          })}
                          rows={2}
                          placeholder="Python, JavaScript, Project Management..."
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>

                    {/* Education */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between border-b pb-2">
                        <h4 className="font-medium text-gray-900">Education ({editingProfile.education?.length || 0})</h4>
                        <button
                          onClick={() => setEditingProfile({
                            ...editingProfile,
                            education: [...(editingProfile.education || []), { institution: "" }]
                          })}
                          className="text-sm text-blue-600 hover:text-blue-800"
                        >
                          + Add Education
                        </button>
                      </div>
                      {editingProfile.education?.map((edu, idx) => (
                        <div key={idx} className="bg-gray-50 rounded-lg p-4 space-y-3">
                          <div className="flex justify-between items-start">
                            <span className="text-sm font-medium text-gray-500">Education {idx + 1}</span>
                            <button
                              onClick={() => setEditingProfile({
                                ...editingProfile,
                                education: editingProfile.education?.filter((_, i) => i !== idx)
                              })}
                              className="text-red-500 hover:text-red-700 text-sm"
                            >
                              Remove
                            </button>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">Institution</label>
                              <input
                                type="text"
                                value={edu.institution}
                                onChange={(e) => {
                                  const newEdu = [...(editingProfile.education || [])];
                                  newEdu[idx] = {...edu, institution: e.target.value};
                                  setEditingProfile({...editingProfile, education: newEdu});
                                }}
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">Degree</label>
                              <input
                                type="text"
                                value={edu.degree || ""}
                                onChange={(e) => {
                                  const newEdu = [...(editingProfile.education || [])];
                                  newEdu[idx] = {...edu, degree: e.target.value};
                                  setEditingProfile({...editingProfile, education: newEdu});
                                }}
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">Field of Study</label>
                              <input
                                type="text"
                                value={edu.field_of_study || ""}
                                onChange={(e) => {
                                  const newEdu = [...(editingProfile.education || [])];
                                  newEdu[idx] = {...edu, field_of_study: e.target.value};
                                  setEditingProfile({...editingProfile, education: newEdu});
                                }}
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">Graduation Year</label>
                              <input
                                type="text"
                                value={edu.end_date || ""}
                                onChange={(e) => {
                                  const newEdu = [...(editingProfile.education || [])];
                                  newEdu[idx] = {...edu, end_date: e.target.value};
                                  setEditingProfile({...editingProfile, education: newEdu});
                                }}
                                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
                    <button
                      onClick={() => setProfileModalOpen(false)}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={async () => {
                        if (editingProfile) {
                          await saveResearchData({ user_profile: { ...editingProfile } });
                        }
                        setProfileModalOpen(false);
                      }}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                    >
                      Save Changes
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Job Edit Modal */}
          {jobModalOpen && editingJob && (
            <div className="fixed inset-0 z-50 overflow-y-auto">
              <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center">
                <div
                  className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
                  onClick={() => setJobModalOpen(false)}
                />
                <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[85vh] flex flex-col">
                  <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">Target Job - Full Details</h3>
                    <button onClick={() => setJobModalOpen(false)} className="text-gray-400 hover:text-gray-500">
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
                    {/* Basic Info */}
                    <div className="space-y-4">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Job Details</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Job Title</label>
                          <input
                            type="text"
                            value={editingJob.title || ""}
                            onChange={(e) => setEditingJob({...editingJob, title: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Company</label>
                          <input
                            type="text"
                            value={editingJob.company_name || ""}
                            onChange={(e) => setEditingJob({...editingJob, company_name: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                          <input
                            type="text"
                            value={editingJob.location || ""}
                            onChange={(e) => setEditingJob({...editingJob, location: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Work Type</label>
                          <input
                            type="text"
                            value={editingJob.work_type || ""}
                            onChange={(e) => setEditingJob({...editingJob, work_type: e.target.value})}
                            placeholder="Remote, Hybrid, On-site"
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                        <textarea
                          value={editingJob.description || ""}
                          onChange={(e) => setEditingJob({...editingJob, description: e.target.value})}
                          rows={4}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>

                    {/* Requirements */}
                    <div className="space-y-3">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Requirements</h4>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Enter requirements (one per line)</label>
                        <textarea
                          value={editingJob.requirements?.join("\n") || ""}
                          onChange={(e) => setEditingJob({
                            ...editingJob,
                            requirements: e.target.value.split("\n").filter(r => r.trim())
                          })}
                          rows={4}
                          placeholder="5+ years experience&#10;Bachelor's degree&#10;Strong communication skills"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>

                    {/* Preferred Qualifications */}
                    <div className="space-y-3">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Preferred Qualifications</h4>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Enter preferred qualifications (one per line)</label>
                        <textarea
                          value={editingJob.preferred_qualifications?.join("\n") || ""}
                          onChange={(e) => setEditingJob({
                            ...editingJob,
                            preferred_qualifications: e.target.value.split("\n").filter(q => q.trim())
                          })}
                          rows={3}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>

                    {/* Tech Stack */}
                    <div className="space-y-3">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Tech Stack</h4>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Enter technologies separated by commas</label>
                        <textarea
                          value={editingJob.tech_stack?.join(", ") || ""}
                          onChange={(e) => setEditingJob({
                            ...editingJob,
                            tech_stack: e.target.value.split(",").map(t => t.trim()).filter(t => t)
                          })}
                          rows={2}
                          placeholder="Python, AWS, Kubernetes, React..."
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>

                    {/* Responsibilities */}
                    <div className="space-y-3">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Responsibilities</h4>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Enter responsibilities (one per line)</label>
                        <textarea
                          value={editingJob.responsibilities?.join("\n") || ""}
                          onChange={(e) => setEditingJob({
                            ...editingJob,
                            responsibilities: e.target.value.split("\n").filter(r => r.trim())
                          })}
                          rows={4}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>

                    {/* Benefits */}
                    <div className="space-y-3">
                      <h4 className="font-medium text-gray-900 border-b pb-2">Benefits</h4>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Enter benefits (one per line)</label>
                        <textarea
                          value={editingJob.benefits?.join("\n") || ""}
                          onChange={(e) => setEditingJob({
                            ...editingJob,
                            benefits: e.target.value.split("\n").filter(b => b.trim())
                          })}
                          rows={3}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
                    <button
                      onClick={() => setJobModalOpen(false)}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={async () => {
                        if (editingJob) {
                          await saveResearchData({ job_posting: { ...editingJob } });
                        }
                        setJobModalOpen(false);
                      }}
                      className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                    >
                      Save Changes
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
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

    // Show step based on current workflow step
    switch (workflow.currentStep) {
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
        return (
          <DiscoveryStep
            threadId={workflow.threadId || ""}
            gapAnalysis={workflow.data.gapAnalysis}
            discoveryPrompts={workflow.data.discoveryPrompts}
            discoveryMessages={workflow.data.discoveryMessages}
            discoveredExperiences={workflow.data.discoveredExperiences}
            discoveryConfirmed={workflow.data.discoveryConfirmed}
            discoveryExchanges={workflow.data.discoveryExchanges}
            pendingQuestion={workflow.pendingQuestion}
            onSubmitAnswer={workflow.submitAnswer}
            interruptPayload={workflow.interruptPayload as {
              message?: string;
              context?: {
                intent?: string;
                related_gaps?: string[];
                prompt_number?: number;
                total_prompts?: number;
              };
            } | null}
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
