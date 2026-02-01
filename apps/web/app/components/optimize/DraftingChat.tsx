"use client";

import { useState, useRef, useEffect } from "react";

const API_URL = "";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: string;
  suggestion?: string;
  timestamp: string;
}

interface DraftingChatProps {
  threadId: string;
  selectedText: string;
  onApplySuggestion: (originalText: string, newText: string) => void;
  onClearSelection: () => void;
}

/**
 * Chat interface for AI-assisted resume editing.
 *
 * Features:
 * - Natural language commands (remove, rewrite, shorten, etc.)
 * - Context-aware suggestions based on selected text
 * - Quick action buttons for common operations
 * - Chat history within session
 */
export default function DraftingChat({
  threadId,
  selectedText,
  onApplySuggestion,
  onClearSelection,
}: DraftingChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastSuggestion, setLastSuggestion] = useState<{
    original: string;
    suggested: string;
  } | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when selection changes
  useEffect(() => {
    if (selectedText && inputRef.current) {
      inputRef.current.focus();
    }
  }, [selectedText]);

  /**
   * Parse user input to determine the action type.
   * Returns the action and any additional instructions.
   */
  const parseCommand = (text: string): { action: string; instructions: string } => {
    const lowerText = text.toLowerCase().trim();

    // Direct action keywords
    if (lowerText.startsWith("remove") || lowerText.startsWith("delete")) {
      return { action: "remove", instructions: text };
    }
    if (lowerText.startsWith("rewrite") || lowerText.startsWith("rephrase")) {
      return { action: "rewrite", instructions: text };
    }
    if (lowerText.startsWith("shorten") || lowerText.startsWith("condense") || lowerText.startsWith("make shorter")) {
      return { action: "shorten", instructions: text };
    }
    if (lowerText.startsWith("improve") || lowerText.startsWith("enhance") || lowerText.startsWith("make better")) {
      return { action: "improve", instructions: text };
    }
    if (lowerText.startsWith("quantify") || lowerText.includes("add numbers") || lowerText.includes("add metrics")) {
      return { action: "quantify", instructions: text };
    }
    if (lowerText.includes("keyword") || lowerText.includes("ats")) {
      return { action: "add_keywords", instructions: text };
    }
    if (lowerText.includes("formal") || lowerText.includes("professional")) {
      return { action: "fix_tone", instructions: "Make it more formal and professional" };
    }
    if (lowerText.includes("casual") || lowerText.includes("conversational")) {
      return { action: "fix_tone", instructions: "Make it more conversational" };
    }

    // Default to custom action for complex requests
    return { action: "custom", instructions: text };
  };

  /**
   * Send a message to the AI assistant.
   */
  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setLastSuggestion(null);

    try {
      const { action, instructions } = parseCommand(input);

      // Handle remove action locally
      if (action === "remove" && selectedText) {
        const assistantMessage: ChatMessage = {
          id: `msg-${Date.now() + 1}`,
          role: "assistant",
          content: `I'll remove the selected text. Click "Apply" to confirm the removal.`,
          action: "remove",
          suggestion: "",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setLastSuggestion({ original: selectedText, suggested: "" });
        setIsLoading(false);
        return;
      }

      // For other actions, call the API
      if (!selectedText) {
        const assistantMessage: ChatMessage = {
          id: `msg-${Date.now() + 1}`,
          role: "assistant",
          content: "Please select some text in the editor first, then tell me what you'd like to do with it.",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setIsLoading(false);
        return;
      }

      const response = await fetch(`${API_URL}/api/optimize/${threadId}/editor/assist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          selected_text: selectedText,
          instructions: instructions,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get suggestion");
      }

      const result = await response.json();

      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content: result.explanation || `Here's my suggestion for "${action}":`,
        action,
        suggestion: result.suggestion,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLastSuggestion({ original: selectedText, suggested: result.suggestion });
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle quick action buttons.
   * Directly sends the action command without going through input state.
   */
  const handleQuickAction = async (action: string) => {
    if (!selectedText) {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          role: "assistant",
          content: "Please select some text in the editor first.",
          timestamp: new Date().toISOString(),
        },
      ]);
      return;
    }

    // Add user message
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: action,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setLastSuggestion(null);

    try {
      // Handle remove action locally
      if (action === "remove") {
        const assistantMessage: ChatMessage = {
          id: `msg-${Date.now() + 1}`,
          role: "assistant",
          content: `I'll remove the selected text. Click "Apply" to confirm the removal.`,
          action: "remove",
          suggestion: "",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setLastSuggestion({ original: selectedText, suggested: "" });
        setIsLoading(false);
        return;
      }

      // For other actions, call the API
      const response = await fetch(`${API_URL}/api/optimize/${threadId}/editor/assist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          selected_text: selectedText,
          instructions: action,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get suggestion");
      }

      const result = await response.json();

      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content: result.explanation || `Here's my suggestion for "${action}":`,
        action,
        suggestion: result.suggestion,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setLastSuggestion({ original: selectedText, suggested: result.suggestion });
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Apply the last suggestion to the editor.
   */
  const handleApply = () => {
    if (lastSuggestion) {
      onApplySuggestion(lastSuggestion.original, lastSuggestion.suggested);
      setLastSuggestion(null);
      onClearSelection();

      // Add confirmation message
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          role: "assistant",
          content: "Applied! The change has been made to your resume.",
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  /**
   * Handle key press for sending on Enter.
   */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="bg-white rounded-lg shadow border h-full flex flex-col">
      {/* Header */}
      <div className="px-3 py-2 border-b bg-gray-50">
        <h3 className="text-sm font-medium text-gray-900">AI Assistant</h3>
        <p className="text-xs text-gray-500">Select text, then ask me to edit it</p>
      </div>

      {/* Selected Text Preview */}
      {selectedText && (
        <div className="px-3 py-2 bg-purple-50 border-b">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-purple-700">Selected:</span>
            <button
              onClick={onClearSelection}
              className="text-xs text-purple-600 hover:text-purple-800"
            >
              Clear
            </button>
          </div>
          <p className="text-xs text-purple-900 mt-1 line-clamp-2">
            {selectedText.length > 100 ? `${selectedText.substring(0, 100)}...` : selectedText}
          </p>
        </div>
      )}

      {/* Quick Actions */}
      {selectedText && (
        <div className="px-3 py-2 border-b flex flex-wrap gap-1">
          <button
            onClick={() => handleQuickAction("improve")}
            disabled={isLoading}
            className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
          >
            Improve
          </button>
          <button
            onClick={() => handleQuickAction("shorten")}
            disabled={isLoading}
            className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50"
          >
            Shorten
          </button>
          <button
            onClick={() => handleQuickAction("rewrite")}
            disabled={isLoading}
            className="px-2 py-1 text-xs bg-amber-100 text-amber-700 rounded hover:bg-amber-200 disabled:opacity-50"
          >
            Rewrite
          </button>
          <button
            onClick={() => handleQuickAction("remove")}
            disabled={isLoading}
            className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50"
          >
            Remove
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3 min-h-[150px]">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-xs py-4">
            <p>Select text in the editor to get started.</p>
            <p className="mt-1">Try: rewrite, shorten, remove, make more formal</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 ${
                msg.role === "user"
                  ? "bg-purple-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              <p className="text-xs">{msg.content}</p>
              {msg.suggestion && (
                <div className="mt-2 p-2 bg-white rounded border text-xs">
                  <p className="text-gray-600 mb-1">Suggested:</p>
                  <p className="text-gray-900">{msg.suggestion}</p>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-3 py-2">
              <div className="flex space-x-1">
                <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" />
                <div
                  className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.2s" }}
                />
                <div
                  className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.4s" }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Apply Button (when suggestion available) */}
      {lastSuggestion && (
        <div className="px-3 py-2 border-t bg-green-50">
          <button
            onClick={handleApply}
            className="w-full px-3 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
          >
            Apply Suggestion
          </button>
        </div>
      )}

      {/* Input */}
      <div className="px-3 py-2 border-t">
        <div className="flex space-x-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selectedText ? "What should I do with this text?" : "Select text first..."}
            disabled={isLoading || !selectedText}
            rows={1}
            className="flex-1 px-3 py-2 text-xs border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-none disabled:bg-gray-100"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading || !selectedText}
            className="px-3 py-2 bg-purple-600 text-white text-xs rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
