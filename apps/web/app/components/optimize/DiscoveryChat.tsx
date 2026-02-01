"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { DiscoveryMessage, DiscoveryPrompt } from "../../hooks/useDiscoveryStorage";
import { useTypingEffect } from "../../hooks/useTypingEffect";

interface CurrentTopic {
  id?: string;
  title?: string;
  goal?: string;
  prompts_asked?: number;
  max_prompts?: number;
}

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
  currentTopic?: CurrentTopic | null;
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
  currentTopic,
}: DiscoveryChatProps) {
  const [response, setResponse] = useState("");
  const [optimisticMessage, setOptimisticMessage] = useState<string | null>(null);
  const [typedMessages, setTypedMessages] = useState<Set<string>>(new Set());
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prevMessageCount = useRef(messages.length);
  const prevPendingQuestion = useRef<string | null>(null);

  // Typing effect for the pending prompt (AI's current question)
  const shouldTypePrompt = pendingPrompt && !optimisticMessage && !typedMessages.has(pendingPrompt.question);
  const {
    displayedText: typedPromptText,
    isTyping: isTypingPrompt,
    isComplete: isPromptComplete,
    skipToEnd: skipPromptTyping,
  } = useTypingEffect(
    shouldTypePrompt ? pendingPrompt.question : "",
    {
      speed: 12,
      delay: 100,
      onComplete: () => {
        if (pendingPrompt) {
          setTypedMessages(prev => {
            const next = new Set(Array.from(prev));
            next.add(pendingPrompt.question);
            return next;
          });
        }
      },
      skip: !shouldTypePrompt,
    }
  );

  // Mark prompt as typed when it completes or when we skip
  useEffect(() => {
    if (pendingPrompt && typedMessages.has(pendingPrompt.question)) {
      // Already typed, no action needed
    }
  }, [pendingPrompt, typedMessages]);

  // Filter out the pending prompt from messages if it appears there
  // (avoid showing same question twice)
  const filteredMessages = useMemo(() => {
    if (!pendingPrompt) return messages;
    return messages.filter(msg =>
      !(msg.role === "agent" && msg.content === pendingPrompt.question)
    );
  }, [messages, pendingPrompt]);

  // Scroll to bottom of chat container (not the whole page)
  const scrollToBottom = (smooth = true) => {
    const container = chatContainerRef.current;
    if (container && typeof container.scrollTo === "function") {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: smooth ? "smooth" : "auto",
      });
    } else if (container) {
      // Fallback for environments without scrollTo (e.g., jsdom in tests)
      container.scrollTop = container.scrollHeight;
    }
  };

  // Auto-scroll only when content actually changes
  useEffect(() => {
    const hasNewMessages = filteredMessages.length > prevMessageCount.current;
    const hasNewPrompt = pendingPrompt?.question !== prevPendingQuestion.current;

    if (hasNewMessages || hasNewPrompt) {
      scrollToBottom();
    }

    prevMessageCount.current = filteredMessages.length;
    prevPendingQuestion.current = pendingPrompt?.question ?? null;
  }, [filteredMessages.length, pendingPrompt?.question]);

  // Auto-scroll as typing effect progresses (AI message grows)
  useEffect(() => {
    if (isTypingPrompt && typedPromptText) {
      scrollToBottom(false); // Use instant scroll during typing for smoother UX
    }
  }, [typedPromptText, isTypingPrompt]);

  // Clear optimistic message when messages prop updates (backend responded)
  useEffect(() => {
    if (optimisticMessage && messages.some(m => m.role === "user" && m.content === optimisticMessage)) {
      setOptimisticMessage(null);
    }
  }, [messages, optimisticMessage]);

  // Scroll when optimistic message is shown
  useEffect(() => {
    if (optimisticMessage) {
      scrollToBottom();
    }
  }, [optimisticMessage]);

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
    // Show user message immediately (optimistic UI)
    setOptimisticMessage(text);
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
    // Show skip message immediately (optimistic UI)
    setOptimisticMessage("skip");
    await onSubmitResponse("skip");
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header - compact design */}
      <div className="px-4 py-3 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <h3 className="text-base font-semibold text-gray-900">
              Discovery
            </h3>
            <span className="text-sm text-gray-500">
              {currentPromptNumber}/{totalPrompts}
            </span>
            {/* Progress bar inline */}
            <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-600 transition-all duration-300"
                style={{ width: `${(currentPromptNumber / totalPrompts) * 100}%` }}
              />
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {/* Current topic badge */}
            {currentTopic?.title && (
              <span className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded truncate max-w-32" title={currentTopic.goal}>
                {currentTopic.title}
              </span>
            )}
            {/* Exchange indicator */}
            <span className={`text-xs px-2 py-1 rounded ${exchanges >= 3 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
              {exchanges}/3 exchanges
            </span>
            {canConfirm && (
              <button
                onClick={onConfirmComplete}
                disabled={isSubmitting}
                className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:bg-gray-300 transition-colors"
              >
                Complete
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Chat Messages - reduced padding, wider messages */}
      <div ref={chatContainerRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
        {filteredMessages.map((msg, idx) => (
          <div key={idx}>
            {msg.role === "agent" ? (
              // Agent message - full width with small avatar
              <div className="flex items-start space-x-2">
                <div className="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-purple-600 text-xs font-medium">AI</span>
                </div>
                <div className="flex-1 bg-gray-50 rounded-lg rounded-tl-none px-3 py-2">
                  <p className="text-gray-800 text-sm">{msg.content}</p>
                </div>
              </div>
            ) : (
              // User message - full width with small avatar
              <div className="flex items-start space-x-2 justify-end">
                <div className="flex-1 bg-purple-600 text-white rounded-lg rounded-tr-none px-3 py-2">
                  <p className="text-sm">{msg.content}</p>
                  {msg.experiencesExtracted && msg.experiencesExtracted.length > 0 && (
                    <div className="mt-1.5 pt-1.5 border-t border-purple-400">
                      <span className="text-xs text-purple-200">
                        {msg.experiencesExtracted.length} experience(s) captured
                      </span>
                    </div>
                  )}
                </div>
                <div className="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-gray-600 text-xs font-medium">Y</span>
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Optimistic User Message (shown immediately while waiting for backend) */}
        {optimisticMessage && (
          <div data-testid="optimistic-message">
            <div className="flex items-start space-x-2 justify-end">
              <div className="flex-1 bg-purple-600 text-white rounded-lg rounded-tr-none px-3 py-2">
                <p className="text-sm">{optimisticMessage === "skip" ? "(Skipped)" : optimisticMessage}</p>
              </div>
              <div className="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-gray-600 text-xs font-medium">Y</span>
              </div>
            </div>
          </div>
        )}

        {/* AI Thinking Indicator (shown after optimistic message while waiting) */}
        {optimisticMessage && isSubmitting && (
          <div className="flex items-start space-x-2" data-testid="ai-thinking">
            <div className="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-purple-600 text-xs font-medium">AI</span>
            </div>
            <div className="flex-1 bg-gray-50 rounded-lg rounded-tl-none px-3 py-2">
              <div className="flex items-center space-x-2">
                <div className="flex space-x-1">
                  <div className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" />
                  <div
                    className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  />
                  <div
                    className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0.4s" }}
                  />
                </div>
                <span className="text-xs text-gray-500">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        {/* Pending Prompt with Typing Effect */}
        {pendingPrompt && !optimisticMessage && (
          <div>
            <div className="flex items-start space-x-2">
              <div className="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-purple-600 text-xs font-medium">AI</span>
              </div>
              <div
                className="flex-1 bg-gray-50 rounded-lg rounded-tl-none px-3 py-2 cursor-pointer"
                onClick={() => {
                  if (isTypingPrompt) skipPromptTyping();
                }}
                title={isTypingPrompt ? "Click to show full message" : ""}
              >
                <p className="text-gray-800 text-sm">
                  {shouldTypePrompt ? typedPromptText : pendingPrompt.question}
                  {isTypingPrompt && (
                    <span className="inline-block w-0.5 h-4 bg-purple-600 ml-0.5 animate-pulse" />
                  )}
                </p>
                {/* Show hint and gaps only after typing completes */}
                {(isPromptComplete || typedMessages.has(pendingPrompt.question)) && (
                  <>
                    {pendingPrompt.intent && (
                      <p className="text-xs text-gray-500 mt-1.5 italic">
                        Hint: {pendingPrompt.intent}
                      </p>
                    )}
                    {pendingPrompt.relatedGaps && pendingPrompt.relatedGaps.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {pendingPrompt.relatedGaps.slice(0, 2).map((gap, idx) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 bg-amber-100 text-amber-700 text-xs rounded"
                          >
                            {gap}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Waiting indicator when no pending prompt and no optimistic message */}
        {!pendingPrompt && !optimisticMessage && filteredMessages.length > 0 && (
          <div className="flex items-start space-x-2">
            <div className="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-purple-600 text-xs font-medium">AI</span>
            </div>
            <div className="flex-1 bg-gray-50 rounded-lg rounded-tl-none px-3 py-2">
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

      </div>

      {/* Input Area - compact design, show only when typing is complete */}
      {pendingPrompt && (isPromptComplete || typedMessages.has(pendingPrompt.question)) && (
        <div className="px-3 py-2 border-t bg-gray-50">
          <div className="flex space-x-2">
            <textarea
              ref={textareaRef}
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Share your experience... (Shift+Enter for new line)"
              disabled={isSubmitting}
              rows={2}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-none disabled:bg-gray-100"
            />
            <div className="flex flex-col space-y-1">
              <button
                onClick={handleSubmit}
                disabled={!response.trim() || isSubmitting}
                className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? "..." : "Send"}
              </button>
              <button
                onClick={handleSkip}
                disabled={isSubmitting}
                className="px-4 py-1 text-xs text-gray-500 hover:text-gray-700 disabled:text-gray-400"
              >
                Skip
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Typing indicator when AI is still typing */}
      {pendingPrompt && isTypingPrompt && (
        <div className="px-3 py-2 border-t bg-gray-50 text-center">
          <span className="text-xs text-gray-500">Click the message to skip typing animation</span>
        </div>
      )}
    </div>
  );
}
