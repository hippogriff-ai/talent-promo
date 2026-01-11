"use client";

import { useState, useRef, useEffect } from "react";
import { DiscoveryMessage, DiscoveryPrompt } from "../../hooks/useDiscoveryStorage";

interface DiscoveryChatProps {
  messages: DiscoveryMessage[];
  pendingPrompt: DiscoveryPrompt | null;
  totalPrompts: number;
  currentPromptNumber: number;
  exchanges: number;
  canConfirm: boolean;
  onSubmitResponse: (response: string) => Promise<void>;
  onConfirmComplete: () => Promise<void>;
  isSubmitting: boolean;
}

/**
 * Chat component for the discovery conversation.
 *
 * Features:
 * - Displays conversation history
 * - Shows current prompt with context
 * - Auto-scrolls to bottom
 * - Supports Enter to send (Shift+Enter for newline)
 */
export default function DiscoveryChat({
  messages,
  pendingPrompt,
  totalPrompts,
  currentPromptNumber,
  exchanges,
  canConfirm,
  onSubmitResponse,
  onConfirmComplete,
  isSubmitting,
}: DiscoveryChatProps) {
  const [response, setResponse] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingPrompt]);

  // Focus textarea when prompt appears
  useEffect(() => {
    if (pendingPrompt && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [pendingPrompt]);

  const handleSubmit = async () => {
    if (!response.trim() || isSubmitting) return;

    const text = response.trim();
    setResponse("");
    await onSubmitResponse(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSkip = async () => {
    if (isSubmitting) return;
    await onSubmitResponse("skip");
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              Discovery Conversation
            </h3>
            <p className="text-sm text-gray-600">
              Let&apos;s uncover experiences you may have overlooked
            </p>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-500">
              Question {currentPromptNumber} of {totalPrompts}
            </span>
            {canConfirm && (
              <button
                onClick={onConfirmComplete}
                disabled={isSubmitting}
                className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:bg-gray-300 transition-colors"
              >
                Complete Discovery
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-purple-600 transition-all duration-300"
            style={{ width: `${(currentPromptNumber / totalPrompts) * 100}%` }}
          />
        </div>

        {/* Exchange count */}
        <div className="mt-2 flex items-center space-x-2 text-sm">
          <span className="text-gray-500">Exchanges: {exchanges}/3</span>
          {exchanges >= 3 ? (
            <span className="text-green-600 flex items-center">
              <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Ready to complete
            </span>
          ) : (
            <span className="text-gray-400">
              ({3 - exchanges} more to unlock completion)
            </span>
          )}
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-1">
            {msg.role === "agent" ? (
              // Agent message
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-purple-600 text-sm font-medium">AI</span>
                </div>
                <div className="flex-1 bg-gray-100 rounded-lg rounded-tl-none p-3 max-w-[85%]">
                  <p className="text-gray-800">{msg.content}</p>
                </div>
              </div>
            ) : (
              // User message
              <div className="flex items-start space-x-3 justify-end">
                <div className="flex-1 max-w-[85%] bg-purple-600 text-white rounded-lg rounded-tr-none p-3">
                  <p>{msg.content}</p>
                  {msg.experiencesExtracted && msg.experiencesExtracted.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-purple-400">
                      <span className="text-xs text-purple-200">
                        {msg.experiencesExtracted.length} experience(s) captured
                      </span>
                    </div>
                  )}
                </div>
                <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-gray-600 text-sm font-medium">You</span>
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Pending Prompt */}
        {pendingPrompt && (
          <div className="space-y-1">
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-purple-600 text-sm font-medium">AI</span>
              </div>
              <div className="flex-1 bg-gray-100 rounded-lg rounded-tl-none p-3 max-w-[85%]">
                <p className="text-gray-800">{pendingPrompt.question}</p>
                {pendingPrompt.intent && (
                  <p className="text-xs text-gray-500 mt-2 italic">
                    Hint: {pendingPrompt.intent}
                  </p>
                )}
                {pendingPrompt.relatedGaps && pendingPrompt.relatedGaps.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {pendingPrompt.relatedGaps.slice(0, 2).map((gap, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded"
                      >
                        {gap}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Waiting indicator when no pending prompt */}
        {!pendingPrompt && messages.length > 0 && (
          <div className="flex items-start space-x-3">
            <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
              <span className="text-purple-600 text-sm font-medium">AI</span>
            </div>
            <div className="flex-1 bg-gray-100 rounded-lg rounded-tl-none p-3">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <div
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.2s" }}
                />
                <div
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.4s" }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      {pendingPrompt && (
        <div className="p-4 border-t bg-gray-50">
          <div className="flex space-x-3">
            <textarea
              ref={textareaRef}
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Share your experience... (Shift+Enter for new line)"
              disabled={isSubmitting}
              rows={3}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-none disabled:bg-gray-100"
            />
            <div className="flex flex-col space-y-2">
              <button
                onClick={handleSubmit}
                disabled={!response.trim() || isSubmitting}
                className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? "..." : "Send"}
              </button>
              <button
                onClick={handleSkip}
                disabled={isSubmitting}
                className="px-6 py-2 text-sm text-gray-600 hover:text-gray-800 disabled:text-gray-400"
              >
                Skip
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            The more detail you share, the better we can tailor your resume.
          </p>
        </div>
      )}
    </div>
  );
}
