"use client";

import { useState } from "react";
import type { ValidationResults, BiasFlag, PIIWarning, UngroundedClaim } from "../../types/guardrails";
import { BIAS_CATEGORIES, PII_TYPES, CLAIM_TYPES } from "../../types/guardrails";

interface ValidationWarningsProps {
  validation: ValidationResults | null;
  onDismiss?: () => void;
}

/**
 * Displays AI safety validation warnings for bias and PII detection.
 *
 * Shows collapsible sections for different warning categories with
 * actionable suggestions where available.
 */
export function ValidationWarnings({ validation, onDismiss }: ValidationWarningsProps) {
  const [expanded, setExpanded] = useState(true);

  if (!validation) return null;

  const hasWarnings =
    validation.bias_flags?.length > 0 ||
    validation.pii_warnings?.length > 0 ||
    validation.ungrounded_claims?.length > 0 ||
    validation.warnings?.length > 0;

  if (!hasWarnings) return null;

  // Group bias flags by category
  const biasByCategory: Record<string, BiasFlag[]> = {};
  for (const flag of validation.bias_flags || []) {
    if (!biasByCategory[flag.category]) {
      biasByCategory[flag.category] = [];
    }
    biasByCategory[flag.category].push(flag);
  }

  return (
    <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50">
      {/* Header */}
      <div
        className="flex cursor-pointer items-center justify-between px-4 py-3"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <svg
            className="h-5 w-5 text-amber-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <span className="font-medium text-amber-800">
            Content Warnings ({validation.bias_flags?.length || 0} bias,{" "}
            {validation.pii_warnings?.length || 0} PII,{" "}
            {validation.ungrounded_claims?.length || 0} unverified)
          </span>
        </div>
        <div className="flex items-center gap-2">
          {onDismiss && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDismiss();
              }}
              className="text-amber-600 hover:text-amber-800"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
          <svg
            className={`h-5 w-5 text-amber-600 transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Content */}
      {expanded && (
        <div className="border-t border-amber-200 px-4 py-3">
          {/* Bias warnings by category */}
          {Object.entries(biasByCategory).map(([category, flags]) => (
            <div key={category} className="mb-4 last:mb-0">
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-900">
                <CategoryIcon category={category} />
                {BIAS_CATEGORIES[category]?.label || category}
              </h4>
              <ul className="space-y-2">
                {flags.map((flag, idx) => (
                  <li
                    key={idx}
                    className="rounded bg-white p-2 text-sm shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-medium text-amber-800">
                          &ldquo;{flag.term}&rdquo;
                        </span>
                        <p className="mt-1 text-gray-600">{flag.message}</p>
                        {flag.suggestion && (
                          <p className="mt-1 text-green-700">
                            <span className="font-medium">Suggestion:</span> Use &ldquo;
                            {flag.suggestion}&rdquo; instead
                          </p>
                        )}
                      </div>
                      <span
                        className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${
                          flag.severity === "block"
                            ? "bg-red-100 text-red-700"
                            : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {flag.severity}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* PII warnings */}
          {validation.pii_warnings && validation.pii_warnings.length > 0 && (
            <div className="mb-4 last:mb-0">
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-900">
                <svg
                  className="h-4 w-4 text-red-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  />
                </svg>
                Sensitive Information Detected
              </h4>
              <ul className="space-y-2">
                {validation.pii_warnings.map((pii, idx) => (
                  <li
                    key={idx}
                    className="rounded bg-white p-2 text-sm shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-medium text-red-800">
                          {PII_TYPES[pii.type] || pii.type}
                        </span>
                        <p className="mt-1 text-gray-600">{pii.message}</p>
                        <p className="mt-1 font-mono text-xs text-gray-500">
                          Value: {pii.masked_value}
                        </p>
                      </div>
                      <span className="shrink-0 rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                        {pii.severity}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Ungrounded claims */}
          {validation.ungrounded_claims && validation.ungrounded_claims.length > 0 && (
            <div className="mb-4 last:mb-0">
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-blue-900">
                <svg
                  className="h-4 w-4 text-blue-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Unverified Claims
              </h4>
              <p className="mb-2 text-xs text-gray-500">
                These claims could not be confirmed from your profile. Please verify they are accurate.
              </p>
              <ul className="space-y-2">
                {validation.ungrounded_claims.map((claim, idx) => (
                  <li
                    key={idx}
                    className="rounded bg-white p-2 text-sm shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-medium text-blue-800">
                          {claim.claim}
                        </span>
                        <p className="mt-1 text-gray-600">{claim.message}</p>
                      </div>
                      <span className="shrink-0 rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                        {CLAIM_TYPES[claim.type] || claim.type}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* General warnings */}
          {validation.warnings && validation.warnings.length > 0 && (
            <div className="mb-4 last:mb-0">
              <h4 className="mb-2 text-sm font-semibold text-amber-900">
                Other Warnings
              </h4>
              <ul className="space-y-1">
                {validation.warnings.map((warning, idx) => (
                  <li key={idx} className="text-sm text-gray-600">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Sanitization notice */}
          {validation.sanitized && (
            <div className="mt-3 rounded bg-blue-50 p-2 text-sm text-blue-800">
              <span className="font-medium">Note:</span> Some content was
              automatically cleaned up to remove problematic patterns.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Icon for bias category.
 */
function CategoryIcon({ category }: { category: string }) {
  switch (category) {
    case "age":
      return (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      );
    case "gender":
      return (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
          />
        </svg>
      );
    default:
      return (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      );
  }
}

export default ValidationWarnings;
