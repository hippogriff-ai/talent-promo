import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

import { useEditTracking } from "./useEditTracking";

describe("useEditTracking", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  /**
   * Test: Hook initializes with expected functions.
   * Verifies the hook returns all required tracking functions.
   */
  it("returns tracking functions", () => {
    const { result } = renderHook(() => useEditTracking());

    expect(result.current.trackEdit).toBeDefined();
    expect(result.current.trackTextChange).toBeDefined();
    expect(result.current.trackSectionReorder).toBeDefined();
    expect(result.current.trackFormattingChange).toBeDefined();
    expect(result.current.flush).toBeDefined();
  });

  /**
   * Test: Events are debounced before sending.
   * Verifies events are batched and sent after debounce timeout.
   */
  it("debounces edit events before sending", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 1000, threadId: "test-123" })
    );

    act(() => {
      result.current.trackEdit({
        type: "text_change",
        before: "old text",
        after: "new text",
      });
    });

    // Event should not be sent immediately
    expect(mockRecordEvent).not.toHaveBeenCalled();

    // Advance timer past debounce
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    // Event should now be sent
    expect(mockRecordEvent).toHaveBeenCalled();
  });

  /**
   * Test: Multiple events within debounce window are batched.
   * Verifies multiple rapid edits are sent together.
   */
  it("batches multiple events within debounce window", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 1000, threadId: "test-123" })
    );

    act(() => {
      result.current.trackEdit({ type: "text_change", before: "a", after: "b" });
      result.current.trackEdit({ type: "text_change", before: "b", after: "c" });
      result.current.trackEdit({ type: "text_change", before: "c", after: "d" });
    });

    // Advance timer past debounce
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    // All events should be sent
    expect(mockRecordEvent).toHaveBeenCalledTimes(3);
  });

  /**
   * Test: Disabled tracking prevents event sending.
   * Verifies the enabled flag properly disables tracking.
   */
  it("does not track when disabled", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ enabled: false })
    );

    act(() => {
      result.current.trackEdit({
        type: "text_change",
        before: "old",
        after: "new",
      });
    });

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(mockRecordEvent).not.toHaveBeenCalled();
  });

  /**
   * Test: trackTextChange ignores identical content.
   * Verifies no event is sent when before and after are the same.
   */
  it("ignores identical text in trackTextChange", async () => {
    const { result } = renderHook(() => useEditTracking({ debounceMs: 100 }));

    act(() => {
      result.current.trackTextChange("same text", "same text");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockRecordEvent).not.toHaveBeenCalled();
  });

  /**
   * Test: Section detection from content patterns.
   * Verifies the hook automatically detects resume sections.
   */
  it("detects section from content", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 100, threadId: "test-123" })
    );

    act(() => {
      result.current.trackTextChange(
        "Old summary",
        "New professional summary with more detail"
      );
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "edit",
        event_data: expect.objectContaining({
          section: "summary",
        }),
      })
    );
  });

  /**
   * Test: Style pattern extraction for first person.
   * Verifies the hook detects first person usage.
   */
  it("extracts first person usage pattern", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 100, threadId: "test-123" })
    );

    act(() => {
      result.current.trackTextChange("Led team", "I led the team of 5 engineers");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          uses_first_person: true,
        }),
      })
    );
  });

  /**
   * Test: Style pattern extraction for quantification.
   * Verifies the hook detects numeric quantification.
   */
  it("extracts quantification usage pattern", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 100, threadId: "test-123" })
    );

    act(() => {
      result.current.trackTextChange(
        "Improved performance",
        "Improved performance by 40% across 5 teams"
      );
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_data: expect.objectContaining({
          uses_quantification: true,
        }),
      })
    );
  });

  /**
   * Test: Formatting change tracking.
   * Verifies formatting changes are tracked with metadata.
   */
  it("tracks formatting changes with metadata", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 100, threadId: "test-123" })
    );

    act(() => {
      result.current.trackFormattingChange("bold", true, "experience");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "edit",
        event_data: expect.objectContaining({
          edit_type: "formatting_change",
          section: "experience",
        }),
      })
    );
  });

  /**
   * Test: Section reorder tracking.
   * Verifies section reordering is tracked with new index.
   */
  it("tracks section reordering", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 100, threadId: "test-123" })
    );

    act(() => {
      result.current.trackSectionReorder("skills", 2);
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "edit",
        event_data: expect.objectContaining({
          edit_type: "section_reorder",
          section: "skills",
          new_index: 2,
        }),
      })
    );
  });

  /**
   * Test: Manual flush sends events immediately.
   * Verifies flush() bypasses debounce.
   */
  it("flush sends events immediately", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 5000, threadId: "test-123" })
    );

    act(() => {
      result.current.trackEdit({
        type: "text_change",
        before: "old",
        after: "new",
      });
    });

    // Flush immediately without waiting
    await act(async () => {
      await result.current.flush();
    });

    expect(mockRecordEvent).toHaveBeenCalled();
  });

  /**
   * Test: Thread ID is included in events.
   * Verifies the thread_id is passed to recorded events.
   */
  it("includes thread_id in events", async () => {
    const { result } = renderHook(() =>
      useEditTracking({ debounceMs: 100, threadId: "workflow-abc-123" })
    );

    act(() => {
      result.current.trackTextChange("before", "after");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockRecordEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        thread_id: "workflow-abc-123",
      })
    );
  });
});
