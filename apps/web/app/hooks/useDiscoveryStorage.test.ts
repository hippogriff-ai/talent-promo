import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDiscoveryStorage } from "./useDiscoveryStorage";

describe("useDiscoveryStorage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(null);
  });

  describe("Session Management", () => {
    it("should start a new session", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      expect(result.current.session).not.toBeNull();
      expect(result.current.session?.threadId).toBe("thread-123");
      expect(result.current.session?.messages).toEqual([]);
      expect(result.current.session?.confirmed).toBe(false);
    });

    it("should check for existing session", () => {
      const existingSession = {
        threadId: "thread-123",
        messages: [{ role: "agent", content: "Hello", timestamp: "2024-01-01" }],
        discoveredExperiences: [],
        prompts: [],
        confirmed: false,
        exchanges: 1,
        startedAt: "2024-01-01",
        updatedAt: "2024-01-01",
        lastError: null,
        currentPromptIndex: 0,
      };

      (localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(
        JSON.stringify({ "thread-123": existingSession })
      );

      const { result } = renderHook(() => useDiscoveryStorage());

      let found;
      act(() => {
        found = result.current.checkExistingSession("thread-123");
      });

      expect(found).not.toBeNull();
      expect(result.current.existingSession?.threadId).toBe("thread-123");
    });

    it("should resume session", () => {
      const existingSession = {
        threadId: "thread-123",
        messages: [{ role: "agent" as const, content: "Hello", timestamp: "2024-01-01" }],
        discoveredExperiences: [],
        prompts: [],
        confirmed: false,
        exchanges: 1,
        startedAt: "2024-01-01",
        updatedAt: "2024-01-01",
        lastError: null,
        currentPromptIndex: 0,
      };

      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.resumeSession(existingSession);
      });

      expect(result.current.session?.threadId).toBe("thread-123");
      expect(result.current.existingSession).toBeNull();
    });

    it("should clear session and start fresh", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      act(() => {
        result.current.clearSession("thread-123");
      });

      expect(result.current.session).toBeNull();
    });
  });

  describe("Conversation Persistence", () => {
    it("should save message to session immediately", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      act(() => {
        result.current.addMessage({
          role: "user",
          content: "Test response",
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.session?.messages.length).toBe(1);
      expect(result.current.session?.messages[0].content).toBe("Test response");
      expect(localStorage.setItem).toHaveBeenCalled();
    });

    it("should increment exchanges when user responds", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      expect(result.current.session?.exchanges).toBe(0);

      act(() => {
        result.current.addMessage({
          role: "user",
          content: "User response",
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.session?.exchanges).toBe(1);
    });

    it("should not increment exchanges for agent messages", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      act(() => {
        result.current.addMessage({
          role: "agent",
          content: "Agent question",
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.session?.exchanges).toBe(0);
    });
  });

  describe("Discovered Experiences", () => {
    it("should add discovered experience", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      act(() => {
        result.current.addExperience({
          id: "exp-1",
          description: "Led Docker migration",
          sourceQuote: "I led our Docker migration",
          mappedRequirements: ["Container experience"],
          discoveredAt: new Date().toISOString(),
        });
      });

      expect(result.current.session?.discoveredExperiences.length).toBe(1);
      expect(result.current.session?.discoveredExperiences[0].description).toBe(
        "Led Docker migration"
      );
    });
  });

  describe("Completion", () => {
    it("should not allow confirmation with less than 3 exchanges", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      // Add 2 exchanges
      act(() => {
        result.current.addMessage({
          role: "user",
          content: "Response 1",
          timestamp: new Date().toISOString(),
        });
      });
      act(() => {
        result.current.addMessage({
          role: "user",
          content: "Response 2",
          timestamp: new Date().toISOString(),
        });
      });

      expect(result.current.canConfirm()).toBe(false);
    });

    it("should allow confirmation with 3+ exchanges", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      // Add 3 exchanges
      for (let i = 0; i < 3; i++) {
        act(() => {
          result.current.addMessage({
            role: "user",
            content: `Response ${i}`,
            timestamp: new Date().toISOString(),
          });
        });
      }

      expect(result.current.canConfirm()).toBe(true);
    });

    it("should mark discovery as confirmed", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      act(() => {
        result.current.confirmDiscovery();
      });

      expect(result.current.session?.confirmed).toBe(true);
    });
  });

  describe("Backend Sync", () => {
    it("should sync from backend data", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      act(() => {
        result.current.syncFromBackend({
          discovery_messages: [
            { role: "agent", content: "Q1", timestamp: "2024-01-01" },
            { role: "user", content: "A1", timestamp: "2024-01-01" },
          ],
          discovered_experiences: [
            {
              id: "exp-1",
              description: "Experience 1",
              source_quote: "Quote",
              mapped_requirements: ["Req 1"],
              discovered_at: "2024-01-01",
            },
          ],
          discovery_prompts: [
            {
              id: "p1",
              question: "Q?",
              intent: "Intent",
              related_gaps: ["Gap"],
              priority: 1,
              asked: true,
            },
          ],
          discovery_confirmed: false,
          discovery_exchanges: 1,
        });
      });

      expect(result.current.session?.messages.length).toBe(2);
      expect(result.current.session?.discoveredExperiences.length).toBe(1);
      expect(result.current.session?.prompts.length).toBe(1);
    });
  });

  describe("Error Handling", () => {
    it("should record errors", () => {
      const { result } = renderHook(() => useDiscoveryStorage());

      act(() => {
        result.current.startSession("thread-123", []);
      });

      act(() => {
        result.current.recordError("Something went wrong");
      });

      expect(result.current.session?.lastError).toBe("Something went wrong");
    });
  });
});
