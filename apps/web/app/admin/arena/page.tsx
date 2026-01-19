"use client";

import { useState, useEffect, useCallback } from "react";
import { useArena, ArenaStatus, Analytics, ArenaComparison, ArenaStreamEvent } from "@/app/hooks/useArena";
import { VariantPanel } from "./components/VariantPanel";
import { PreferenceRating } from "./components/PreferenceRating";
import { AnalyticsDashboard } from "./components/AnalyticsDashboard";
import { ComparisonHistory } from "./components/ComparisonHistory";
import { MetricsPanel } from "./components/MetricsPanel";
import { LiveProgress } from "./components/LiveProgress";

const ADMIN_TOKEN_KEY = "arena_admin_token";

interface FormFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  multiline?: boolean;
}

function FormField({ label, value, onChange, placeholder, multiline }: FormFieldProps): JSX.Element {
  const className = "w-full px-3 py-2 border rounded";
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={className}
          rows={6}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={className}
        />
      )}
    </div>
  );
}

const PREFERENCE_STYLES: Record<string, string> = {
  A: "bg-blue-100 text-blue-700",
  B: "bg-purple-100 text-purple-700",
  tie: "bg-gray-100 text-gray-700",
};

function getPreferenceLabel(preference: string): string {
  return preference === "tie" ? "Tie" : `Variant ${preference}`;
}

