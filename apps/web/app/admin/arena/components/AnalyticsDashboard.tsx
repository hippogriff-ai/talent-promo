"use client";

import { Analytics } from "@/app/hooks/useArena";

interface AnalyticsDashboardProps {
  analytics: Analytics | null;
}

interface PreferenceCounts {
  A: number;
  B: number;
  tie: number;
}

function BreakdownBar({ label, counts }: { label: string; counts: PreferenceCounts }): JSX.Element {
  const total = counts.A + counts.B + counts.tie;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-24 text-gray-600">{label}</span>
      <div className="flex-1 flex h-4 rounded overflow-hidden bg-gray-100">
        <div className="bg-blue-500" style={{ width: `${(counts.A / total) * 100}%` }} />
        <div className="bg-gray-400" style={{ width: `${(counts.tie / total) * 100}%` }} />
        <div className="bg-purple-500" style={{ width: `${(counts.B / total) * 100}%` }} />
      </div>
      <span className="w-16 text-right text-gray-500">{total} votes</span>
    </div>
  );
}

function BreakdownSection({
  title,
  data,
}: {
  title: string;
  data: Record<string, PreferenceCounts>;
}): JSX.Element | null {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;

  return (
    <div className="mb-4 last:mb-0">
      <p className="text-sm font-medium mb-2">{title}</p>
      <div className="space-y-2">
        {entries.map(([label, counts]) => (
          <BreakdownBar key={label} label={label} counts={counts} />
        ))}
      </div>
    </div>
  );
}

export function AnalyticsDashboard({ analytics }: AnalyticsDashboardProps): JSX.Element {
  if (!analytics) {
    return (
      <div className="border rounded-lg p-6 bg-white">
        <h3 className="font-semibold mb-4">Cumulative Analytics</h3>
        <p className="text-gray-500">Loading analytics...</p>
      </div>
    );
  }

  const winRateA = (analytics.win_rate_a * 100).toFixed(1);
  const winRateB = (analytics.win_rate_b * 100).toFixed(1);
  const tieRate =
    analytics.total_ratings > 0
      ? ((analytics.ties / analytics.total_ratings) * 100).toFixed(1)
      : "0.0";

  return (
    <div className="border rounded-lg p-6 bg-white">
      <h3 className="font-semibold mb-4">Cumulative Analytics</h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="text-center p-3 bg-gray-50 rounded">
          <p className="text-2xl font-bold">{analytics.total_comparisons}</p>
          <p className="text-sm text-gray-500">Comparisons</p>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded">
          <p className="text-2xl font-bold">{analytics.total_ratings}</p>
          <p className="text-sm text-gray-500">Total Ratings</p>
        </div>
        <div className="text-center p-3 bg-blue-50 rounded">
          <p className="text-2xl font-bold text-blue-600">{winRateA}%</p>
          <p className="text-sm text-gray-500">Variant A Wins</p>
        </div>
        <div className="text-center p-3 bg-purple-50 rounded">
          <p className="text-2xl font-bold text-purple-600">{winRateB}%</p>
          <p className="text-sm text-gray-500">Variant B Wins</p>
        </div>
      </div>

      {/* Overall preference bar */}
      <div className="mb-6">
        <p className="text-sm font-medium mb-2">Overall Preference</p>
        <div className="flex h-8 rounded overflow-hidden">
          <div
            className="bg-blue-500 flex items-center justify-center text-white text-xs"
            style={{ width: `${winRateA}%` }}
          >
            {analytics.variant_a_wins > 0 && `A: ${analytics.variant_a_wins}`}
          </div>
          <div
            className="bg-gray-400 flex items-center justify-center text-white text-xs"
            style={{ width: `${tieRate}%` }}
          >
            {analytics.ties > 0 && `Tie: ${analytics.ties}`}
          </div>
          <div
            className="bg-purple-500 flex items-center justify-center text-white text-xs"
            style={{ width: `${winRateB}%` }}
          >
            {analytics.variant_b_wins > 0 && `B: ${analytics.variant_b_wins}`}
          </div>
        </div>
      </div>

      <BreakdownSection title="By Step" data={analytics.by_step} />
      <BreakdownSection title="By Aspect" data={analytics.by_aspect} />
    </div>
  );
}
