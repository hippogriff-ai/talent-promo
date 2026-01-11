"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface StreamEvent {
  type: "step_update" | "complete" | "error";
  step?: string;
  timestamp?: string;
  pending_question?: string;
  qa_round?: number;
  message?: string;
}

export interface UseSSEStreamReturn {
  events: StreamEvent[];
  currentStep: string | null;
  pendingQuestion: string | null;
  qaRound: number;
  isConnected: boolean;
  isComplete: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

export function useSSEStream(threadId: string | null): UseSSEStreamReturn {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [qaRound, setQaRound] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!threadId || eventSourceRef.current) return;

    const url = `${API_URL}/api/optimize/${threadId}/stream`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);

        setEvents((prev) => [...prev, data]);

        switch (data.type) {
          case "step_update":
            setCurrentStep(data.step || null);
            if (data.pending_question !== undefined) {
              setPendingQuestion(data.pending_question);
            }
            if (data.qa_round !== undefined) {
              setQaRound(data.qa_round);
            }
            break;

          case "complete":
            setIsComplete(true);
            setCurrentStep(data.step || "completed");
            eventSource.close();
            break;

          case "error":
            setError(data.message || "Unknown error");
            eventSource.close();
            break;
        }
      } catch (e) {
        console.error("Failed to parse SSE event:", e);
      }
    };

    eventSource.onerror = (e) => {
      console.error("SSE error:", e);
      setIsConnected(false);

      eventSource.close();
      eventSourceRef.current = null;

      // Attempt reconnect after delay if not complete
      if (!isComplete) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      }
    };
  }, [threadId, isComplete]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setIsConnected(false);
  }, []);

  // Auto-connect when threadId is provided
  useEffect(() => {
    if (threadId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [threadId, connect, disconnect]);

  // Reset state when threadId changes
  useEffect(() => {
    setEvents([]);
    setCurrentStep(null);
    setPendingQuestion(null);
    setQaRound(0);
    setIsComplete(false);
    setError(null);
  }, [threadId]);

  return {
    events,
    currentStep,
    pendingQuestion,
    qaRound,
    isConnected,
    isComplete,
    error,
    connect,
    disconnect,
  };
}
