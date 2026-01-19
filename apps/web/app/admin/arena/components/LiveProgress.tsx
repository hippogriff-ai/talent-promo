"use client";

import { useEffect, useState } from "react";
import { ArenaStreamEvent } from "@/app/hooks/useArena";

interface LiveProgressProps {
  events: ArenaStreamEvent[];
  maxEvents?: number;
}

const VARIANT_COLORS = {
  A: "text-blue-600 bg-blue-50",
  B: "text-purple-600 bg-purple-50",
};

export function LiveProgress({ events, maxEvents = 10 }: LiveProgressProps) {
  const displayEvents = events.slice(-maxEvents);

  if (displayEvents.length === 0) {
    return (
      <div className="border rounded-lg p-4 bg-gray-50">
        <p className="text-sm text-gray-500 text-center">Waiting for events...</p>
      </div>
    );
  }

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h4 className="font-medium mb-3 text-sm text-gray-600">Live Progress</h4>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {displayEvents.map((event, idx) => (
          <div
            key={idx}
            className={`text-sm p-2 rounded flex items-start gap-2 ${
              event.variant ? VARIANT_COLORS[event.variant] : "bg-gray-100"
            }`}
          >
            {event.variant && (
              <span className="font-mono font-bold shrink-0">[{event.variant}]</span>
            )}
            <div className="flex-1">
              {event.type === "step_update" && (
                <span>Step: <strong>{event.step}</strong></span>
              )}
              {event.type === "progress" && (
                <span>{event.message || event.phase}</span>
              )}
              {event.type === "sync" && (
                <span className="text-green-700">Both variants synced at: <strong>{event.step}</strong></span>
              )}
              {event.type === "complete" && (
                <span className="text-gray-700">
                  Comparison complete (A: {event.variant_a}, B: {event.variant_b})
                </span>
              )}
              {event.type === "error" && (
                <span className="text-red-600">{event.message}</span>
              )}
            </div>
            {event.timestamp && (
              <span className="text-xs text-gray-400 shrink-0">
                {new Date(event.timestamp).toLocaleTimeString()}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
