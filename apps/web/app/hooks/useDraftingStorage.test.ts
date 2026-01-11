import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDraftingStorage, DraftingSuggestion } from "./useDraftingStorage";

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

describe("useDraftingStorage", () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it("initializes with null session", () => {
    const { result } = renderHook(() => useDraftingStorage());

    expect(result.current.session).toBeNull();
    expect(result.current.existingSession).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("starts a new session", () => {
    const { result } = renderHook(() => useDraftingStorage());

    act(() => {
      result.current.startSession("thread-123", "<h1>Test</h1>", []);
    });

    expect(result.current.session).not.toBeNull();
    expect(result.current.session?.threadId).toBe("thread-123");
    expect(result.current.session?.resumeHtml).toBe("<h1>Test</h1>");
    expect(result.current.session?.currentVersion).toBe("1.0");
    expect(result.current.session?.versions).toHaveLength(1);
  });

  it("starts session with suggestions", () => {
    const { result } = renderHook(() => useDraftingStorage());

    const suggestions: DraftingSuggestion[] = [
      {
        id: "sug_1",
        location: "summary",
        originalText: "old",
        proposedText: "new",
        rationale: "better",
        status: "pending",
        createdAt: new Date().toISOString(),
      },
    ];

    act(() => {
      result.current.startSession("thread-123", "<h1>Test</h1>", suggestions);
    });

    expect(result.current.session?.suggestions).toHaveLength(1);
    expect(result.current.session?.suggestions[0].id).toBe("sug_1");
  });

  it("accepts a suggestion", () => {
    const { result } = renderHook(() => useDraftingStorage());

    const suggestions: DraftingSuggestion[] = [
      {
        id: "sug_1",
        location: "summary",
        originalText: "old text",
        proposedText: "new text",
        rationale: "better",
        status: "pending",
        createdAt: new Date().toISOString(),
      },
    ];

    act(() => {
      result.current.startSession("thread-123", "<p>old text</p>", suggestions);
    });

    act(() => {
      result.current.acceptSuggestion("sug_1");
    });

    // Check suggestion status updated
    const accepted = result.current.session?.suggestions.find(
      (s) => s.id === "sug_1"
    );
    expect(accepted?.status).toBe("accepted");

    // Check HTML was updated
    expect(result.current.session?.resumeHtml).toBe("<p>new text</p>");

    // Check change log
    expect(result.current.session?.changeLog).toHaveLength(1);
    expect(result.current.session?.changeLog[0].changeType).toBe("accept");
  });

  it("declines a suggestion", () => {
    const { result } = renderHook(() => useDraftingStorage());

    const suggestions: DraftingSuggestion[] = [
      {
        id: "sug_1",
        location: "summary",
        originalText: "old text",
        proposedText: "new text",
        rationale: "better",
        status: "pending",
        createdAt: new Date().toISOString(),
      },
    ];

    act(() => {
      result.current.startSession("thread-123", "<p>old text</p>", suggestions);
    });

    act(() => {
      result.current.declineSuggestion("sug_1");
    });

    // Check suggestion status updated
    const declined = result.current.session?.suggestions.find(
      (s) => s.id === "sug_1"
    );
    expect(declined?.status).toBe("declined");

    // Check HTML was NOT updated
    expect(result.current.session?.resumeHtml).toBe("<p>old text</p>");

    // Check change log
    expect(result.current.session?.changeLog).toHaveLength(1);
    expect(result.current.session?.changeLog[0].changeType).toBe("decline");
  });

  it("records a direct edit", async () => {
    const { result } = renderHook(() => useDraftingStorage());

    act(() => {
      result.current.startSession("thread-123", "<p>content</p>", []);
    });

    act(() => {
      result.current.recordEdit("summary", "old", "new");
    });

    // Wait for async state updates to settle
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    // changeLog should be preserved even after version creation
    expect(result.current.session?.changeLog).toHaveLength(1);
    expect(result.current.session?.changeLog[0].changeType).toBe("edit");
    expect(result.current.session?.changeLog[0].location).toBe("summary");
  });

  it("creates a manual save version", () => {
    const { result } = renderHook(() => useDraftingStorage());

    act(() => {
      result.current.startSession("thread-123", "<h1>Test</h1>", []);
    });

    act(() => {
      result.current.manualSave();
    });

    expect(result.current.session?.versions).toHaveLength(2);
    expect(result.current.session?.currentVersion).toBe("1.1");
    expect(result.current.session?.versions[1].trigger).toBe("manual_save");
  });

  it("restores a previous version", () => {
    const { result } = renderHook(() => useDraftingStorage());

    act(() => {
      result.current.startSession("thread-123", "<h1>Original</h1>", []);
    });

    // Update content
    act(() => {
      result.current.updateResumeHtml("<h1>Modified</h1>");
      result.current.manualSave();
    });

    // Restore to 1.0
    act(() => {
      result.current.restoreVersion("1.0");
    });

    expect(result.current.session?.resumeHtml).toBe("<h1>Original</h1>");
    expect(result.current.session?.versions.slice(-1)[0].trigger).toBe("restore");
  });

  it("approves the draft", () => {
    const { result } = renderHook(() => useDraftingStorage());

    act(() => {
      result.current.startSession("thread-123", "<h1>Test</h1>", []);
    });

    act(() => {
      result.current.approveDraft();
    });

    expect(result.current.session?.approved).toBe(true);
  });

  it("checks for existing session", () => {
    // Seed localStorage with existing session
    const existingSession = {
      "thread-123": {
        threadId: "thread-123",
        resumeHtml: "<h1>Existing</h1>",
        suggestions: [],
        versions: [],
        currentVersion: "1.0",
        changeLog: [],
        approved: false,
        startedAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    };
    mockLocalStorage.setItem(
      "resume_agent:drafting_session",
      JSON.stringify(existingSession)
    );

    const { result } = renderHook(() => useDraftingStorage());

    let existing;
    act(() => {
      existing = result.current.checkExistingSession("thread-123");
    });

    expect(existing).not.toBeNull();
    expect(result.current.existingSession).not.toBeNull();
  });

  it("clears existing session", () => {
    const existingSession = {
      "thread-123": {
        threadId: "thread-123",
        resumeHtml: "<h1>Existing</h1>",
        suggestions: [],
        versions: [],
        currentVersion: "1.0",
        changeLog: [],
        approved: false,
        startedAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    };
    mockLocalStorage.setItem(
      "resume_agent:drafting_session",
      JSON.stringify(existingSession)
    );

    const { result } = renderHook(() => useDraftingStorage());

    act(() => {
      result.current.clearSession("thread-123");
    });

    expect(result.current.session).toBeNull();
    expect(result.current.existingSession).toBeNull();
  });

  it("keeps only last 5 versions", () => {
    const { result } = renderHook(() => useDraftingStorage());

    act(() => {
      result.current.startSession("thread-123", "<h1>Test</h1>", []);
    });

    // Create 6 more versions (total 7)
    for (let i = 0; i < 6; i++) {
      act(() => {
        result.current.manualSave();
      });
    }

    expect(result.current.session?.versions.length).toBeLessThanOrEqual(5);
  });

  it("returns correct pending suggestions count", () => {
    const { result } = renderHook(() => useDraftingStorage());

    const suggestions: DraftingSuggestion[] = [
      {
        id: "sug_1",
        location: "summary",
        originalText: "old",
        proposedText: "new",
        rationale: "better",
        status: "pending",
        createdAt: new Date().toISOString(),
      },
      {
        id: "sug_2",
        location: "experience",
        originalText: "old2",
        proposedText: "new2",
        rationale: "better2",
        status: "accepted",
        createdAt: new Date().toISOString(),
      },
    ];

    act(() => {
      result.current.startSession("thread-123", "<h1>Test</h1>", suggestions);
    });

    expect(result.current.pendingSuggestionsCount()).toBe(1);
  });

  it("returns true when all suggestions resolved", () => {
    const { result } = renderHook(() => useDraftingStorage());

    const suggestions: DraftingSuggestion[] = [
      {
        id: "sug_1",
        location: "summary",
        originalText: "old",
        proposedText: "new",
        rationale: "better",
        status: "accepted",
        createdAt: new Date().toISOString(),
      },
    ];

    act(() => {
      result.current.startSession("thread-123", "<h1>Test</h1>", suggestions);
    });

    expect(result.current.allSuggestionsResolved()).toBe(true);
  });
});
