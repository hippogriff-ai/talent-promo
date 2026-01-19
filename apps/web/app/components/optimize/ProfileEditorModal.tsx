"use client";

import { useState, useEffect } from "react";

interface ProfileEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  markdown: string | null;
  onSave: (updatedMarkdown: string) => void;
}

/**
 * Modal for viewing and editing LinkedIn profile markdown content.
 *
 * Features:
 * - Renders markdown in a readable format
 * - Allows users to edit the raw markdown
 * - User can add missing information before proceeding
 */
export function ProfileEditorModal({
  isOpen,
  onClose,
  title,
  markdown,
  onSave,
}: ProfileEditorModalProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState("");

  useEffect(() => {
    if (markdown) {
      setEditedContent(markdown);
    }
  }, [markdown]);

  if (!isOpen || !markdown) return null;

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleSave = () => {
    onSave(editedContent);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedContent(markdown);
    setIsEditing(false);
  };

  // Simple markdown renderer for display mode
  const renderMarkdown = (content: string) => {
    // Split into lines and render with basic formatting
    const lines = content.split('\n');

    return lines.map((line, index) => {
      // H1
      if (line.startsWith('# ')) {
        return (
          <h1 key={index} className="text-2xl font-bold text-gray-900 mt-4 mb-2">
            {line.slice(2)}
          </h1>
        );
      }
      // H2
      if (line.startsWith('## ')) {
        return (
          <h2 key={index} className="text-xl font-semibold text-gray-800 mt-6 mb-2 border-b border-gray-200 pb-1">
            {line.slice(3)}
          </h2>
        );
      }
      // H3
      if (line.startsWith('### ')) {
        return (
          <h3 key={index} className="text-lg font-medium text-gray-700 mt-4 mb-1">
            {line.slice(4)}
          </h3>
        );
      }
      // Bullet points
      if (line.startsWith('• ') || line.startsWith('- ')) {
        return (
          <li key={index} className="ml-4 text-gray-600 mb-1">
            {line.slice(2)}
          </li>
        );
      }
      // Links (simplified)
      if (line.includes('<web_link>')) {
        const cleanLine = line.replace(/<web_link>/g, '').replace(/\[([^\]]+)\]/g, '$1');
        return (
          <p key={index} className="text-gray-600 mb-1">
            {cleanLine}
          </p>
        );
      }
      // Empty line
      if (line.trim() === '') {
        return <div key={index} className="h-2" />;
      }
      // Regular text
      return (
        <p key={index} className="text-gray-600 mb-1">
          {line}
        </p>
      );
    });
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[85vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50 rounded-t-lg">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
              <p className="text-sm text-gray-500 mt-0.5">
                {isEditing ? "Edit your profile information below" : "Review and edit if needed"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {!isEditing && (
                <button
                  onClick={handleEdit}
                  className="px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                >
                  Edit
                </button>
              )}
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-500 p-1"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {isEditing ? (
              <div className="space-y-4">
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                  <p className="text-sm text-yellow-800">
                    <span className="font-medium">Tip:</span> Add any missing information like projects,
                    certifications, or achievements. The AI will use this to optimize your resume.
                  </p>
                </div>
                <textarea
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  className="w-full h-[50vh] p-4 font-mono text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                  placeholder="Enter profile information..."
                />
              </div>
            ) : (
              <div className="prose prose-sm max-w-none">
                {renderMarkdown(markdown)}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
            <div className="text-sm text-gray-500">
              {markdown.length.toLocaleString()} characters
            </div>
            <div className="flex items-center gap-3">
              {isEditing ? (
                <>
                  <button
                    onClick={handleCancel}
                    className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Save Changes
                  </button>
                </>
              ) : (
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Done
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
