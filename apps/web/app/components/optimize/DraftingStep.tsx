"use client";

import { useState, useEffect, useCallback } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Underline from "@tiptap/extension-underline";
import Highlight from "@tiptap/extension-highlight";

import {
  useDraftingStorage,
  DraftingSuggestion,
  DraftVersion,
  DraftValidation,
} from "../../hooks/useDraftingStorage";
import { useSuggestions, useDraftingState } from "../../hooks/useSuggestions";
import { useSuggestionTracking, TrackedSuggestion } from "../../hooks/useSuggestionTracking";
import { useEditTracking } from "../../hooks/useEditTracking";
import { SuggestionList } from "./SuggestionCard";
import VersionHistory from "./VersionHistory";
import PreferenceSidebar from "./PreferenceSidebar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DraftingStepProps {
  threadId: string;
  initialHtml: string;
  suggestions: Array<{
    id: string;
    location: string;
    original_text: string;
    proposed_text: string;
    rationale: string;
    status: string;
    created_at: string;
    resolved_at?: string;
  }>;
  versions: Array<{
    version: string;
    html_content: string;
    trigger: string;
    description: string;
    change_log?: Array<{
      id: string;
      location: string;
      change_type: string;
      original_text?: string;
      new_text?: string;
      suggestion_id?: string;
      timestamp: string;
    }>;
    created_at: string;
  }>;
  currentVersion: string;
  draftApproved: boolean;
  onApprove: () => void;
}

/**
 * Main Drafting step component.
 *
 * Features:
 * - Rich text editor for resume
 * - Suggestion cards with accept/decline
 * - Version history with restore
 * - Auto-save and manual save
 * - Session recovery
 */
