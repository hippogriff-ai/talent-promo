"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/app/hooks/useAuth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RatingModalProps {
  threadId: string;
  jobTitle?: string;
  companyName?: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmit?: () => void;
}

interface RatingData {
  overall_quality: number | null;
  ats_satisfaction: boolean | null;
  would_send_as_is: boolean | null;
  feedback_text: string;
}

const STORAGE_KEYS = {
  pendingRatings: "resume_agent:pending_ratings",
  anonymousId: "resume_agent:anonymous_id",
};

function StarRating({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (value: number) => void;
}) {
  const [hover, setHover] = useState<number | null>(null);

  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHover(star)}
          onMouseLeave={() => setHover(null)}
          className="text-2xl focus:outline-none transition-colors"
        >
          <span
            className={
              (hover !== null ? star <= hover : value !== null && star <= value)
                ? "text-yellow-400"
                : "text-gray-300"
            }
          >
            ★
          </span>
        </button>
      ))}
    </div>
  );
}

function ThumbsButton({
  selected,
  isUp,
  onClick,
}: {
  selected: boolean | null;
  isUp: boolean;
  onClick: () => void;
}) {
  const isActive = selected === isUp;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`p-2 rounded-full border-2 transition-all ${
        isActive
          ? isUp
            ? "border-green-500 bg-green-50 text-green-600"
            : "border-red-500 bg-red-50 text-red-600"
          : "border-gray-300 text-gray-400 hover:border-gray-400"
      }`}
    >
      <span className="text-xl">{isUp ? "👍" : "👎"}</span>
    </button>
  );
}

export function RatingModal({
  threadId,
  jobTitle,
  companyName,
  isOpen,
  onClose,
  onSubmit,
}: RatingModalProps) {
  const { isAuthenticated } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rating, setRating] = useState<RatingData>({
    overall_quality: null,
    ats_satisfaction: null,
    would_send_as_is: null,
    feedback_text: "",
  });

  // Reset when modal opens
  useEffect(() => {
    if (isOpen) {
      setRating({
        overall_quality: null,
        ats_satisfaction: null,
        would_send_as_is: null,
        feedback_text: "",
      });
    }
  }, [isOpen]);

  const handleSubmit = async () => {
    setIsSubmitting(true);

    const ratingPayload = {
      thread_id: threadId,
      overall_quality: rating.overall_quality,
      ats_satisfaction: rating.ats_satisfaction,
      would_send_as_is: rating.would_send_as_is,
      feedback_text: rating.feedback_text || null,
      job_title: jobTitle || null,
      company_name: companyName || null,
    };

    try {
      if (isAuthenticated) {
        // Submit to API
        await fetch(`${API_URL}/api/ratings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ratingPayload),
          credentials: "include",
        });
      } else {
        // Store locally for anonymous users
        saveToLocalStorage(ratingPayload);
      }

      onSubmit?.();
      onClose();
    } catch (error) {
      console.error("Failed to submit rating:", error);
      // Save locally as fallback
      saveToLocalStorage(ratingPayload);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  const saveToLocalStorage = (ratingPayload: Record<string, unknown>) => {
    try {
      const existing = localStorage.getItem(STORAGE_KEYS.pendingRatings);
      const ratings = existing ? JSON.parse(existing) : [];
      ratings.push({
        ...ratingPayload,
        created_at: new Date().toISOString(),
      });
      localStorage.setItem(STORAGE_KEYS.pendingRatings, JSON.stringify(ratings));

      // Ensure anonymous ID exists
      if (!localStorage.getItem(STORAGE_KEYS.anonymousId)) {
        localStorage.setItem(STORAGE_KEYS.anonymousId, crypto.randomUUID());
      }
    } catch (error) {
      console.error("Failed to save rating to localStorage:", error);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          How was your resume?
        </h2>

        <div className="space-y-6">
          {/* Overall Quality */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Overall quality
            </label>
            <StarRating
              value={rating.overall_quality}
              onChange={(value) =>
                setRating((prev) => ({ ...prev, overall_quality: value }))
              }
            />
          </div>

          {/* ATS Satisfaction */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Happy with ATS optimization?
            </label>
            <div className="flex gap-4">
              <ThumbsButton
                selected={rating.ats_satisfaction}
                isUp={true}
                onClick={() =>
                  setRating((prev) => ({
                    ...prev,
                    ats_satisfaction:
                      prev.ats_satisfaction === true ? null : true,
                  }))
                }
              />
              <ThumbsButton
                selected={rating.ats_satisfaction}
                isUp={false}
                onClick={() =>
                  setRating((prev) => ({
                    ...prev,
                    ats_satisfaction:
                      prev.ats_satisfaction === false ? null : false,
                  }))
                }
              />
            </div>
          </div>

          {/* Would Send As-Is */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Would you send this as-is?
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() =>
                  setRating((prev) => ({
                    ...prev,
                    would_send_as_is:
                      prev.would_send_as_is === true ? null : true,
                  }))
                }
                className={`px-4 py-2 rounded-md border transition-all ${
                  rating.would_send_as_is === true
                    ? "border-green-500 bg-green-50 text-green-700"
                    : "border-gray-300 text-gray-600 hover:border-gray-400"
                }`}
              >
                Yes
              </button>
              <button
                type="button"
                onClick={() =>
                  setRating((prev) => ({
                    ...prev,
                    would_send_as_is:
                      prev.would_send_as_is === false ? null : false,
                  }))
                }
                className={`px-4 py-2 rounded-md border transition-all ${
                  rating.would_send_as_is === false
                    ? "border-red-500 bg-red-50 text-red-700"
                    : "border-gray-300 text-gray-600 hover:border-gray-400"
                }`}
              >
                No
              </button>
            </div>
          </div>

          {/* Optional Feedback */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Additional feedback (optional)
            </label>
            <textarea
              value={rating.feedback_text}
              onChange={(e) =>
                setRating((prev) => ({ ...prev, feedback_text: e.target.value }))
              }
              placeholder="What could be improved?"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? "Submitting..." : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
}
