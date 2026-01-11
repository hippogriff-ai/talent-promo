"use client";

import { ATSReport } from "../../hooks/useExportStorage";

interface ATSReportDisplayProps {
  report: ATSReport;
}

/**
 * ATS Report display component.
 *
 * Shows:
 * - Keyword match score with visual indicator
 * - Matched keywords
 * - Missing keywords
 * - Formatting issues
 * - Recommendations
 */
export default function ATSReportDisplay({ report }: ATSReportDisplayProps) {
  const isPassing = report.keyword_match_score >= 70;
  const scoreColor = isPassing ? "text-green-600" : "text-amber-600";
  const scoreBgColor = isPassing ? "bg-green-50" : "bg-amber-50";
  const scoreBorderColor = isPassing ? "border-green-200" : "border-amber-200";

  return (
    <div className="space-y-6" data-testid="ats-report">
      {/* Score Card */}
      <div
        className={`${scoreBgColor} ${scoreBorderColor} border rounded-lg p-6`}
        data-testid="ats-score-card"
      >
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              ATS Compatibility Score
            </h3>
            <p className="text-sm text-gray-600 mt-1">
              {isPassing
                ? "Your resume is well-optimized for ATS systems"
                : "Consider adding more keywords to improve ATS compatibility"}
            </p>
          </div>
          <div className="text-right">
            <span
              className={`text-4xl font-bold ${scoreColor}`}
              data-testid="ats-score-value"
            >
              {report.keyword_match_score}%
            </span>
            <p className="text-sm text-gray-500 mt-1">
              {isPassing ? "Passing" : "Needs Improvement"}
            </p>
          </div>
        </div>

        {/* Score Bar */}
        <div className="mt-4">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all ${
                isPassing ? "bg-green-500" : "bg-amber-500"
              }`}
              style={{ width: `${report.keyword_match_score}%` }}
              data-testid="ats-score-bar"
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>0%</span>
            <span>70% (Passing)</span>
            <span>100%</span>
          </div>
        </div>
      </div>

      {/* Keywords Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Matched Keywords */}
        <div className="bg-white border rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-3">
            <svg
              className="w-5 h-5 text-green-500"
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
            <h4 className="font-medium text-gray-900">
              Matched Keywords ({report.matched_keywords.length})
            </h4>
          </div>
          <div className="flex flex-wrap gap-2" data-testid="matched-keywords">
            {report.matched_keywords.length > 0 ? (
              report.matched_keywords.map((keyword, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-green-100 text-green-800 text-sm rounded"
                >
                  {keyword}
                </span>
              ))
            ) : (
              <p className="text-sm text-gray-500">No keywords matched</p>
            )}
          </div>
        </div>

        {/* Missing Keywords */}
        <div className="bg-white border rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-3">
            <svg
              className="w-5 h-5 text-amber-500"
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
            <h4 className="font-medium text-gray-900">
              Missing Keywords ({report.missing_keywords.length})
            </h4>
          </div>
          <div className="flex flex-wrap gap-2" data-testid="missing-keywords">
            {report.missing_keywords.length > 0 ? (
              report.missing_keywords.map((keyword, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-amber-100 text-amber-800 text-sm rounded"
                >
                  {keyword}
                </span>
              ))
            ) : (
              <p className="text-sm text-gray-500">All keywords matched!</p>
            )}
          </div>
        </div>
      </div>

      {/* Formatting Issues */}
      {report.formatting_issues.length > 0 && (
        <div className="bg-white border border-red-200 rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-3">
            <svg
              className="w-5 h-5 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h4 className="font-medium text-gray-900">Formatting Issues</h4>
          </div>
          <ul
            className="space-y-2 text-sm text-gray-700"
            data-testid="formatting-issues"
          >
            {report.formatting_issues.map((issue, idx) => (
              <li key={idx} className="flex items-start space-x-2">
                <span className="text-red-500 mt-1">•</span>
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center space-x-2 mb-3">
            <svg
              className="w-5 h-5 text-blue-500"
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
            <h4 className="font-medium text-gray-900">Recommendations</h4>
          </div>
          <ul
            className="space-y-2 text-sm text-gray-700"
            data-testid="recommendations"
          >
            {report.recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start space-x-2">
                <span className="text-blue-500 mt-1">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
