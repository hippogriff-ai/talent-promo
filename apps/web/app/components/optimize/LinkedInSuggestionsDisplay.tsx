"use client";

import { useState } from "react";
import { LinkedInSuggestion } from "../../hooks/useExportStorage";

interface LinkedInSuggestionsDisplayProps {
  suggestions: LinkedInSuggestion;
}

/**
 * LinkedIn Suggestions display component.
 *
 * Shows:
 * - Suggested headline with copy button
 * - Suggested summary/about section
 * - Experience bullets mapped to sections
 */
export default function LinkedInSuggestionsDisplay({
  suggestions,
}: LinkedInSuggestionsDisplayProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleCopy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch (error) {
      console.error("Failed to copy:", error);
    }
  };

  return (
    <div className="space-y-6" data-testid="linkedin-suggestions">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 bg-blue-600 rounded flex items-center justify-center">
          <span className="text-white font-bold text-lg">in</span>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            LinkedIn Profile Suggestions
          </h3>
          <p className="text-sm text-gray-500">
            Optimized content for your LinkedIn profile
          </p>
        </div>
      </div>

      {/* Headline */}
      <div className="bg-white border rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-gray-900">Headline</h4>
          <button
            onClick={() => handleCopy(suggestions.headline, "headline")}
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center space-x-1"
            data-testid="copy-headline"
          >
            {copiedField === "headline" ? (
              <>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                <span>Copied!</span>
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                  />
                </svg>
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
        <p
          className="text-gray-700 bg-gray-50 p-3 rounded border"
          data-testid="headline-content"
        >
          {suggestions.headline || "No headline suggestion available"}
        </p>
        <p className="text-xs text-gray-500 mt-2">
          Max 220 characters • Shows below your name on LinkedIn
        </p>
      </div>

      {/* Summary/About */}
      <div className="bg-white border rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-gray-900">About Section</h4>
          <button
            onClick={() => handleCopy(suggestions.summary, "summary")}
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center space-x-1"
            data-testid="copy-summary"
          >
            {copiedField === "summary" ? (
              <>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                <span>Copied!</span>
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                  />
                </svg>
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
        <div
          className="text-gray-700 bg-gray-50 p-3 rounded border whitespace-pre-wrap max-h-48 overflow-y-auto"
          data-testid="summary-content"
        >
          {suggestions.summary || "No summary suggestion available"}
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Max 2,600 characters • Your professional story
        </p>
      </div>

      {/* Experience Bullets */}
      {suggestions.experience_bullets.length > 0 && (
        <div className="bg-white border rounded-lg p-4">
          <h4 className="font-medium text-gray-900 mb-4">Experience Bullets</h4>
          <div
            className="space-y-4"
            data-testid="experience-bullets"
          >
            {suggestions.experience_bullets.map((exp, idx) => (
              <div
                key={idx}
                className="border-l-2 border-blue-200 pl-4"
                data-testid={`experience-${idx}`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{exp.position}</p>
                    <p className="text-sm text-gray-600">{exp.company}</p>
                  </div>
                  <button
                    onClick={() =>
                      handleCopy(exp.bullets.join("\n• "), `exp-${idx}`)
                    }
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    {copiedField === `exp-${idx}` ? "Copied!" : "Copy bullets"}
                  </button>
                </div>
                {exp.bullets.length > 0 && (
                  <ul className="mt-2 space-y-1 text-sm text-gray-700">
                    {exp.bullets.map((bullet, bulletIdx) => (
                      <li key={bulletIdx} className="flex items-start">
                        <span className="mr-2 text-blue-500">•</span>
                        <span>{bullet}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="bg-gray-50 border rounded-lg p-4">
        <h4 className="font-medium text-gray-900 mb-2">
          Tips for LinkedIn Optimization
        </h4>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>• Use keywords from the job posting in your headline</li>
          <li>• Keep your summary focused on your target role</li>
          <li>• Quantify achievements where possible</li>
          <li>• Match your resume bullets to LinkedIn experience</li>
        </ul>
      </div>
    </div>
  );
}
