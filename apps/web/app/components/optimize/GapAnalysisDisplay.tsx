"use client";

import { GapAnalysis } from "../../hooks/useWorkflow";

interface GapItem {
  description: string;
  requirement_id?: string;
  requirement_text?: string;
  priority: number;
}

interface OpportunityItem {
  description: string;
  related_gaps: string[];
  potential_impact: string;
}

interface ExtendedGapAnalysis extends GapAnalysis {
  gaps_detailed?: GapItem[];
  opportunities?: OpportunityItem[];
}

interface GapAnalysisDisplayProps {
  gapAnalysis: ExtendedGapAnalysis;
  compact?: boolean;
}

/**
 * Displays the gap analysis results with:
 * - Gaps (missing qualifications) linked to job requirements
 * - Strengths (matching qualifications)
 * - Opportunities (potential angles to explore)
 */
export default function GapAnalysisDisplay({
  gapAnalysis,
  compact = false,
}: GapAnalysisDisplayProps) {
  const gaps = gapAnalysis.gaps_detailed || [];
  const opportunities = gapAnalysis.opportunities || [];
  const strengths = gapAnalysis.strengths || [];

  if (compact) {
    return (
      <div className="space-y-3">
        {/* Compact view for sidebar */}
        {strengths.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-green-700 mb-1">
              Your Strengths
            </h4>
            <ul className="text-sm text-gray-600 space-y-1">
              {strengths.slice(0, 3).map((strength, idx) => (
                <li key={idx} className="flex items-start">
                  <span className="text-green-500 mr-1 flex-shrink-0">+</span>
                  <span>{strength}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {gaps.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-amber-700 mb-1">
              Gaps to Address
            </h4>
            <ul className="text-sm text-gray-600 space-y-1">
              {gaps.slice(0, 3).map((gap, idx) => (
                <li key={idx} className="flex items-start">
                  <span className="text-amber-500 mr-1 flex-shrink-0">-</span>
                  <span>{gap.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {opportunities.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-blue-700 mb-1">
              Opportunities
            </h4>
            <ul className="text-sm text-gray-600 space-y-1">
              {opportunities.slice(0, 2).map((opp, idx) => (
                <li key={idx} className="flex items-start">
                  <span className="text-blue-500 mr-1 flex-shrink-0">*</span>
                  <span>{opp.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      <h3 className="text-lg font-semibold text-gray-900">Gap Analysis</h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Strengths */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
              <svg
                className="w-4 h-4 text-green-600"
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
            </div>
            <h4 className="font-medium text-green-800">
              Strengths ({strengths.length})
            </h4>
          </div>
          <ul className="space-y-2">
            {strengths.map((strength, idx) => (
              <li
                key={idx}
                className="text-sm text-gray-700 bg-green-50 rounded-lg px-3 py-2"
              >
                {strength}
              </li>
            ))}
            {strengths.length === 0 && (
              <li className="text-sm text-gray-500 italic">
                No matching strengths identified
              </li>
            )}
          </ul>
        </div>

        {/* Gaps */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
              <svg
                className="w-4 h-4 text-amber-600"
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
            </div>
            <h4 className="font-medium text-amber-800">
              Gaps ({gaps.length || gapAnalysis.gaps?.length || 0})
            </h4>
          </div>
          <ul className="space-y-2">
            {gaps.length > 0
              ? gaps.map((gap, idx) => (
                  <li
                    key={idx}
                    className="text-sm bg-amber-50 rounded-lg px-3 py-2"
                  >
                    <p className="text-gray-700">{gap.description}</p>
                    {gap.requirement_text && (
                      <p className="text-xs text-amber-600 mt-1">
                        Requirement: {gap.requirement_text}
                      </p>
                    )}
                  </li>
                ))
              : gapAnalysis.gaps?.map((gap, idx) => (
                  <li
                    key={idx}
                    className="text-sm text-gray-700 bg-amber-50 rounded-lg px-3 py-2"
                  >
                    {gap}
                  </li>
                ))}
            {gaps.length === 0 && (!gapAnalysis.gaps || gapAnalysis.gaps.length === 0) && (
              <li className="text-sm text-gray-500 italic">
                No gaps identified - great match!
              </li>
            )}
          </ul>
        </div>

        {/* Opportunities */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
              <svg
                className="w-4 h-4 text-blue-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                />
              </svg>
            </div>
            <h4 className="font-medium text-blue-800">
              Opportunities ({opportunities.length})
            </h4>
          </div>
          <ul className="space-y-2">
            {opportunities.map((opp, idx) => (
              <li key={idx} className="text-sm bg-blue-50 rounded-lg px-3 py-2">
                <p className="text-gray-700">{opp.description}</p>
                {opp.potential_impact && (
                  <span
                    className={`inline-block mt-1 px-2 py-0.5 text-xs rounded ${
                      opp.potential_impact === "high"
                        ? "bg-blue-200 text-blue-800"
                        : opp.potential_impact === "medium"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {opp.potential_impact} impact
                  </span>
                )}
              </li>
            ))}
            {opportunities.length === 0 && (
              <li className="text-sm text-gray-500 italic">
                Discovery will help find opportunities
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
