"use client";

import { VariantStatus } from "@/app/hooks/useArena";

interface VariantPanelProps {
  variant: "A" | "B";
  status: VariantStatus | null;
  label: string;
}

export function VariantPanel({ variant, status, label }: VariantPanelProps) {
  if (!status) {
    return (
      <div className="border rounded-lg p-4 bg-gray-50">
        <h3 className="font-semibold mb-2">Variant {variant}: {label}</h3>
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  const getStatusColor = (s: string) => {
    switch (s) {
      case "completed":
        return "text-green-600 bg-green-100";
      case "error":
        return "text-red-600 bg-red-100";
      case "waiting_input":
        return "text-yellow-600 bg-yellow-100";
      default:
        return "text-blue-600 bg-blue-100";
    }
  };

  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold">Variant {variant}: {label}</h3>
        <span className={`px-2 py-1 rounded text-sm ${getStatusColor(status.status)}`}>
          {status.status}
        </span>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-sm text-gray-500">Current Step</p>
          <p className="font-medium">{status.current_step || "N/A"}</p>
        </div>

        {status.progress_messages && status.progress_messages.length > 0 && (
          <div>
            <p className="text-sm text-gray-500 mb-2">Recent Progress</p>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {status.progress_messages.slice(-3).map((msg, i) => (
                <p key={i} className="text-xs text-gray-600 bg-gray-50 p-1 rounded">
                  {msg.message}
                </p>
              ))}
            </div>
          </div>
        )}

        {status.resume_html && (
          <div>
            <p className="text-sm text-gray-500 mb-2">Resume Preview</p>
            <pre className="text-xs border rounded p-2 max-h-48 overflow-y-auto bg-gray-50 whitespace-pre-wrap">
              {status.resume_html.replace(/<[^>]*>/g, "").slice(0, 1000)}...
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