export default function ArenaPage() {
  const [token, setToken] = useState("");
  const [arenaId, setArenaId] = useState<string | null>(null);
  const [status, setStatus] = useState<ArenaStatus | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [history, setHistory] = useState<ArenaComparison[]>([]);
  const [input, setInput] = useState({
    linkedin_url: "",
    job_url: "",
    resume_text: "",
    job_text: "",
  });
  const [useText, setUseText] = useState(false);
  const [streamEvents, setStreamEvents] = useState<ArenaStreamEvent[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem(ADMIN_TOKEN_KEY);
    if (stored) setToken(stored);
  }, []);

  const arena = useArena(token);

  // Subscribe to SSE stream and poll for status
  useEffect(() => {
    if (!arenaId || !token) return;

    // Clear previous events when starting new comparison
    setStreamEvents([]);

    // Subscribe to SSE stream for real-time updates (limit to 50 events max)
    const cleanup = arena.subscribeToStream(arenaId, (event) => {
      setStreamEvents((prev) => [...prev.slice(-49), event]);
    });

    // Also poll for full status (SSE only sends deltas)
    const poll = async () => {
      const s = await arena.getStatus(arenaId);
      if (s) setStatus(s);
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      cleanup();
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [arenaId, token]);

  // Load analytics and history
  useEffect(() => {
    if (!token) return;
    arena.getAnalytics().then((a) => a && setAnalytics(a));
    arena.listComparisons(10).then((r) => r && setHistory(r.comparisons));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleStart = async () => {
    const result = await arena.startComparison(input);
    if (result) {
      setArenaId(result.arena_id);
      // Refresh history
      arena.listComparisons(10).then((r) => r && setHistory(r.comparisons));
    }
  };

  const handleSelectComparison = async (id: string) => {
    setArenaId(id);
    // Fetch status immediately instead of waiting for poll
    const s = await arena.getStatus(id);
    if (s) setStatus(s);
  };

  const handleRate = useCallback(
    async (step: string, preference: "A" | "B" | "tie", reason?: string) => {
      if (!arenaId) return;
      const success = await arena.submitRating(arenaId, step, "quality", preference, reason);
      if (success) {
        // Refresh status and analytics
        const s = await arena.getStatus(arenaId);
        if (s) setStatus(s);
        const a = await arena.getAnalytics();
        if (a) setAnalytics(a);
      }
    },
    [arenaId, arena]
  );

  const handleAnswer = async (text: string) => {
    if (!arenaId) return;
    await arena.submitAnswer(arenaId, text);
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportComparison = async (format: "json" | "csv") => {
    if (!arenaId) return;
    const blob = await arena.exportComparison(arenaId, format);
    if (blob) {
      downloadBlob(blob, `arena_${arenaId}.${format}`);
    }
  };

  const handleExportAnalytics = async (format: "json" | "csv") => {
    const blob = await arena.exportAnalytics(format);
    if (blob) {
      downloadBlob(blob, `arena_analytics.${format}`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h2 className="text-2xl font-bold mb-6">Agent Arena: A/B Comparison</h2>

      {/* Analytics Dashboard */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-2">
          <h3 className="font-semibold">Analytics</h3>
          <div className="flex gap-2">
            <button
              onClick={() => handleExportAnalytics("json")}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Export JSON
            </button>
            <button
              onClick={() => handleExportAnalytics("csv")}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Export CSV
            </button>
          </div>
        </div>
        <AnalyticsDashboard analytics={analytics} />
      </div>

      {/* Comparison History */}
      {!arenaId && history.length > 0 && (
        <div className="mb-8">
          <ComparisonHistory comparisons={history} onSelect={handleSelectComparison} />
        </div>
      )}

      {/* Start new comparison */}
      {!arenaId && (
        <div className="border rounded-lg p-6 bg-white mb-8">
          <h3 className="font-semibold mb-4">Start New Comparison</h3>

          <div className="mb-4">
            <label className="flex items-center gap-2 mb-2">
              <input
                type="checkbox"
                checked={useText}
                onChange={(e) => setUseText(e.target.checked)}
              />
              <span className="text-sm">Use pasted text instead of URLs</span>
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            {!useText ? (
              <>
                <FormField
                  label="LinkedIn URL"
                  value={input.linkedin_url}
                  onChange={(v) => setInput({ ...input, linkedin_url: v })}
                  placeholder="https://linkedin.com/in/..."
                />
                <FormField
                  label="Job URL"
                  value={input.job_url}
                  onChange={(v) => setInput({ ...input, job_url: v })}
                  placeholder="https://..."
                />
              </>
            ) : (
              <>
                <FormField
                  label="Resume Text"
                  value={input.resume_text}
                  onChange={(v) => setInput({ ...input, resume_text: v })}
                  placeholder="Paste resume content..."
                  multiline
                />
                <FormField
                  label="Job Description"
                  value={input.job_text}
                  onChange={(v) => setInput({ ...input, job_text: v })}
                  placeholder="Paste job description..."
                  multiline
                />
              </>
            )}
          </div>

          <button
            onClick={handleStart}
            disabled={arena.loading}
            className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {arena.loading ? "Starting..." : "Start Comparison"}
          </button>

          {arena.error && <p className="text-red-500 mt-2">{arena.error}</p>}
        </div>
      )}

      {/* Active comparison */}
      {arenaId && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm text-gray-500">Arena ID: {arenaId}</p>
              <p className="text-sm text-gray-500">
                Status: <span className="font-medium">{status?.status || "Loading..."}</span>
                {status?.sync_point && ` (synced at: ${status.sync_point})`}
              </p>
            </div>
            <div className="flex gap-4 items-center">
              <div className="flex gap-2">
                <button
                  onClick={() => handleExportComparison("json")}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  Export JSON
                </button>
                <button
                  onClick={() => handleExportComparison("csv")}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  Export CSV
                </button>
              </div>
              <button
                onClick={() => {
                  setArenaId(null);
                  setStatus(null);
                }}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Start New
              </button>
            </div>
          </div>

          {/* Live progress stream */}
          {streamEvents.length > 0 && (
            <LiveProgress events={streamEvents} maxEvents={10} />
          )}

          {/* Side by side comparison */}
          <div className="grid grid-cols-2 gap-6">
            <VariantPanel
              variant="A"
              label="LangGraph State Machine"
              status={status?.variant_a || null}
            />
            <VariantPanel
              variant="B"
              label="Deep Agents Coordinator"
              status={status?.variant_b || null}
            />
          </div>

          {/* Metrics panel */}
          {status?.metrics && Object.keys(status.metrics).length > 0 && (
            <MetricsPanel metrics={status.metrics} />
          )}

          {/* Rating panel - show when both at sync point */}
          {status?.sync_point && (
            <PreferenceRating
              step={status.sync_point}
              onRate={(pref, reason) => handleRate(status.sync_point!, pref, reason)}
            />
          )}

          {/* Answer input - show when waiting for input */}
          {status?.status === "waiting_input" && (
            <div className="border rounded-lg p-4 bg-white">
              <h4 className="font-medium mb-3">Submit Answer (to both variants)</h4>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Type your answer..."
                  className="flex-1 px-3 py-2 border rounded"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleAnswer((e.target as HTMLInputElement).value);
                      (e.target as HTMLInputElement).value = "";
                    }
                  }}
                />
                <button
                  onClick={(e) => {
                    const input = (e.target as HTMLElement).previousElementSibling as HTMLInputElement;
                    handleAnswer(input.value);
                    input.value = "";
                  }}
                  className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                >
                  Send
                </button>
              </div>
            </div>
          )}

          {/* Ratings history */}
          {status?.ratings && status.ratings.length > 0 && (
            <div className="border rounded-lg p-4 bg-white">
              <h4 className="font-medium mb-3">Rating History</h4>
              <div className="space-y-2">
                {status.ratings.map((r) => (
                  <div key={r.rating_id} className="flex items-center gap-4 text-sm">
                    <span className="text-gray-600">{r.step}</span>
                    <span className={`px-2 py-0.5 rounded ${PREFERENCE_STYLES[r.preference]}`}>
                      {getPreferenceLabel(r.preference)}
                    </span>
                    {r.reason && <span className="text-gray-500">&ldquo;{r.reason}&rdquo;</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
