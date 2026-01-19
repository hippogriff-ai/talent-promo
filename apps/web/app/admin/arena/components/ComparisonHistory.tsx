"use client";

import { ArenaComparison } from "@/app/hooks/useArena";

interface ComparisonHistoryProps {
  comparisons: ArenaComparison[];
  onSelect: (arenaId: string) => void;
}

export function ComparisonHistory({ comparisons, onSelect }: ComparisonHistoryProps) {
  if (comparisons.length === 0) {
    return (
      <div className="border rounded-lg p-4 bg-white">
        <h3 className="font-semibold mb-2">Recent Comparisons</h3>
        <p className="text-gray-500 text-sm">No comparisons yet</p>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed": return "bg-green-100 text-green-700";
      case "error": return "bg-red-100 text-red-700";
      case "running": return "bg-blue-100 text-blue-700";
      default: return "bg-gray-100 text-gray-700";
    }
  };

  const formatDate = (iso: string) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h3 className="font-semibold mb-3">Recent Comparisons</h3>
      <div className="space-y-2">
        {comparisons.map((c) => (
          <button
            key={c.arena_id}
            onClick={() => onSelect(c.arena_id)}
            className="w-full text-left p-3 rounded border hover:bg-gray-50 flex items-center justify-between"
          >
            <div>
              <p className="text-sm font-medium">{c.arena_id.slice(0, 8)}...</p>
              <p className="text-xs text-gray-500">{formatDate(c.created_at)}</p>
            </div>
            <div className="flex items-center gap-2">
              {c.winner && (
                <span className={`text-xs px-2 py-0.5 rounded ${
                  c.winner === "A" ? "bg-blue-100 text-blue-700" :
                  c.winner === "B" ? "bg-purple-100 text-purple-700" :
                  "bg-gray-100 text-gray-700"
                }`}>
                  Winner: {c.winner}
                </span>
              )}
              <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(c.status)}`}>
                {c.status}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
