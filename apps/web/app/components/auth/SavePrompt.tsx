"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/app/hooks/useAuth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STORAGE_KEYS = {
  pendingEvents: "resume_agent:pending_events",
  pendingRatings: "resume_agent:pending_ratings",
  promptDismissed: "resume_agent:save_prompt_dismissed",
  completedResumes: "resume_agent:completed_resumes",
};

interface SavePromptProps {
  onDismiss?: () => void;
}

export function SavePrompt({ onDismiss }: SavePromptProps) {
  const { isAuthenticated, login } = useAuth();
  const [isVisible, setIsVisible] = useState(false);
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    // Don't show if authenticated
    if (isAuthenticated) {
      setIsVisible(false);
      return;
    }

    // Don't show if dismissed
    const dismissed = localStorage.getItem(STORAGE_KEYS.promptDismissed);
    if (dismissed) {
      setIsVisible(false);
      return;
    }

    // Show if user has pending data worth saving
    const events = localStorage.getItem(STORAGE_KEYS.pendingEvents);
    const ratings = localStorage.getItem(STORAGE_KEYS.pendingRatings);
    const completedResumes = localStorage.getItem(STORAGE_KEYS.completedResumes);

    const eventCount = events ? JSON.parse(events).length : 0;
    const ratingCount = ratings ? JSON.parse(ratings).length : 0;
    const resumeCount = completedResumes ? parseInt(completedResumes, 10) : 0;

    // Show prompt if:
    // - User has completed at least 1 resume, OR
    // - User has 3+ preference events, OR
    // - User has submitted a rating
    const shouldShow = resumeCount >= 1 || eventCount >= 3 || ratingCount >= 1;
    setIsVisible(shouldShow);
  }, [isAuthenticated]);

  const handleDismiss = () => {
    localStorage.setItem(STORAGE_KEYS.promptDismissed, "true");
    setIsVisible(false);
    onDismiss?.();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setMessage(null);

    const result = await login(email);

    if (result.success) {
      setMessage({ type: "success", text: "Check your email for the login link!" });
      setEmail("");
    } else {
      setMessage({ type: "error", text: result.message });
    }

    setIsSubmitting(false);
  };

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-4 right-4 max-w-sm bg-white rounded-lg shadow-lg border border-gray-200 p-4 z-40">
      <button
        onClick={handleDismiss}
        className="absolute top-2 right-2 text-gray-400 hover:text-gray-600"
        aria-label="Dismiss"
      >
        ×
      </button>

      <h3 className="text-lg font-semibold text-gray-900 mb-2">
        Save your preferences?
      </h3>
      <p className="text-sm text-gray-600 mb-4">
        Your editing style will be remembered for next time.
      </p>

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter your email"
          required
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={isSubmitting}
        />

        {message && (
          <p
            className={`text-sm ${
              message.type === "success" ? "text-green-600" : "text-red-600"
            }`}
          >
            {message.text}
          </p>
        )}

        <div className="flex gap-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex-1 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {isSubmitting ? "Sending..." : "Save"}
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900"
          >
            Maybe later
          </button>
        </div>
      </form>
    </div>
  );
}
