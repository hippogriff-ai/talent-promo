"use client";

import { useCallback, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Underline from "@tiptap/extension-underline";
import Highlight from "@tiptap/extension-highlight";
import { useEditorAssist, EditorAction } from "../../hooks/useEditorAssist";
import { JobPosting, GapAnalysis } from "../../hooks/useWorkflow";

interface ResumeEditorProps {
  threadId: string;
  initialContent: string;
  jobPosting: JobPosting | null;
  gapAnalysis: GapAnalysis | null;
  onSave: (html: string) => Promise<void>;
}

export default function ResumeEditor({
  threadId,
  initialContent,
  jobPosting,
  gapAnalysis,
  onSave,
}: ResumeEditorProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);
  const [selectedText, setSelectedText] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const {
    suggestion,
    isLoading: isAssistLoading,
    error: assistError,
    requestSuggestion,
    clearSuggestion,
  } = useEditorAssist(threadId);

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
    content: initialContent,
    onSelectionUpdate: ({ editor }) => {
      const { from, to } = editor.state.selection;
      if (from !== to) {
        setSelectedText(editor.state.doc.textBetween(from, to));
      } else {
        setSelectedText("");
      }
    },
    editorProps: {
      attributes: {
        class:
          "prose prose-sm max-w-none focus:outline-none min-h-[500px] px-8 py-6",
      },
    },
  });

  const handleSave = async () => {
    if (!editor) return;

    setIsSaving(true);
    try {
      await onSave(editor.getHTML());
    } catch (error) {
      console.error("Save failed:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleAssist = (action: EditorAction) => {
    if (!selectedText) {
      alert("Please select some text first");
      return;
    }
    requestSuggestion(action, selectedText);
  };

  const applySuggestion = useCallback(() => {
    if (!suggestion || !editor) return;

    const { from, to } = editor.state.selection;
    editor.chain().focus().deleteRange({ from, to }).insertContent(suggestion.suggestion).run();
    clearSuggestion();
  }, [suggestion, editor, clearSuggestion]);

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

          <div className="flex-1" />

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-300"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>

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
        <div className="w-80 bg-white rounded-lg shadow ml-4 flex flex-col overflow-hidden">
          <div className="p-4 border-b">
            <h3 className="font-semibold text-gray-900">AI Assistant</h3>
            <p className="text-sm text-gray-500">
              Select text and use actions below
            </p>
          </div>

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
                <p className="text-sm font-medium text-gray-700">Suggestion</p>
                <div className="p-3 bg-blue-50 border border-blue-200 rounded">
                  <p className="text-sm text-gray-800">{suggestion.suggestion}</p>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={applySuggestion}
                    className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                  >
                    Apply
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
