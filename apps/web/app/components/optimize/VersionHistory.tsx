"use client";

import { useState } from "react";
import type { DraftVersion, VersionTrigger } from "../../hooks/useDraftingStorage";

interface VersionHistoryProps {
  versions: DraftVersion[];
  currentVersion: string;
  onRestore: (version: string) => Promise<void>;
  isLoading?: boolean;
}

/**
 * Component displaying version history with restore functionality.
 */
export default function VersionHistory({
  versions,
  currentVersion,
  onRestore,
  isLoading = false,
}: VersionHistoryProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [restoringVersion, setRestoringVersion] = useState<string | null>(null);

  // Sort versions by created date (newest first)
  const sortedVersions = [...versions].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  const handleRestore = async (version: string) => {
    if (version === currentVersion) return;

    setRestoringVersion(version);
    try {
      await onRestore(version);
    } finally {
      setRestoringVersion(null);
    }
  };

  return (
    <div className="relative" data-testid="version-history">
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        data-testid="version-history-toggle"
      >
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
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span>v{currentVersion}</span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          <div className="p-3 border-b border-gray-100">
            <h3 className="font-medium text-gray-900">Version History</h3>
            <p className="text-xs text-gray-500">Last 5 versions saved</p>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {sortedVersions.map((version, index) => {
              const isCurrent = version.version === currentVersion;
              const isRestoring = restoringVersion === version.version;

              return (
                <div
                  key={version.version}
                  className={`p-3 border-b border-gray-50 last:border-b-0 ${
                    isCurrent ? "bg-blue-50" : "hover:bg-gray-50"
                  }`}
                  data-testid={`version-item-${version.version}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`font-medium ${
                            isCurrent ? "text-blue-700" : "text-gray-900"
                          }`}
                        >
                          v{version.version}
                        </span>
                        {isCurrent && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                            Current
                          </span>
                        )}
                        <span
                          className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs ${getTriggerStyle(
                            version.trigger
                          )}`}
                        >
                          {getTriggerLabel(version.trigger)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1 truncate">
                        {version.description}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {formatDate(version.createdAt)}
                      </p>
                    </div>

                    {!isCurrent && (
                      <button
                        onClick={() => handleRestore(version.version)}
                        disabled={isLoading || isRestoring}
                        className="ml-2 px-2 py-1 text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                        data-testid={`restore-button-${version.version}`}
                      >
                        {isRestoring ? "..." : "Restore"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {versions.length === 0 && (
            <div className="p-4 text-center text-gray-500 text-sm">
              No version history yet
            </div>
          )}
        </div>
      )}

      {/* Backdrop to close dropdown */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}

/**
 * Get style for trigger badge.
 */
function getTriggerStyle(trigger: VersionTrigger): string {
  switch (trigger) {
    case "initial":
      return "bg-green-100 text-green-700";
    case "accept":
      return "bg-green-100 text-green-700";
    case "decline":
      return "bg-gray-100 text-gray-700";
    case "edit":
      return "bg-amber-100 text-amber-700";
    case "manual_save":
      return "bg-blue-100 text-blue-700";
    case "auto_checkpoint":
      return "bg-cyan-100 text-cyan-700";
    case "restore":
      return "bg-green-100 text-green-700";
    default:
      return "bg-gray-100 text-gray-700";
  }
}

/**
 * Get label for trigger.
 */
function getTriggerLabel(trigger: VersionTrigger): string {
  switch (trigger) {
    case "initial":
      return "Initial";
    case "accept":
      return "Accepted";
    case "decline":
      return "Declined";
    case "edit":
      return "Edited";
    case "manual_save":
      return "Saved";
    case "auto_checkpoint":
      return "Auto";
    case "restore":
      return "Restored";
    default:
      return trigger;
  }
}

/**
 * Format date for display.
 */
function formatDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  // Less than 1 minute
  if (diff < 60000) {
    return "Just now";
  }

  // Less than 1 hour
  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000);
    return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }

  // Less than 24 hours
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000);
    return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  }

  // Otherwise show date and time
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Compact version indicator for toolbar.
 */
interface VersionIndicatorProps {
  currentVersion: string;
  onClick?: () => void;
}

export function VersionIndicator({ currentVersion, onClick }: VersionIndicatorProps) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center px-2 py-1 text-xs text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
    >
      <svg
        className="w-3 h-3 mr-1"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      v{currentVersion}
    </button>
  );
}
