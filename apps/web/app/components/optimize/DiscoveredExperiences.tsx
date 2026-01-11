"use client";

import { DiscoveredExperience } from "../../hooks/useDiscoveryStorage";

interface DiscoveredExperiencesProps {
  experiences: DiscoveredExperience[];
  compact?: boolean;
}

/**
 * Displays the list of discovered experiences.
 *
 * Each experience shows:
 * - Description
 * - Source quote from conversation
 * - Mapped job requirements
 */
export default function DiscoveredExperiences({
  experiences,
  compact = false,
}: DiscoveredExperiencesProps) {
  if (experiences.length === 0) {
    return (
      <div className={`${compact ? "p-3" : "bg-white rounded-lg shadow p-6"}`}>
        <h4
          className={`${
            compact ? "text-sm font-medium" : "text-lg font-semibold"
          } text-gray-900 mb-2`}
        >
          Discovered Experiences
        </h4>
        <p className="text-sm text-gray-500 italic">
          No experiences discovered yet. Keep answering questions!
        </p>
      </div>
    );
  }

  if (compact) {
    return (
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-gray-900">
          Discovered ({experiences.length})
        </h4>
        <ul className="space-y-2">
          {experiences.slice(0, 3).map((exp) => (
            <li
              key={exp.id}
              className="text-sm bg-green-50 rounded-lg px-3 py-2"
            >
              <p className="text-gray-700 line-clamp-2">{exp.description}</p>
              {exp.mappedRequirements.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {exp.mappedRequirements.slice(0, 2).map((req, idx) => (
                    <span
                      key={idx}
                      className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded"
                    >
                      {req.length > 20 ? req.slice(0, 20) + "..." : req}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
          {experiences.length > 3 && (
            <li className="text-xs text-gray-500">
              +{experiences.length - 3} more
            </li>
          )}
        </ul>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          Discovered Experiences
        </h3>
        <span className="px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full">
          {experiences.length} found
        </span>
      </div>

      <div className="space-y-4">
        {experiences.map((exp) => (
          <div
            key={exp.id}
            className="border border-green-200 rounded-lg p-4 bg-green-50"
          >
            {/* Description */}
            <p className="text-gray-800 font-medium">{exp.description}</p>

            {/* Source quote */}
            {exp.sourceQuote && (
              <div className="mt-2 pl-3 border-l-2 border-green-300">
                <p className="text-sm text-gray-600 italic">
                  &quot;{exp.sourceQuote}&quot;
                </p>
              </div>
            )}

            {/* Mapped requirements */}
            {exp.mappedRequirements.length > 0 && (
              <div className="mt-3">
                <p className="text-xs text-gray-500 mb-1">
                  Addresses requirements:
                </p>
                <div className="flex flex-wrap gap-1">
                  {exp.mappedRequirements.map((req, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded"
                    >
                      {req}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Timestamp */}
            <p className="text-xs text-gray-400 mt-2">
              Discovered{" "}
              {new Date(exp.discoveredAt).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
        ))}
      </div>

      {experiences.length > 0 && (
        <div className="mt-4 pt-4 border-t text-sm text-gray-500">
          These experiences will be incorporated into your optimized resume.
        </div>
      )}
    </div>
  );
}
