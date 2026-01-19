"use client";

import { useState } from "react";
import Link from "next/link";
import { usePreferences, UserPreferences } from "../../hooks/usePreferences";

/**
 * Quick toggle component for boolean preferences.
 */
function QuickToggle({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-center justify-between py-2">
      <span className="text-sm text-gray-700">{label}</span>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        disabled={disabled}
        className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
          checked ? "bg-blue-600" : "bg-gray-200"
        } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <span
          className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </button>
    </label>
  );
}

/**
 * Quick select component for string preferences.
 */
function QuickSelect({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: string | null;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="py-2">
      <label className="block text-sm text-gray-700 mb-1">{label}</label>
      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 disabled:opacity-50"
      >
        <option value="">Default</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * Preference sidebar for the resume editor.
 *
 * Displays a collapsible sidebar with quick toggles for common preferences.
 * Shows "Learned from your edits" indicator when preferences have been
 * automatically detected from user behavior.
 *
 * Features:
 * - Collapsed by default (icon button to expand)
 * - Quick toggles for common preferences
 * - "View all" link to full settings page
 * - Shows learned preferences indicator
 *
 * @example
 * ```tsx
 * // In your editor layout:
 * <div className="flex">
 *   <div className="flex-1">
 *     <Editor />
 *   </div>
 *   <PreferenceSidebar />
 * </div>
 * ```
 */
export function PreferenceSidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const { preferences, isLoading, updatePreferences } = usePreferences();
  const [isSaving, setIsSaving] = useState(false);

  const handleChange = async (key: keyof UserPreferences, value: unknown) => {
    setIsSaving(true);
    await updatePreferences({ [key]: value });
    setIsSaving(false);
  };

  // Check if any preferences have been set (learned or explicit)
  const hasLearnedPreferences =
    preferences.tone ||
    preferences.structure ||
    preferences.first_person !== null ||
    preferences.quantification_preference ||
    preferences.achievement_focus !== null;

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed right-4 top-1/2 -translate-y-1/2 p-2 bg-white rounded-l-lg shadow-lg border border-r-0 border-gray-200 hover:bg-gray-50 transition-colors z-40"
        title="Open preferences"
      >
        <svg
          className="w-5 h-5 text-gray-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        {hasLearnedPreferences && (
          <span className="absolute -top-1 -right-1 w-2 h-2 bg-blue-500 rounded-full" />
        )}
      </button>
    );
  }

  return (
    <div className="fixed right-0 top-0 h-full w-72 bg-white shadow-lg border-l border-gray-200 z-50 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Preferences</h3>
        <button
          onClick={() => setIsOpen(false)}
          className="p-1 text-gray-400 hover:text-gray-600 rounded"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Learned indicator */}
      {hasLearnedPreferences && (
        <div className="mx-4 mt-4 p-2 bg-blue-50 rounded-md flex items-center text-sm text-blue-700">
          <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          Learned from your edits
        </div>
      )}

      {/* Quick preferences */}
      <div className="p-4 space-y-2">
        {isLoading ? (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        ) : (
          <>
            <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              Writing Style
            </h4>

            <QuickSelect
              label="Tone"
              value={preferences.tone}
              options={[
                { value: "formal", label: "Formal" },
                { value: "conversational", label: "Conversational" },
                { value: "confident", label: "Confident" },
                { value: "humble", label: "Humble" },
              ]}
              onChange={(v) => handleChange("tone", v)}
              disabled={isSaving}
            />

            <QuickSelect
              label="Structure"
              value={preferences.structure}
              options={[
                { value: "bullets", label: "Bullet Points" },
                { value: "paragraphs", label: "Paragraphs" },
                { value: "mixed", label: "Mixed" },
              ]}
              onChange={(v) => handleChange("structure", v)}
              disabled={isSaving}
            />

            <QuickToggle
              label="First Person ('I')"
              checked={preferences.first_person ?? false}
              onChange={(v) => handleChange("first_person", v)}
              disabled={isSaving}
            />

            <div className="border-t border-gray-100 my-3" />

            <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              Content
            </h4>

            <QuickSelect
              label="Quantification"
              value={preferences.quantification_preference}
              options={[
                { value: "heavy_metrics", label: "Data-Driven" },
                { value: "qualitative", label: "Qualitative" },
                { value: "balanced", label: "Balanced" },
              ]}
              onChange={(v) => handleChange("quantification_preference", v)}
              disabled={isSaving}
            />

            <QuickToggle
              label="Achievement Focus"
              checked={preferences.achievement_focus ?? false}
              onChange={(v) => handleChange("achievement_focus", v)}
              disabled={isSaving}
            />
          </>
        )}
      </div>

      {/* Footer */}
      <div className="sticky bottom-0 bg-white border-t border-gray-200 p-4">
        <Link
          href="/settings/profile"
          className="block w-full text-center text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          View All Preferences →
        </Link>
      </div>
    </div>
  );
}

export default PreferenceSidebar;
