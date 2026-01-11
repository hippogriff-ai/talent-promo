import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useExportStorage,
  ATSReport,
  LinkedInSuggestion,
} from "./useExportStorage";

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

describe("useExportStorage", () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it("initializes with null session", () => {
    const { result } = renderHook(() => useExportStorage());

    expect(result.current.session).toBeNull();
    expect(result.current.existingSession).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("starts a new session", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    expect(result.current.session).not.toBeNull();
    expect(result.current.session?.threadId).toBe("thread-123");
    expect(result.current.session?.currentStep).toBe("idle");
    expect(result.current.session?.exportCompleted).toBe(false);
  });

  it("updates export step", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    act(() => {
      result.current.updateStep("optimizing");
    });

    expect(result.current.session?.currentStep).toBe("optimizing");
  });

  it("saves ATS report", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    const mockReport: ATSReport = {
      keyword_match_score: 85,
      matched_keywords: ["Python", "AWS"],
      missing_keywords: ["GraphQL"],
      formatting_issues: [],
      recommendations: ["Add more keywords"],
      analyzed_at: new Date().toISOString(),
    };

    act(() => {
      result.current.saveATSReport(mockReport);
    });

    expect(result.current.session?.atsReport).not.toBeNull();
    expect(result.current.session?.atsReport?.keyword_match_score).toBe(85);
  });

  it("saves LinkedIn suggestions", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    const mockSuggestions: LinkedInSuggestion = {
      headline: "Software Engineer | Python | AWS",
      summary: "Experienced engineer...",
      experience_bullets: [
        {
          company: "Tech Corp",
          position: "Senior Engineer",
          bullets: ["Led team", "Built systems"],
        },
      ],
      generated_at: new Date().toISOString(),
    };

    act(() => {
      result.current.saveLinkedInSuggestions(mockSuggestions);
    });

    expect(result.current.session?.linkedinSuggestions).not.toBeNull();
    expect(result.current.session?.linkedinSuggestions?.headline).toBe(
      "Software Engineer | Python | AWS"
    );
  });

  it("completes export", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    act(() => {
      result.current.completeExport();
    });

    expect(result.current.session?.exportCompleted).toBe(true);
    expect(result.current.session?.currentStep).toBe("completed");
    expect(result.current.session?.completedAt).not.toBeNull();
  });

  it("checks for existing session", () => {
    // Seed localStorage with existing session
    const existingSession = {
      "thread-123": {
        threadId: "thread-123",
        currentStep: "completed",
        atsReport: { keyword_match_score: 90 },
        linkedinSuggestions: null,
        exportCompleted: true,
        startedAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
      },
    };
    mockLocalStorage.setItem(
      "resume_agent:export_session",
      JSON.stringify(existingSession)
    );

    const { result } = renderHook(() => useExportStorage());

    let existing;
    act(() => {
      existing = result.current.checkExistingSession("thread-123");
    });

    expect(existing).not.toBeNull();
    expect(result.current.existingSession).not.toBeNull();
  });

  it("resumes existing session", () => {
    const { result } = renderHook(() => useExportStorage());

    const existingSession = {
      threadId: "thread-123",
      currentStep: "completed" as const,
      atsReport: {
        keyword_match_score: 90,
        matched_keywords: [],
        missing_keywords: [],
        formatting_issues: [],
        recommendations: [],
        analyzed_at: new Date().toISOString(),
      },
      linkedinSuggestions: null,
      exportCompleted: true,
      startedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
    };

    act(() => {
      result.current.resumeSession(existingSession);
    });

    expect(result.current.session).not.toBeNull();
    expect(result.current.session?.exportCompleted).toBe(true);
  });

  it("clears session", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    act(() => {
      result.current.clearSession("thread-123");
    });

    expect(result.current.session).toBeNull();
    expect(result.current.existingSession).toBeNull();
  });

  it("syncs from backend", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    act(() => {
      result.current.syncFromBackend({
        export_step: "completed",
        export_completed: true,
        ats_report: {
          keyword_match_score: 75,
          matched_keywords: ["Python"],
          missing_keywords: [],
          formatting_issues: [],
          recommendations: [],
          analyzed_at: new Date().toISOString(),
        },
      });
    });

    expect(result.current.session?.currentStep).toBe("completed");
    expect(result.current.session?.exportCompleted).toBe(true);
    expect(result.current.session?.atsReport?.keyword_match_score).toBe(75);
  });

  it("returns correct ATS score passing status", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    // Initially no report
    expect(result.current.isATSScorePassing()).toBe(false);

    // Add passing score
    act(() => {
      result.current.saveATSReport({
        keyword_match_score: 80,
        matched_keywords: [],
        missing_keywords: [],
        formatting_issues: [],
        recommendations: [],
        analyzed_at: new Date().toISOString(),
      });
    });

    expect(result.current.isATSScorePassing()).toBe(true);

    // Add failing score
    act(() => {
      result.current.saveATSReport({
        keyword_match_score: 50,
        matched_keywords: [],
        missing_keywords: [],
        formatting_issues: [],
        recommendations: [],
        analyzed_at: new Date().toISOString(),
      });
    });

    expect(result.current.isATSScorePassing()).toBe(false);
  });

  it("returns correct progress percentage", () => {
    const { result } = renderHook(() => useExportStorage());

    act(() => {
      result.current.startSession("thread-123");
    });

    // idle = 0%
    expect(result.current.getProgressPercentage()).toBe(0);

    act(() => {
      result.current.updateStep("optimizing");
    });

    // optimizing is step 1 of 7 (excluding idle)
    expect(result.current.getProgressPercentage()).toBeGreaterThan(0);

    act(() => {
      result.current.updateStep("completed");
    });

    // completed = 100%
    expect(result.current.getProgressPercentage()).toBe(100);
  });
});
