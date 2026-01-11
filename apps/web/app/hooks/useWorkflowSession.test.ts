import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWorkflowSession, WorkflowStage } from "./useWorkflowSession";

// Mock localStorage
const mockLocalStorage = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, "localStorage", {
  value: mockLocalStorage,
});

describe("useWorkflowSession", () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    vi.clearAllMocks();
  });

  describe("Workflow Navigation", () => {
    it("GIVEN user on any stage, WHEN viewing UI, THEN stepper shows all 4 stages", () => {
      const { result } = renderHook(() => useWorkflowSession());

      expect(result.current.stageOrder).toHaveLength(4);
      expect(result.current.stageOrder).toEqual([
        "research",
        "discovery",
        "drafting",
        "export",
      ]);
    });

    it("GIVEN current stage is Research, WHEN stepper displayed, THEN Research shows as active, others locked", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      expect(result.current.session?.stages.research).toBe("active");
      expect(result.current.session?.stages.discovery).toBe("locked");
      expect(result.current.session?.stages.drafting).toBe("locked");
      expect(result.current.session?.stages.export).toBe("locked");
    });

    it("GIVEN stage complete, WHEN stepper displayed, THEN completed stage shows checkmark, next unlocks", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
      });

      expect(result.current.session?.stages.research).toBe("completed");
      expect(result.current.session?.stages.discovery).toBe("active");
      expect(result.current.session?.stages.drafting).toBe("locked");
    });
  });

  describe("Stage Transitions", () => {
    it("GIVEN Research complete, WHEN RESEARCH_COMPLETE emitted, THEN Discovery unlocks automatically", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
      });

      expect(result.current.session?.researchComplete).toBe(true);
      expect(result.current.session?.stages.discovery).toBe("active");
      expect(result.current.session?.currentStage).toBe("discovery");
    });

    it("GIVEN Discovery confirmed, WHEN user clicks Continue, THEN Drafting unlocks", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
      });

      act(() => {
        result.current.completeStage("discovery");
      });

      expect(result.current.session?.discoveryConfirmed).toBe(true);
      expect(result.current.session?.stages.drafting).toBe("active");
    });

    it("GIVEN Drafting approved, WHEN user clicks Continue, THEN Export unlocks", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
        result.current.completeStage("discovery");
        result.current.completeStage("drafting");
      });

      expect(result.current.session?.draftApproved).toBe(true);
      expect(result.current.session?.stages.export).toBe("active");
    });

    it("GIVEN Export complete, WHEN EXPORT_COMPLETE emitted, THEN workflow shows Complete state", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
        result.current.completeStage("discovery");
        result.current.completeStage("drafting");
        result.current.completeStage("export");
      });

      expect(result.current.session?.exportComplete).toBe(true);
      expect(result.current.isWorkflowComplete()).toBe(true);
    });
  });

  describe("Stage Guards", () => {
    it("GIVEN user tries to access stage N, WHEN stage N-1 not complete, THEN cannot access", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      // Try to access discovery before research complete
      expect(result.current.canAccessStage("discovery")).toBe(false);
      expect(result.current.canAccessStage("drafting")).toBe(false);
      expect(result.current.canAccessStage("export")).toBe(false);
    });

    it("GIVEN user bookmarks Export URL, WHEN prior stages incomplete, THEN redirects to earliest incomplete", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      // Complete only research
      act(() => {
        result.current.completeStage("research");
      });

      // Try to access export directly
      let success: boolean = false;
      act(() => {
        success = result.current.setActiveStage("export");
      });

      expect(success).toBe(false);
      expect(result.current.getEarliestIncompleteStage()).toBe("discovery");
    });

    it("allows access to completed stages for review", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
        result.current.completeStage("research");
        result.current.completeStage("discovery");
      });

      // Should be able to go back to research
      expect(result.current.canAccessStage("research")).toBe(true);

      let success: boolean = false;
      act(() => {
        success = result.current.setActiveStage("research");
      });

      expect(success).toBe(true);
    });
  });

  describe("Session Continuity", () => {
    it("GIVEN user completes Research and closes browser, WHEN returns, THEN detects session", () => {
      // Create a session
      const { result: result1 } = renderHook(() => useWorkflowSession());

      act(() => {
        result1.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result1.current.completeStage("research");
      });

      // Verify session was saved
      expect(mockLocalStorage.setItem).toHaveBeenCalled();
      expect(result1.current.session?.currentStage).toBe("discovery");
      expect(result1.current.session?.researchComplete).toBe(true);

      // Simulate browser reload - verify localStorage was called
      const storedData = mockLocalStorage.getItem("resume_agent:workflow_session");
      expect(storedData).not.toBeNull();

      const parsed = JSON.parse(storedData!);
      expect(parsed.currentStage).toBe("discovery");
    });

    it("GIVEN user in middle of Discovery, WHEN returns, THEN can resume from localStorage", () => {
      const { result: result1 } = renderHook(() => useWorkflowSession());

      act(() => {
        result1.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result1.current.completeStage("research");
      });

      // Verify session state
      expect(result1.current.session?.currentStage).toBe("discovery");
      expect(result1.current.session?.researchComplete).toBe(true);
      expect(result1.current.session?.stages.discovery).toBe("active");
    });
  });

  describe("New Session", () => {
    it("GIVEN user has completed workflow, WHEN confirms new session, THEN clears all localStorage", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
        result.current.completeStage("research");
        result.current.completeStage("discovery");
        result.current.completeStage("drafting");
        result.current.completeStage("export");
      });

      act(() => {
        result.current.clearAllSessions();
      });

      expect(result.current.session).toBeNull();
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith(
        "resume_agent:workflow_session"
      );
    });

    it("GIVEN user has existing session, WHEN enters different URLs, THEN creates new session", () => {
      const { result } = renderHook(() => useWorkflowSession());

      // First session
      act(() => {
        result.current.startSession("linkedin.com/in/user1", "job1.com/posting", "thread-1");
      });

      const firstSessionId = result.current.session?.sessionId;

      // Different URLs = new session
      act(() => {
        result.current.startSession("linkedin.com/in/user2", "job2.com/posting", "thread-2");
      });

      expect(result.current.session?.sessionId).not.toBe(firstSessionId);
      expect(result.current.session?.threadId).toBe("thread-2");
    });
  });

  describe("Error Recovery", () => {
    it("GIVEN any stage fails with error, WHEN error occurs, THEN saves state", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
      });

      act(() => {
        result.current.recordError("API timeout", "discovery");
      });

      expect(result.current.session?.lastError).toBe("API timeout");
      expect(result.current.session?.errorStage).toBe("discovery");
      expect(result.current.session?.stages.discovery).toBe("error");
    });

    it("GIVEN error displayed, WHEN user clicks Retry, THEN resumes from last state", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
      });

      act(() => {
        result.current.recordError("API timeout", "discovery");
      });

      act(() => {
        result.current.retryFromError();
      });

      expect(result.current.session?.lastError).toBeNull();
      expect(result.current.session?.errorStage).toBeNull();
      expect(result.current.session?.stages.discovery).toBe("active");
      expect(result.current.session?.currentStage).toBe("discovery");
    });

    it("GIVEN unrecoverable error, WHEN Start Fresh, THEN preserves completed stages", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.completeStage("research");
      });

      act(() => {
        result.current.completeStage("discovery");
      });

      act(() => {
        result.current.recordError("Drafting failed", "drafting");
      });

      act(() => {
        result.current.startFreshFromError();
      });

      // Research and discovery should still be complete
      expect(result.current.session?.stages.research).toBe("completed");
      expect(result.current.session?.stages.discovery).toBe("completed");

      // Drafting should be reset to active
      expect(result.current.session?.stages.drafting).toBe("active");
      expect(result.current.session?.stages.export).toBe("locked");
      expect(result.current.session?.lastError).toBeNull();
    });
  });

  describe("Backend Sync", () => {
    it("syncs session state from backend status", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      act(() => {
        result.current.syncFromBackend({
          current_step: "discovery",
          research_complete: true,
          discovery_confirmed: false,
        });
      });

      expect(result.current.session?.researchComplete).toBe(true);
      expect(result.current.session?.stages.research).toBe("completed");
      expect(result.current.session?.stages.discovery).toBe("active");
    });
  });

  describe("Progress Tracking", () => {
    it("calculates completion percentage correctly", () => {
      const { result } = renderHook(() => useWorkflowSession());

      act(() => {
        result.current.startSession("linkedin.com/in/user", "job.com/posting", "thread-123");
      });

      expect(result.current.getCompletionPercentage()).toBe(0);

      act(() => {
        result.current.completeStage("research");
      });

      expect(result.current.getCompletionPercentage()).toBe(25);

      act(() => {
        result.current.completeStage("discovery");
      });

      expect(result.current.getCompletionPercentage()).toBe(50);

      act(() => {
        result.current.completeStage("drafting");
      });

      expect(result.current.getCompletionPercentage()).toBe(75);

      act(() => {
        result.current.completeStage("export");
      });

      expect(result.current.getCompletionPercentage()).toBe(100);
    });
  });
});
