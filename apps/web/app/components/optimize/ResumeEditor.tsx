"use client";

import { useCallback, useState, useRef, useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Underline from "@tiptap/extension-underline";
import Highlight from "@tiptap/extension-highlight";
import {
  useEditorAssist,
  EditorAction,
  ChatMessage as HookChatMessage,
  EditorSelectionPayload,
} from "../../hooks/useEditorAssist";
import { JobPosting, GapAnalysis } from "../../hooks/useWorkflow";

// Chat message type for highlight-and-chat feature (extends hook type with UI fields)
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  selectedText?: string;
  suggestion?: string;
  revisionId?: string;
  canApply?: boolean;
  verificationSummary?: string;
  timestamp: Date;
}

interface ResumeEditorProps {
  threadId: string;
  initialContent: string;
  jobPosting: JobPosting | null;
  gapAnalysis: GapAnalysis | null;
  onSave: (html: string) => Promise<void>;
  onApprove?: () => Promise<void>;
}

const stripHighlightMarks = (html: string) => html.replace(/<mark[^>]*>/gi, '').replace(/<\/mark>/gi, '');

const plainTextFromHtml = (html: string) => html.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();

export default function ResumeEditor({
  threadId,
  initialContent,
  jobPosting,
  gapAnalysis,
  onSave,
  onApprove,
}: ResumeEditorProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);
  const [selectedText, setSelectedText] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [chatMode, setChatMode] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  // Store selection positions to persist highlight
  const [highlightedRange, setHighlightedRange] = useState<EditorSelectionPayload | null>(null);

  const {
    suggestion,
    isLoading: isAssistLoading,
    error: assistError,
    requestSuggestion,
    clearSuggestion,
    chatWithDraftingAgent,
    applyRevision,
    syncEditor,
  } = useEditorAssist(threadId);

  const [overrideVerification, setOverrideVerification] = useState(false);

  // localStorage key for auto-saving editor content
  const editorStorageKey = `resume_agent:editor_html:${threadId}`;

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  useEffect(() => {
    setOverrideVerification(false);
  }, [suggestion?.revisionId]);

  // Load from localStorage if available (preserves unsaved edits across refreshes)
  // Strip any persisted <mark> highlight tags (artifact from editor assist)
  const savedHtml = typeof window !== "undefined"
    ? localStorage.getItem(editorStorageKey)
    : null;
  const rawContent = savedHtml || initialContent;
  const cleanContent = stripHighlightMarks(rawContent);
  // Persist cleaned version so <mark> tags don't reappear on refresh
  if (typeof window !== "undefined" && cleanContent !== rawContent) {
    try { localStorage.setItem(editorStorageKey, cleanContent); } catch { /* ignore */ }
  }

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Placeholder.configure({
        placeholder: "Start writing your resume...",
      }),
      Underline,
      Highlight.configure({
        multicolor: true,
      }),
    ],
    content: cleanContent,
    onUpdate: ({ editor }) => {
      // Auto-save to localStorage on every edit
      try {
        localStorage.setItem(editorStorageKey, editor.getHTML());
      } catch {
        // Ignore quota errors
      }
    },
    onSelectionUpdate: ({ editor }) => {
      const { from, to } = editor.state.selection;
      if (from !== to) {
        const text = editor.state.doc.textBetween(from, to);
        const contextBefore = editor.state.doc.textBetween(Math.max(0, from - 500), from, " ");
        const contextAfter = editor.state.doc.textBetween(to, Math.min(editor.state.doc.content.size, to + 500), " ");
        setSelectedText(text);
        // Store the selection range for persistent highlighting
        setHighlightedRange({
          from,
          to,
          context_before: contextBefore,
          context_after: contextAfter,
        });
      } else {
        // Don't clear selected text if we have a highlighted range (user clicked away)
        if (!highlightedRange) {
          setSelectedText("");
        }
      }
    },
    editorProps: {
      attributes: {
        class:
          "prose prose-sm max-w-none focus:outline-none min-h-[500px] px-8 py-6",
      },
    },
  });

  useEffect(() => {
    if (!editor) return;
    const savedDraft = typeof window !== "undefined"
      ? localStorage.getItem(editorStorageKey)
      : null;
    const nextContent = stripHighlightMarks(savedDraft || initialContent || "");
    if (!nextContent) return;

    const currentHtml = stripHighlightMarks(editor.getHTML());
    if (!plainTextFromHtml(currentHtml) && currentHtml !== nextContent) {
      editor.commands.setContent(nextContent);
    }
  }, [editor, editorStorageKey, initialContent]);

  const handleSave = async () => {
    if (!editor) return;

    setIsSaving(true);
    try {
      await onSave(stripHighlightMarks(editor.getHTML()));
      // Clear localStorage draft — backend is now up to date
      try { localStorage.removeItem(editorStorageKey); } catch { /* ignore */ }
    } catch (error) {
      console.error("Save failed:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleApprove = async () => {
    if (!onApprove) return;

    setIsApproving(true);
    try {
      // Save first to ensure all edits are persisted
      if (editor) {
        await onSave(stripHighlightMarks(editor.getHTML()));
      }
      await onApprove();
    } catch (error) {
      console.error("Approve failed:", error);
    } finally {
      setIsApproving(false);
    }
  };

  // Apply visual highlight to the selected text (for when focus leaves editor)
  const applyHighlight = useCallback(() => {
    if (!editor || !highlightedRange) return;
    const { from, to } = highlightedRange;
    editor.chain().setTextSelection({ from, to }).setHighlight({ color: '#fef08a' }).run();
  }, [editor, highlightedRange]);

  // Clear the visual highlight
  const clearHighlight = useCallback(() => {
    if (!editor || !highlightedRange) return;
    const { from, to } = highlightedRange;
    editor.chain().setTextSelection({ from, to }).unsetHighlight().run();
    setHighlightedRange(null);
    setSelectedText("");
  }, [editor, highlightedRange]);

  // Strip ALL highlight marks from the entire document (cleanup after applying suggestions)
  const stripAllHighlights = useCallback(() => {
    if (!editor) return;
    const { state } = editor;
    const highlightType = state.schema?.marks?.highlight;
    if (!highlightType) return;
    const { tr } = state;
    tr.removeMark(0, state.doc.content.size, highlightType);
    editor.view.dispatch(tr);
  }, [editor]);

  // Handle focus on chat input - apply highlight to keep selection visible
  const handleChatFocus = () => {
    if (highlightedRange && editor) {
      applyHighlight();
    }
  };

  const persistCurrentEditor = useCallback(async () => {
    if (!editor) return false;
    const currentHtml = stripHighlightMarks(editor.getHTML());
    const synced = await syncEditor(currentHtml);
    if (synced) {
      try {
        localStorage.setItem(editorStorageKey, currentHtml);
      } catch {
        // Ignore quota errors
      }
    }
    return synced;
  }, [editor, editorStorageKey, syncEditor]);

  const handleAssist = async (action: EditorAction) => {
    if (!selectedText) {
      alert("Please select some text first");
      return;
    }
    const synced = await persistCurrentEditor();
    if (!synced) return;
    requestSuggestion(action, selectedText, undefined, highlightedRange);
  };

  const applyServerRenderedRevision = useCallback((resumeHtml: string) => {
    if (!editor) return;
    editor.commands.setContent(resumeHtml);
    try {
      localStorage.setItem(editorStorageKey, resumeHtml);
    } catch {
      // Ignore quota errors
    }
    stripAllHighlights();
    clearSuggestion();
    setHighlightedRange(null);
    setSelectedText("");
    setOverrideVerification(false);
  }, [clearSuggestion, editor, editorStorageKey, stripAllHighlights]);

  const applySuggestion = useCallback(async () => {
    if (!suggestion?.revisionId || !editor) return;

    const synced = await persistCurrentEditor();
    if (!synced) return;
    const result = await applyRevision(suggestion.revisionId, overrideVerification);
    if (result?.resumeHtml) {
      applyServerRenderedRevision(result.resumeHtml);
    }
  }, [applyRevision, applyServerRenderedRevision, editor, overrideVerification, persistCurrentEditor, suggestion]);

  // Handle chat message submission - uses drafting agent with full context
  const handleChatSubmit = async () => {
    if (!chatInput.trim() || !selectedText || isAssistLoading) return;

    const synced = await persistCurrentEditor();
    if (!synced) return;

    const submittedInput = chatInput;
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: submittedInput,
      selectedText: selectedText,
      timestamp: new Date(),
    };

    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");

    // Convert chat messages to format expected by drafting agent
    const chatHistory: HookChatMessage[] = chatMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // Use drafting agent - backend uses synced state for full context
    const result = await chatWithDraftingAgent(selectedText, submittedInput, chatHistory, highlightedRange);

    if (result) {
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: result.suggestion,
        suggestion: result.suggestion,
        revisionId: result.revisionId,
        canApply: result.canApply,
        verificationSummary: result.verification?.summary,
        timestamp: new Date(),
      };
      setChatMessages((prev) => [...prev, assistantMessage]);
    }
  };

  // Apply suggestion from chat message
  const applyChatSuggestion = useCallback(async (revisionId: string, allowOverride = false) => {
    if (!editor) return;

    const synced = await persistCurrentEditor();
    if (!synced) return;
    const result = await applyRevision(revisionId, allowOverride);
    if (result?.resumeHtml) {
      applyServerRenderedRevision(result.resumeHtml);
    }
  }, [applyRevision, applyServerRenderedRevision, editor, persistCurrentEditor]);

  // Handle Enter key in chat input
  const handleChatKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleChatSubmit();
    }
  };

  return (
    <div className="flex h-[calc(100vh-16rem)]">
      {/* Main Editor */}
      <div className="flex-1 flex flex-col bg-white rounded-lg shadow overflow-hidden">
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
            •
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor?.chain().focus().toggleOrderedList().run()}
            active={editor?.isActive("orderedList")}
            title="Numbered List"
          >
            1.
          </ToolbarButton>

          <div className="w-px h-6 bg-gray-300 mx-2" />

          <ToolbarButton
            onClick={() => editor?.chain().focus().undo().run()}
            disabled={!editor?.can().undo()}
            title="Undo (Ctrl+Z)"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
            </svg>
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor?.chain().focus().redo().run()}
            disabled={!editor?.can().redo()}
            title="Redo (Ctrl+Y)"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6" />
            </svg>
          </ToolbarButton>

          <div className="flex-1" />

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-300"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>

          {onApprove && (
            <button
              onClick={handleApprove}
              disabled={isApproving}
              className="px-4 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:bg-gray-300"
            >
              {isApproving ? "Approving..." : "Approve & Export"}
            </button>
          )}

          <button
            onClick={() => setIsDrawerOpen(!isDrawerOpen)}
            className={`px-3 py-1.5 text-sm rounded ${
              isDrawerOpen
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            AI Assist
          </button>
        </div>

        {/* Editor Content */}
        <div className="flex-1 overflow-y-auto">
          <EditorContent editor={editor} />
        </div>

        {/* Status bar */}
        <div className="border-t px-4 py-2 text-xs text-gray-500 bg-gray-50 flex justify-between">
          <span>
            {selectedText
              ? `${selectedText.length} characters selected`
              : "Select text to use AI assistance"}
          </span>
          <span>Auto-saved</span>
        </div>
      </div>

      {/* AI Assistant Drawer */}
      {isDrawerOpen && (
        <div className="w-96 bg-white rounded-lg shadow ml-4 flex flex-col overflow-hidden">
          {/* Header with mode toggle */}
          <div className="p-4 border-b">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-900">AI Assistant</h3>
              <div className="flex bg-gray-100 rounded-lg p-0.5">
                <button
                  onClick={() => setChatMode(false)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    !chatMode ? "bg-white shadow text-blue-600" : "text-gray-600"
                  }`}
                >
                  Quick Actions
                </button>
                <button
                  onClick={() => setChatMode(true)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    chatMode ? "bg-white shadow text-blue-600" : "text-gray-600"
                  }`}
                >
                  Chat
                </button>
              </div>
            </div>
            {selectedText ? (
              <div className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs">
                <span className="font-medium text-yellow-800">Selected: </span>
                <span className="text-yellow-700 line-clamp-2">&quot;{selectedText}&quot;</span>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Select text to get AI assistance
              </p>
            )}
          </div>

          {/* Quick Actions Mode */}
          {!chatMode && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Quick Actions */}
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">Quick Actions</p>
                <AssistButton
                  onClick={() => handleAssist("improve")}
                  disabled={!selectedText || isAssistLoading}
                >
                  ✨ Improve Writing
                </AssistButton>
                <AssistButton
                  onClick={() => handleAssist("add_keywords")}
                  disabled={!selectedText || isAssistLoading}
                >
                  🔑 Add ATS Keywords
                </AssistButton>
                <AssistButton
                  onClick={() => handleAssist("quantify")}
                  disabled={!selectedText || isAssistLoading}
                >
                  📊 Add Metrics
                </AssistButton>
                <AssistButton
                  onClick={() => handleAssist("shorten")}
                  disabled={!selectedText || isAssistLoading}
                >
                  ✂️ Make Concise
                </AssistButton>
                <AssistButton
                  onClick={() => handleAssist("fix_tone")}
                  disabled={!selectedText || isAssistLoading}
                >
                  💼 More Professional
                </AssistButton>
              </div>

              {/* Loading */}
              {isAssistLoading && (
                <div className="flex items-center space-x-2 text-blue-600">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent" />
                  <span className="text-sm">Generating suggestion...</span>
                </div>
              )}

              {/* Error */}
              {assistError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                  {assistError}
                </div>
              )}

              {/* Suggestion */}
              {suggestion && (
                <div className="space-y-3">
                  <div>
                    <p className="text-sm font-medium text-gray-700">Revision Plan</p>
                    {suggestion.targetUnit?.label && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {suggestion.targetUnit.label}
                      </p>
                    )}
                  </div>
                  {suggestion.editPlan && (
                    <div className="p-3 bg-gray-50 border border-gray-200 rounded text-xs text-gray-700 space-y-2">
                      <p className="font-medium text-gray-900">{suggestion.editPlan.goal}</p>
                      <div className="space-y-1">
                        {suggestion.editPlan.todos.map((todo) => (
                          <div key={todo.id} className="flex justify-between gap-2">
                            <span>{todo.label}</span>
                            <span className={todo.status === "done" ? "text-green-700" : "text-gray-500"}>
                              {todo.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <p className="text-sm font-medium text-gray-700">Proposed Revision</p>
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded">
                    <p className="text-sm text-gray-800">{suggestion.suggestion}</p>
                  </div>
                  {suggestion.verification && (
                    <div
                      className={`p-3 border rounded text-xs ${
                        suggestion.verification.passed
                          ? "bg-green-50 border-green-200 text-green-800"
                          : "bg-amber-50 border-amber-200 text-amber-800"
                      }`}
                    >
                      <p className="font-medium">{suggestion.verification.summary}</p>
                      {suggestion.verification.evidence && (
                        <p className="mt-1">&quot;{suggestion.verification.evidence}&quot;</p>
                      )}
                    </div>
                  )}
                  {suggestion.overrideRequired && (
                    <label className="flex items-start gap-2 text-xs text-gray-700">
                      <input
                        type="checkbox"
                        checked={overrideVerification}
                        onChange={(event) => setOverrideVerification(event.target.checked)}
                        className="mt-0.5"
                      />
                      Apply with verification override
                    </label>
                  )}
                  <div className="flex space-x-2">
                    <button
                      onClick={applySuggestion}
                      disabled={!suggestion.revisionId || (!suggestion.canApply && !overrideVerification) || isAssistLoading}
                      className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                    >
                      Use this revision
                    </button>
                    <button
                      onClick={clearSuggestion}
                      className="px-3 py-2 border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              )}

              {/* Keywords reference */}
              {gapAnalysis && gapAnalysis.keywords_to_include.length > 0 && (
                <div className="pt-4 border-t">
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Target Keywords
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {gapAnalysis.keywords_to_include.map((kw, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded cursor-pointer hover:bg-blue-100"
                        onClick={() => {
                          editor?.chain().focus().insertContent(kw).run();
                        }}
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    Click to insert at cursor
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Chat Mode */}
          {chatMode && (
            <>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {chatMessages.length === 0 && (
                  <div className="text-center text-gray-500 text-sm py-8">
                    <p className="mb-2">Highlight text in the editor, then ask me anything about it.</p>
                    <p className="text-xs text-gray-400">
                      Examples: &quot;Make this more impactful&quot;, &quot;Add metrics&quot;, &quot;Rephrase for clarity&quot;
                    </p>
                  </div>
                )}

                {chatMessages.map((msg) => (
                  <div key={msg.id} className="space-y-1">
                    {msg.role === "user" ? (
                      <div className="flex justify-end">
                        <div className="max-w-[85%] bg-blue-600 text-white rounded-lg rounded-tr-none p-3">
                          {msg.selectedText && (
                            <div className="text-xs text-blue-200 mb-1 pb-1 border-b border-blue-400 line-clamp-1">
                              Re: &quot;{msg.selectedText}&quot;
                            </div>
                          )}
                          <p className="text-sm">{msg.content}</p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex">
                        <div className="max-w-[85%] bg-gray-100 rounded-lg rounded-tl-none p-3">
                          <p className="text-sm text-gray-800">{msg.content}</p>
                          {msg.verificationSummary && (
                            <p
                              className={`mt-2 text-xs ${
                                msg.canApply ? "text-green-700" : "text-amber-700"
                              }`}
                            >
                              {msg.verificationSummary}
                            </p>
                          )}
                          {msg.revisionId && (
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                onClick={() => applyChatSuggestion(msg.revisionId!)}
                                disabled={!msg.canApply || isAssistLoading}
                                className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                              >
                                Use this revision
                              </button>
                              {!msg.canApply && (
                                <button
                                  onClick={() => applyChatSuggestion(msg.revisionId!, true)}
                                  disabled={isAssistLoading}
                                  className="px-3 py-1 border border-amber-300 text-amber-800 text-xs rounded hover:bg-amber-50 disabled:opacity-50"
                                >
                                  Use with override
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {isAssistLoading && (
                  <div className="flex">
                    <div className="bg-gray-100 rounded-lg rounded-tl-none p-3">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                      </div>
                    </div>
                  </div>
                )}

                {assistError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                    {assistError}
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Chat Input */}
              <div className="p-4 border-t bg-gray-50">
                <div className="flex space-x-2">
                  <textarea
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={handleChatKeyDown}
                    onFocus={handleChatFocus}
                    placeholder={selectedText ? "Ask about the selected text..." : "Select text first..."}
                    disabled={!selectedText || isAssistLoading}
                    rows={2}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg resize-none text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
                  />
                  <button
                    onClick={handleChatSubmit}
                    disabled={!chatInput.trim() || !selectedText || isAssistLoading}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                  >
                    Send
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Press Enter to send, Shift+Enter for new line
                </p>
              </div>
            </>
          )}

          {/* Job context */}
          {jobPosting && (
            <div className="p-4 border-t bg-gray-50">
              <p className="text-xs text-gray-500">
                Optimizing for: {jobPosting.title} at {jobPosting.company_name}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolbarButton({
  onClick,
  active,
  disabled,
  title,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`w-8 h-8 rounded flex items-center justify-center text-sm ${
        disabled
          ? "text-gray-300 cursor-not-allowed"
          : active
          ? "bg-blue-100 text-blue-700"
          : "text-gray-700 hover:bg-gray-200"
      }`}
    >
      {children}
    </button>
  );
}

function AssistButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full p-2 text-left bg-white border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
    >
      {children}
    </button>
  );
}
