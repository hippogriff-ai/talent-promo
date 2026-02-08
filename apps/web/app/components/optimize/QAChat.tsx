"use client";

import { useState, useRef, useEffect } from "react";
import { GapAnalysis, QAInteraction } from "../../hooks/useWorkflow";

interface QAChatProps {
  qaHistory: QAInteraction[];
  pendingQuestion: string | null;
  qaRound: number;
  onSubmitAnswer: (answer: string) => Promise<void>;
  gapAnalysis: GapAnalysis | null;
}

export default function QAChat({
  qaHistory,
  pendingQuestion,
  qaRound,
  onSubmitAnswer,
  gapAnalysis,
}: QAChatProps) {
  const [answer, setAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [qaHistory, pendingQuestion]);

  const handleSubmit = async () => {
    if (!answer.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await onSubmitAnswer(answer);
      setAnswer("");
    } catch (error) {
      console.error("Failed to submit answer:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDone = async () => {
    setIsSubmitting(true);
    try {
      await onSubmitAnswer("done");
    } catch (error) {
      console.error("Failed to skip:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex h-[calc(100vh-16rem)] gap-6">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-white rounded-lg shadow">
        {/* Header */}
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                Help Us Understand You Better
              </h3>
              <p className="text-sm text-gray-600">
                Answer a few questions to highlight your unique strengths
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500">
                Question {qaRound} of 10
              </span>
              <button
                onClick={handleDone}
                disabled={isSubmitting}
                className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
              >
                Skip remaining →
              </button>
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-3 h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 transition-all duration-300"
              style={{ width: `${(qaRound / 10) * 100}%` }}
            />
          </div>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {qaHistory.map((qa, idx) => (
            <div key={idx} className="space-y-3">
              {/* Agent Question */}
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-blue-600 text-sm font-medium">AI</span>
                </div>
                <div className="flex-1 bg-gray-100 rounded-lg rounded-tl-none p-3">
                  <p className="text-gray-800">{qa.question}</p>
                </div>
              </div>

              {/* User Answer */}
              {qa.answer && (
                <div className="flex items-start space-x-3 justify-end">
                  <div className="flex-1 max-w-[80%] bg-blue-600 text-white rounded-lg rounded-tr-none p-3">
                    <p>{qa.answer}</p>
                  </div>
                  <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-gray-600 text-sm font-medium">You</span>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Pending Question */}
          {pendingQuestion && (
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-blue-600 text-sm font-medium">AI</span>
              </div>
              <div className="flex-1 bg-gray-100 rounded-lg rounded-tl-none p-3">
                <p className="text-gray-800">{pendingQuestion}</p>
              </div>
            </div>
          )}

          {/* Waiting indicator */}
          {!pendingQuestion && qaRound < 10 && (
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-blue-600 text-sm font-medium">AI</span>
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
        {pendingQuestion && (
          <div className="p-4 border-t">
            <div className="flex space-x-3">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your answer... (Shift+Enter for new line)"
                disabled={isSubmitting}
                rows={3}
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none disabled:bg-gray-100"
              />
              <button
                onClick={handleSubmit}
                disabled={!answer.trim() || isSubmitting}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors self-end"
              >
                {isSubmitting ? "..." : "Send"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Context Sidebar */}
      {gapAnalysis && (
        <div className="w-80 bg-white rounded-lg shadow p-4 hidden lg:block">
          <h4 className="font-semibold text-gray-900 mb-3">
            What We&apos;re Looking For
          </h4>

          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-green-700 mb-1">
                Strengths to Highlight
              </p>
              <ul className="text-sm text-gray-600 space-y-1">
                {gapAnalysis.recommended_emphasis.slice(0, 3).map((item, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="text-green-500 mr-1">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <p className="text-sm font-medium text-amber-700 mb-1">
                Gaps to Address
              </p>
              <ul className="text-sm text-gray-600 space-y-1">
                {gapAnalysis.gaps.slice(0, 3).map((item, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="text-amber-500 mr-1">•</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <p className="text-sm font-medium text-blue-700 mb-1">
                Keywords to Include
              </p>
              <div className="flex flex-wrap gap-1">
                {gapAnalysis.keywords_to_include.slice(0, 8).map((kw, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t text-xs text-gray-500">
            <p>
              The more detail you provide, the better we can tailor your resume
              to this specific role.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
