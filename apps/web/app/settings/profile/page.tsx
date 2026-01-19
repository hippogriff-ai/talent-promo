"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/app/hooks/useAuth";
import { usePreferences, UserPreferences } from "@/app/hooks/usePreferences";
import { AuthGuard } from "@/app/components/auth/AuthGuard";

const TONE_OPTIONS = [
  { value: "formal", label: "Formal", description: "Professional and structured" },
  { value: "conversational", label: "Conversational", description: "Friendly and approachable" },
  { value: "confident", label: "Confident", description: "Bold and assertive" },
  { value: "humble", label: "Humble", description: "Modest and understated" },
];

const STRUCTURE_OPTIONS = [
  { value: "bullets", label: "Bullet Points", description: "Concise, scannable items" },
  { value: "paragraphs", label: "Paragraphs", description: "Flowing narrative style" },
  { value: "mixed", label: "Mixed", description: "Combination of both" },
];

const SENTENCE_OPTIONS = [
  { value: "concise", label: "Concise", description: "Short, punchy sentences" },
  { value: "detailed", label: "Detailed", description: "Comprehensive explanations" },
  { value: "mixed", label: "Mixed", description: "Varies by context" },
];

const QUANT_OPTIONS = [
  { value: "heavy_metrics", label: "Data-Driven", description: "Lots of numbers and percentages" },
  { value: "qualitative", label: "Qualitative", description: "Focus on impact descriptions" },
  { value: "balanced", label: "Balanced", description: "Mix of metrics and narrative" },
];

function RadioGroup({
  label,
  name,
  value,
  options,
  onChange,
}: {
  label: string;
  name: string;
  value: string | null;
  options: { value: string; label: string; description: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {options.map((option) => (
          <label
            key={option.value}
            className={`relative flex cursor-pointer rounded-lg border p-4 focus:outline-none ${
              value === option.value
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            <div className="flex flex-col">
              <span
                className={`text-sm font-medium ${
                  value === option.value ? "text-blue-900" : "text-gray-900"
                }`}
              >
                {option.label}
              </span>
              <span
                className={`text-xs ${
                  value === option.value ? "text-blue-700" : "text-gray-500"
                }`}
              >
                {option.description}
              </span>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean | null;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
          checked ? "bg-blue-600" : "bg-gray-200"
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

function SettingsContent() {
  const { user, logout } = useAuth();
  const { preferences, isLoading, updatePreferences, resetPreferences } = usePreferences();
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleChange = async (key: keyof UserPreferences, value: unknown) => {
    setIsSaving(true);
    setMessage(null);

    const success = await updatePreferences({ [key]: value });

    if (success) {
      setMessage({ type: "success", text: "Preferences saved" });
    } else {
      setMessage({ type: "error", text: "Failed to save preferences" });
    }

    setIsSaving(false);
    setTimeout(() => setMessage(null), 3000);
  };

  const handleReset = async () => {
    if (!confirm("Reset all preferences to defaults?")) return;

    setIsSaving(true);
    const success = await resetPreferences();

    if (success) {
      setMessage({ type: "success", text: "Preferences reset" });
    } else {
      setMessage({ type: "error", text: "Failed to reset preferences" });
    }

    setIsSaving(false);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <Link href="/" className="text-sm text-blue-600 hover:text-blue-500">
            ← Back to home
          </Link>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">Profile Settings</h1>
          <p className="mt-1 text-sm text-gray-600">
            Customize how your resumes are generated.
          </p>
        </div>

        {/* User Info */}
        {user && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Signed in as</p>
                <p className="font-medium text-gray-900">{user.email}</p>
              </div>
              <button
                onClick={logout}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Sign out
              </button>
            </div>
          </div>
        )}

        {/* Status Message */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-md ${
              message.type === "success"
                ? "bg-green-50 text-green-800"
                : "bg-red-50 text-red-800"
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Writing Style */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Writing Style</h2>
          <div className="space-y-8">
            <RadioGroup
              label="Tone"
              name="tone"
              value={preferences.tone}
              options={TONE_OPTIONS}
              onChange={(value) => handleChange("tone", value)}
            />

            <RadioGroup
              label="Structure"
              name="structure"
              value={preferences.structure}
              options={STRUCTURE_OPTIONS}
              onChange={(value) => handleChange("structure", value)}
            />

            <RadioGroup
              label="Sentence Length"
              name="sentence_length"
              value={preferences.sentence_length}
              options={SENTENCE_OPTIONS}
              onChange={(value) => handleChange("sentence_length", value)}
            />

            <Toggle
              label="First Person"
              description="Use 'I' statements in descriptions"
              checked={preferences.first_person}
              onChange={(value) => handleChange("first_person", value)}
            />
          </div>
        </div>

        {/* Content Preferences */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Content Preferences</h2>
          <div className="space-y-8">
            <RadioGroup
              label="Quantification"
              name="quantification_preference"
              value={preferences.quantification_preference}
              options={QUANT_OPTIONS}
              onChange={(value) => handleChange("quantification_preference", value)}
            />

            <Toggle
              label="Achievement Focus"
              description="Emphasize accomplishments over responsibilities"
              checked={preferences.achievement_focus}
              onChange={(value) => handleChange("achievement_focus", value)}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Actions</h2>
          <div className="space-y-4">
            <button
              onClick={handleReset}
              disabled={isSaving}
              className="w-full px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              Reset to Defaults
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <AuthGuard redirectTo="/auth/login">
      <SettingsContent />
    </AuthGuard>
  );
}
