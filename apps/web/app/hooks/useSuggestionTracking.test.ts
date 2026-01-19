import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Mock the dependent modules before importing the hook
const mockRecordEvent = vi.fn();

// Mock useAuth since usePreferences depends on it
vi.mock("./useAuth", () => ({
  useAuth: () => ({
    isAuthenticated: false,
    user: null,
    isLoading: false,
    login: vi.fn(),
    verify: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  }),
}));

// Mock usePreferences to provide the recordEvent function
vi.mock("./usePreferences", () => ({
  usePreferences: () => ({
    preferences: {},
    isLoading: false,
    error: null,
    updatePreferences: vi.fn(),
    resetPreferences: vi.fn(),
    recordEvent: mockRecordEvent,
    refresh: vi.fn(),
  }),
}));

import { useSuggestionTracking, TrackedSuggestion } from "./useSuggestionTracking";

describe("useSuggestionTracking", () => {
  const mockSuggestion: TrackedSuggestion = {
    id: "sug-123",
    location: "experience.0",
    original_text: "Worked on projects",
    proposed_text: "Led development of 5 key projects, delivering $2M in value",
    rationale: "Added quantification and action verb",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  /**
   * Test: Hook initializes with expected functions.
   * Verifies the hook returns all required tracking functions.
   */
  it("returns tracking functions", () => {
    const { result } = renderHook(() => useSuggestionTracking());

    expect(result.current.trackAccept).toBeDefined();
    expect(result.current.trackReject).toBeDefined();
    expect(result.current.wrapAcceptHandler).toBeDefined();
    expect(result.current.wrapRejectHandler).toBeDefined();
  });

  /**
   * Test: Accepting a suggestion sends correct event type.
   * Verifies suggestion_accept event is recorded.
   */
  it("tracks suggestion acceptance", async () => {
    const { result } = renderHook(() =>
      useSuggestionTracking({ threadId: "test-123" })
    );

    await act(async () => {
      await result.current.trackAccept(mockSuggestion);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "suggestion_accept",
        thread_id: "test-123",
        event_data: expect.objectContaining({
          suggestion_id: "sug-123",
          location: "experience.0",
        }),
      })
    );
  });

  /**
   * Test: Rejecting a suggestion sends correct event type.
   * Verifies suggestion_reject event is recorded.
   */
  it("tracks suggestion rejection", async () => {
    const { result } = renderHook(() =>
      useSuggestionTracking({ threadId: "test-123" })
    );

    await act(async () => {
      await result.current.trackReject(mockSuggestion, "Too verbose");
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "suggestion_reject",
        event_data: expect.objectContaining({
          suggestion_id: "sug-123",
          rejection_reason: "Too verbose",
        }),
      })
    );
  });

  /**
   * Test: Modified acceptance is tracked.
   * Verifies when user modifies suggestion before accepting.
   */
  it("tracks modified acceptance", async () => {
    const { result } = renderHook(() =>
      useSuggestionTracking({ threadId: "test-123" })
    );

    const modifiedText = "Led development of 3 key projects";

    await act(async () => {
      await result.current.trackAccept(mockSuggestion, modifiedText);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          was_modified: true,
          final_text: modifiedText,
        }),
      })
    );
  });

  /**
   * Test: Unmodified acceptance is tracked correctly.
   * Verifies was_modified is false when text unchanged.
   */
  it("tracks unmodified acceptance", async () => {
    const { result } = renderHook(() => useSuggestionTracking());

    await act(async () => {
      await result.current.trackAccept(mockSuggestion);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          was_modified: false,
        }),
      })
    );
  });

  /**
   * Test: Disabled tracking prevents events.
   * Verifies enabled flag properly disables tracking.
   */
  it("does not track when disabled", async () => {
    const { result } = renderHook(() =>
      useSuggestionTracking({ enabled: false })
    );

    await act(async () => {
      await result.current.trackAccept(mockSuggestion);
      await result.current.trackReject(mockSuggestion);
    });

    expect(mockRecordEvent).not.toHaveBeenCalled();
  });

  /**
   * Test: Wrapped accept handler calls both tracking and original.
   * Verifies wrapAcceptHandler integrates properly.
   */
  it("wrapAcceptHandler calls tracking and original handler", async () => {
    const originalHandler = vi.fn();
    const { result } = renderHook(() =>
      useSuggestionTracking({ threadId: "test-123" })
    );

    const wrappedHandler = result.current.wrapAcceptHandler(originalHandler);

    await act(async () => {
      await wrappedHandler(mockSuggestion);
    });

    expect(mockRecordEvent).toHaveBeenCalled();
    expect(originalHandler).toHaveBeenCalledWith(mockSuggestion);
  });

  /**
   * Test: Wrapped reject handler calls both tracking and original.
   * Verifies wrapRejectHandler integrates properly.
   */
  it("wrapRejectHandler calls tracking and original handler", async () => {
    const originalHandler = vi.fn();
    const { result } = renderHook(() =>
      useSuggestionTracking({ threadId: "test-123" })
    );

    const wrappedHandler = result.current.wrapRejectHandler(originalHandler);

    await act(async () => {
      await wrappedHandler(mockSuggestion, "Don't like it");
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          rejection_reason: "Don't like it",
        }),
      })
    );
    expect(originalHandler).toHaveBeenCalledWith(mockSuggestion);
  });

  /**
   * Test: Style pattern extraction for formal tone acceptance.
   * Verifies formal tone preference is detected on accept.
   */
  it("extracts formal tone preference on acceptance", async () => {
    const formalSuggestion: TrackedSuggestion = {
      id: "sug-456",
      location: "summary",
      original_text: "Helped with projects",
      proposed_text: "Spearheaded implementation of enterprise solutions",
      rationale: "More formal tone",
    };

    const { result } = renderHook(() => useSuggestionTracking());

    await act(async () => {
      await result.current.trackAccept(formalSuggestion);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          prefers_formal_tone: true,
        }),
      })
    );
  });

  /**
   * Test: Style pattern extraction for formal tone rejection.
   * Verifies formal tone dislike is detected on reject.
   */
  it("extracts formal tone dislike on rejection", async () => {
    const formalSuggestion: TrackedSuggestion = {
      id: "sug-456",
      location: "summary",
      original_text: "Helped with projects",
      proposed_text: "Spearheaded implementation of enterprise solutions",
      rationale: "More formal tone",
    };

    const { result } = renderHook(() => useSuggestionTracking());

    await act(async () => {
      await result.current.trackReject(formalSuggestion);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          dislikes_formal_tone: true,
        }),
      })
    );
  });

  /**
   * Test: Quantification preference extraction.
   * Verifies quantification preference is detected.
   */
  it("extracts quantification preference on acceptance", async () => {
    const quantSuggestion: TrackedSuggestion = {
      id: "sug-789",
      location: "experience",
      original_text: "Improved sales",
      proposed_text: "Increased sales by 40% serving 10,000+ customers",
      rationale: "Added metrics",
    };

    const { result } = renderHook(() => useSuggestionTracking());

    await act(async () => {
      await result.current.trackAccept(quantSuggestion);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          prefers_quantification: true,
        }),
      })
    );
  });

  /**
   * Test: Action verb preference extraction.
   * Verifies action verb usage preference is detected.
   */
  it("extracts action verb preference on acceptance", async () => {
    const actionSuggestion: TrackedSuggestion = {
      id: "sug-action",
      location: "experience",
      original_text: "Was responsible for team",
      proposed_text: "Managed cross-functional team of 8 engineers",
      rationale: "Stronger action verb",
    };

    const { result } = renderHook(() => useSuggestionTracking());

    await act(async () => {
      await result.current.trackAccept(actionSuggestion);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          prefers_action_verbs: true,
        }),
      })
    );
  });

  /**
   * Test: Long text is truncated for storage.
   * Verifies text is limited to 500 characters.
   */
  it("truncates long text for storage", async () => {
    const longSuggestion: TrackedSuggestion = {
      id: "sug-long",
      location: "summary",
      original_text: "x".repeat(1000),
      proposed_text: "y".repeat(1000),
    };

    const { result } = renderHook(() => useSuggestionTracking());

    await act(async () => {
      await result.current.trackAccept(longSuggestion);
    });

    const call = mockRecordEvent.mock.calls[0][0];
    expect(call.event_data.original_text.length).toBe(500);
    expect(call.event_data.proposed_text.length).toBe(500);
  });
});