export default function DraftingStep({
  threadId,
  initialHtml,
  suggestions: backendSuggestions,
  versions: backendVersions,
  currentVersion: backendCurrentVersion,
  draftApproved,
  onApprove,
}: DraftingStepProps) {
  const storage = useDraftingStorage();
  const { isLoading: suggestionLoading, acceptSuggestion, declineSuggestion } =
    useSuggestions({
      threadId,
      onSuggestionResolved: () => {
        // Refresh state after suggestion action
        fetchDraftingState();
      },
    });
  const {
    isLoading: stateLoading,
    fetchState: fetchDraftingState,
    saveManually,
    restoreVersion,
    approveDraft,
  } = useDraftingState(threadId);

  // Preference tracking hooks
  const { trackAccept, trackReject } = useSuggestionTracking({ threadId });
  const { trackTextChange, flush: flushEdits } = useEditTracking({ threadId });

  const [showRecoveryPrompt, setShowRecoveryPrompt] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Convert backend data to frontend format
  const suggestions: DraftingSuggestion[] = backendSuggestions.map((s) => ({
    id: s.id,
    location: s.location,
    originalText: s.original_text,
    proposedText: s.proposed_text,
    rationale: s.rationale,
    status: s.status as "pending" | "accepted" | "declined",
    createdAt: s.created_at,
    resolvedAt: s.resolved_at,
  }));

  const versions: DraftVersion[] = backendVersions.map((v) => ({
    version: v.version,
    htmlContent: v.html_content,
    trigger: v.trigger as any,
    description: v.description,
    changeLog: [],
    createdAt: v.created_at,
  }));

  const pendingCount = suggestions.filter((s) => s.status === "pending").length;
  const canApprove = pendingCount === 0;

  // Track previous content for edit tracking
  const [previousContent, setPreviousContent] = useState(initialHtml);

  // Initialize Tiptap editor
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Placeholder.configure({
        placeholder: "Your resume content...",
      }),
      Underline,
      Highlight.configure({
        multicolor: true,
      }),
    ],
    content: initialHtml,
    editorProps: {
      attributes: {
        class:
          "prose prose-sm max-w-none focus:outline-none min-h-[500px] px-6 py-4",
      },
    },
    onUpdate: ({ editor }) => {
      // Track text changes for preference learning
      const newText = editor.getText();
      if (previousContent !== newText) {
        trackTextChange(previousContent, newText);
        setPreviousContent(newText);
      }
    },
  });

  // Initialize/check for existing session
  useEffect(() => {
    if (threadId && !storage.session) {
      const existing = storage.checkExistingSession(threadId);
      if (existing) {
        setShowRecoveryPrompt(true);
      } else {
        storage.startSession(threadId, initialHtml, suggestions);
      }
    }
  }, [threadId, storage, initialHtml, suggestions]);

  // Sync from backend when data changes
  useEffect(() => {
    if (storage.session && threadId === storage.session.threadId) {
      storage.syncFromBackend({
        resume_html: initialHtml,
        draft_suggestions: backendSuggestions,
        draft_versions: backendVersions,
        draft_current_version: backendCurrentVersion,
        draft_approved: draftApproved,
      });
    }
  }, [
    storage,
    threadId,
    initialHtml,
    backendSuggestions,
    backendVersions,
    backendCurrentVersion,
    draftApproved,
  ]);

  // Handle suggestion accept
  const handleAccept = async (id: string) => {
    const suggestion = suggestions.find((s) => s.id === id);
    const result = await acceptSuggestion(id);
    if (result) {
      storage.acceptSuggestion(id);
      showSaveMessage(`Applied suggestion (v${result.version})`);

      // Track acceptance for preference learning
      if (suggestion) {
        const tracked: TrackedSuggestion = {
          id: suggestion.id,
          location: suggestion.location,
          original_text: suggestion.originalText,
          proposed_text: suggestion.proposedText,
          rationale: suggestion.rationale,
        };
        trackAccept(tracked);
      }

      // Refresh editor content
      const newState = await fetchDraftingState();
      if (newState?.resume_html && editor) {
        editor.commands.setContent(newState.resume_html);
      }
    }
  };

  // Handle suggestion decline
  const handleDecline = async (id: string) => {
    const suggestion = suggestions.find((s) => s.id === id);
    const result = await declineSuggestion(id);
    if (result) {
      storage.declineSuggestion(id);
      showSaveMessage(`Declined suggestion (v${result.version})`);

      // Track rejection for preference learning
      if (suggestion) {
        const tracked: TrackedSuggestion = {
          id: suggestion.id,
          location: suggestion.location,
          original_text: suggestion.originalText,
          proposed_text: suggestion.proposedText,
          rationale: suggestion.rationale,
        };
        trackReject(tracked);
      }
    }
  };

  // Handle version restore
  const handleRestore = async (version: string) => {
    const result = await restoreVersion(version);
    if (result) {
      storage.restoreVersion(version);
      showSaveMessage(`Restored to v${version} (now v${result.version})`);
      // Refresh editor content
      const newState = await fetchDraftingState();
      if (newState?.resume_html && editor) {
        editor.commands.setContent(newState.resume_html);
      }
    }
  };

  // Handle manual save
  const handleSave = async () => {
    if (!editor) return;

    setIsSaving(true);
    const html = editor.getHTML();

    // Flush pending edit tracking events before saving
    await flushEdits();

    const result = await saveManually(html);
    if (result) {
      storage.manualSave();
      showSaveMessage(result.message || `Saved as v${result.version}`);
    }

    setIsSaving(false);
  };

  // Handle approve
  const handleApprove = async () => {
    if (pendingCount > 0) {
      setValidationErrors([`${pendingCount} suggestions still pending`]);
      return;
    }

    const result = await approveDraft();
    if (result) {
      if (result.success) {
        storage.approveDraft();
        onApprove();
      } else if (result.validation?.errors) {
        setValidationErrors(result.validation.errors);
      }
    }
  };

  // Show save message temporarily
  const showSaveMessage = (message: string) => {
    setSaveMessage(message);
    setTimeout(() => setSaveMessage(null), 3000);
  };

  // Handle session recovery
  const handleResumeSession = () => {
    if (storage.existingSession) {
      storage.resumeSession(storage.existingSession);
      if (editor && storage.existingSession.resumeHtml) {
        editor.commands.setContent(storage.existingSession.resumeHtml);
      }
    }
    setShowRecoveryPrompt(false);
  };

  const handleStartFresh = () => {
    storage.clearSession(threadId);
    storage.startSession(threadId, initialHtml, suggestions);
    setShowRecoveryPrompt(false);
  };

  // Show recovery prompt if we have an existing incomplete session
  if (showRecoveryPrompt && storage.existingSession) {
    return (
      <div className="bg-white rounded-lg shadow p-6 max-w-md mx-auto">
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Resume Editing Session Found
        </h3>
        <p className="text-gray-600 mb-4">
          You have an unsaved drafting session from{" "}
          {new Date(storage.existingSession.updatedAt).toLocaleString()}.
          Would you like to continue where you left off?
        </p>
        <div className="flex space-x-3">
          <button
            onClick={handleResumeSession}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Continue
          </button>
          <button
            onClick={handleStartFresh}
            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded hover:bg-gray-50"
          >
            Start Fresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="drafting-step">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Review & Edit Resume
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Accept or decline suggestions, then approve when ready
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <VersionHistory
            versions={versions}
            currentVersion={backendCurrentVersion}
            onRestore={handleRestore}
            isLoading={stateLoading}
          />
        </div>
      </div>

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <svg
              className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"
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
              <p className="text-red-800 font-medium">Cannot approve draft</p>
              <ul className="text-red-700 text-sm mt-1 space-y-1">
                {validationErrors.map((error, idx) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          </div>
          <button
            onClick={() => setValidationErrors([])}
            className="mt-2 text-sm text-red-600 hover:text-red-800"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Editor Panel */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow overflow-hidden">
            {/* Toolbar */}
            <div className="border-b p-2 flex items-center space-x-1 bg-gray-50">
              <ToolbarButton
                onClick={() => editor?.chain().focus().toggleBold().run()}
                active={editor?.isActive("bold")}
                title="Bold"
              >
                <span className="font-bold">B</span>
              </ToolbarButton>
              <ToolbarButton
                onClick={() => editor?.chain().focus().toggleItalic().run()}
                active={editor?.isActive("italic")}
                title="Italic"
              >
                <span className="italic">I</span>
              </ToolbarButton>
              <ToolbarButton
                onClick={() => editor?.chain().focus().toggleUnderline().run()}
                active={editor?.isActive("underline")}
                title="Underline"
              >
                <span className="underline">U</span>
              </ToolbarButton>

              <div className="w-px h-6 bg-gray-300 mx-2" />

              <ToolbarButton
                onClick={() =>
                  editor?.chain().focus().toggleHeading({ level: 2 }).run()
                }
                active={editor?.isActive("heading", { level: 2 })}
                title="Heading"
              >
                H2
              </ToolbarButton>
              <ToolbarButton
                onClick={() =>
                  editor?.chain().focus().toggleHeading({ level: 3 }).run()
                }
                active={editor?.isActive("heading", { level: 3 })}
                title="Subheading"
              >
                H3
              </ToolbarButton>

              <div className="w-px h-6 bg-gray-300 mx-2" />

              <ToolbarButton
                onClick={() => editor?.chain().focus().toggleBulletList().run()}
                active={editor?.isActive("bulletList")}
                title="Bullet List"
              >
                &bull;
              </ToolbarButton>

              <div className="flex-1" />

              {/* Save message */}
              {saveMessage && (
                <span className="text-sm text-green-600 flex items-center">
                  <svg
                    className="w-4 h-4 mr-1"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                  {saveMessage}
                </span>
              )}

              <button
                onClick={handleSave}
                disabled={isSaving}
                className="px-4 py-1.5 bg-gray-100 text-gray-700 text-sm rounded hover:bg-gray-200 disabled:opacity-50 transition-colors"
              >
                {isSaving ? "Saving..." : "Save Progress"}
              </button>
            </div>

            {/* Editor Content */}
            <div className="h-[600px] overflow-y-auto">
              <EditorContent editor={editor} />
            </div>
          </div>
        </div>

        {/* Suggestions Panel */}
        <div className="space-y-4">
          {/* Suggestions Header */}
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-gray-900">
              Suggestions{" "}
              {pendingCount > 0 && (
                <span className="text-amber-600">({pendingCount} pending)</span>
              )}
            </h3>
            <button
              onClick={() => setShowResolved(!showResolved)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              {showResolved ? "Hide resolved" : "Show resolved"}
            </button>
          </div>

          {/* Suggestions List */}
          <div className="max-h-[600px] overflow-y-auto">
            <SuggestionList
              suggestions={suggestions}
              onAccept={handleAccept}
              onDecline={handleDecline}
              isLoading={suggestionLoading}
              showResolved={showResolved}
            />
          </div>

          {/* Approve Button */}
          <div className="pt-4 border-t">
            <button
              onClick={handleApprove}
              disabled={!canApprove || stateLoading || draftApproved}
              className={`w-full px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                canApprove && !draftApproved
                  ? "bg-green-600 text-white hover:bg-green-700"
                  : "bg-gray-100 text-gray-400 cursor-not-allowed"
              }`}
            >
              {draftApproved
                ? "Draft Approved!"
                : pendingCount > 0
                ? `Resolve ${pendingCount} suggestion${pendingCount > 1 ? "s" : ""} first`
                : "Approve Draft & Continue"}
            </button>
            {pendingCount > 0 && (
              <p className="text-xs text-gray-500 text-center mt-2">
                Accept or decline all suggestions before approving
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Preference Sidebar */}
      <PreferenceSidebar />
    </div>
  );
}

/**
 * Toolbar button component.
 */
function ToolbarButton({
  onClick,
  active,
  title,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`w-8 h-8 rounded flex items-center justify-center text-sm ${
        active
          ? "bg-blue-100 text-blue-700"
          : "text-gray-700 hover:bg-gray-200"
      }`}
    >
      {children}
    </button>
  );
}
