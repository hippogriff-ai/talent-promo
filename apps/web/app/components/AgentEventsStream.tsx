"use client";

import { useEffect, useState, useRef } from "react";

// Get API URL from environment variable with fallback
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AgentEvent {
  agent_id: string;
  type: string;
  phase?: string;
  message?: string;
  tool?: string;
  query?: string;
  url?: string;
  title?: string;
  timestamp: number;
}

interface AgentEventsStreamProps {
  agentId: string;
  onComplete?: () => void;
}

export default function AgentEventsStream({
  agentId,
  onComplete,
}: AgentEventsStreamProps) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventIdRef = useRef<string>("");
  const isCompletedRef = useRef<boolean>(false);

  useEffect(() => {
    const connectSSE = () => {
      const eventSource = new EventSource(
        `${API_URL}/api/agents/stream/${agentId}`
      );
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setIsConnected(true);
        setError(null);
      };

      eventSource.onmessage = (event) => {
        try {
          const data: AgentEvent = JSON.parse(event.data);

          setEvents((prev) => [...prev, data]);

          if (data.type === "phase") {
            setCurrentPhase(data.phase || null);
          } else if (data.type === "complete") {
            setCurrentPhase("completed");
            isCompletedRef.current = true;
            eventSource.close();
            onComplete?.();
          }

          lastEventIdRef.current = event.lastEventId || "";
        } catch (err) {
          console.error("Failed to parse event:", err);
        }
      };

      eventSource.onerror = (err) => {
        console.error("SSE error:", err);
        setIsConnected(false);
        setError("Connection lost. Retrying...");

        // Reconnect after 3s with backoff
        setTimeout(() => {
          if (!isCompletedRef.current) {
            connectSSE();
          }
        }, 3000);
      };
    };

    connectSSE();

    // Cleanup on unmount
    return () => {
      eventSourceRef.current?.close();
    };
  }, [agentId, onComplete]);

  const getPhaseColor = (phase: string | null) => {
    switch (phase) {
      case "planning":
        return "bg-blue-500";
      case "tools":
        return "bg-purple-500";
      case "writing":
        return "bg-green-500";
      case "completed":
        return "bg-gray-500";
      default:
        return "bg-gray-300";
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Agent Activity</h2>
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="text-sm text-gray-600">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>

        {/* Current Phase Indicator */}
        {currentPhase && (
          <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
            <div className={`w-4 h-4 rounded-full ${getPhaseColor(currentPhase)} animate-pulse`} />
            <span className="font-medium capitalize">{currentPhase}</span>
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
            {error}
          </div>
        )}
      </div>

      {/* Events Timeline */}
      <div className="space-y-4">
        {events.map((event, idx) => (
          <div
            key={idx}
            className="flex gap-4 p-4 bg-white border rounded-lg shadow-sm"
          >
            <div className="flex-shrink-0">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-white ${
                  event.type === "phase"
                    ? "bg-blue-500"
                    : event.type === "tool_use"
                    ? "bg-purple-500"
                    : event.type === "citation"
                    ? "bg-green-500"
                    : "bg-gray-500"
                }`}
              >
                {event.type === "phase" && "📋"}
                {event.type === "tool_use" && "🔧"}
                {event.type === "citation" && "📎"}
                {event.type === "complete" && "✅"}
              </div>
            </div>

            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-500 uppercase">
                  {event.type.replace("_", " ")}
                </span>
                <span className="text-xs text-gray-400">
                  {new Date(event.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>

              {event.message && (
                <p className="text-gray-800">{event.message}</p>
              )}

              {event.tool && (
                <p className="text-gray-700">
                  Tool: <span className="font-mono">{event.tool}</span>
                  {event.query && ` - "${event.query}"`}
                </p>
              )}

              {event.url && (
                <a
                  href={event.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  {event.title || event.url}
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
