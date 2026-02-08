import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useEditorAssist } from "./useEditorAssist";

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("useEditorAssist", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("initial state", () => {
    it("returns correct initial values", () => {
      const { result } = renderHook(() => useEditorAssist("thread-123"));

      expect(result.current.suggestion).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it("returns all methods", () => {
      const { result } = renderHook(() => useEditorAssist("thread-123"));

      expect(typeof result.current.requestSuggestion).toBe("function");
      expect(typeof result.current.clearSuggestion).toBe("function");
      expect(typeof result.current.chatWithDraftingAgent).toBe("function");
      expect(typeof result.current.syncEditor).toBe("function");
    });
  });

  describe("requestSuggestion", () => {
    it("calls /editor/assist with correct payload", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, suggestion: "Improved text" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "original text");
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/optimize/thread-123/editor/assist",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "improve",
            selected_text: "original text",
          }),
        })
      );
    });

    it("sets suggestion on success", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, suggestion: "Better text" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "original text");
      });

      expect(result.current.suggestion).toEqual({
        success: true,
        original: "original text",
        suggestion: "Better text",
        action: "improve",
      });
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it("passes instructions for custom action", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, suggestion: "Custom result" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("custom", "some text", "make it shorter");
      });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.instructions).toBe("make it shorter");
    });

    it("sets error on API failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Server error" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "text");
      });

      expect(result.current.error).toBe("Server error");
      expect(result.current.suggestion).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });

    it("sets error on backend failure response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: false, error: "LLM unavailable" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "text");
      });

      expect(result.current.error).toBe("LLM unavailable");
      expect(result.current.suggestion).toBeNull();
    });

    it("sets error on network failure", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "text");
      });

      expect(result.current.error).toBe("Network error");
      expect(result.current.isLoading).toBe(false);
    });

    it("sets error when threadId is null", async () => {
      const { result } = renderHook(() => useEditorAssist(null));

      await act(async () => {
        await result.current.requestSuggestion("improve", "text");
      });

      expect(result.current.error).toBe("No active workflow");
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("sets error when selectedText is empty", async () => {
      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "  ");
      });

      expect(result.current.error).toBe("No text selected");
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("sets isLoading during request", async () => {
      let resolvePromise: (value: any) => void;
      mockFetch.mockReturnValueOnce(
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
      );

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      // Start request (don't await)
      let promise: Promise<void>;
      act(() => {
        promise = result.current.requestSuggestion("improve", "text");
      });

      // Should be loading
      expect(result.current.isLoading).toBe(true);

      // Resolve
      await act(async () => {
        resolvePromise!({
          ok: true,
          json: () => Promise.resolve({ success: true, suggestion: "Done" }),
        });
        await promise!;
      });

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe("chatWithDraftingAgent", () => {
    it("calls /editor/chat with correct payload", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ success: true, suggestion: "Chat reply", cache_hit: true }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      const history = [
        { role: "user" as const, content: "previous message" },
        { role: "assistant" as const, content: "previous reply" },
      ];

      let returnValue: any;
      await act(async () => {
        returnValue = await result.current.chatWithDraftingAgent("selected", "make it better", history);
      });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.selected_text).toBe("selected");
      expect(body.user_message).toBe("make it better");
      expect(body.chat_history).toEqual(history);

      expect(returnValue).toEqual({ suggestion: "Chat reply", cacheHit: true });
      // Also sets as current suggestion for apply flow
      expect(result.current.suggestion).toEqual({
        success: true,
        original: "selected",
        suggestion: "Chat reply",
        action: "custom",
      });
    });

    it("returns null on error", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Chat error"));

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      let returnValue: any;
      await act(async () => {
        returnValue = await result.current.chatWithDraftingAgent("text", "msg", []);
      });

      expect(returnValue).toBeNull();
      expect(result.current.error).toBe("Chat error");
    });

    it("returns null when threadId is null", async () => {
      const { result } = renderHook(() => useEditorAssist(null));

      let returnValue: any;
      await act(async () => {
        returnValue = await result.current.chatWithDraftingAgent("text", "msg", []);
      });

      expect(returnValue).toBeNull();
      expect(result.current.error).toBe("No active workflow");
    });

    it("returns null when selectedText is empty", async () => {
      const { result } = renderHook(() => useEditorAssist("thread-123"));

      let returnValue: any;
      await act(async () => {
        returnValue = await result.current.chatWithDraftingAgent("  ", "msg", []);
      });

      expect(returnValue).toBeNull();
      expect(result.current.error).toBe("No text selected");
    });

    it("defaults cacheHit to false when not in response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, suggestion: "Reply" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      let returnValue: any;
      await act(async () => {
        returnValue = await result.current.chatWithDraftingAgent("text", "msg", []);
      });

      expect(returnValue!.cacheHit).toBe(false);
    });
  });

  describe("clearSuggestion", () => {
    it("clears suggestion and error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, suggestion: "Result" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "text");
      });

      expect(result.current.suggestion).not.toBeNull();

      act(() => {
        result.current.clearSuggestion();
      });

      expect(result.current.suggestion).toBeNull();
      expect(result.current.error).toBeNull();
    });
  });

  describe("syncEditor", () => {
    it("calls /editor/sync with HTML and tracking data", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        result.current.syncEditor("<h1>Resume</h1>", "old text", "new text", "make it better");
        await new Promise((r) => setTimeout(r, 0));
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/optimize/thread-123/editor/sync",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            html: "<h1>Resume</h1>",
            original: "old text",
            suggestion: "new text",
            user_message: "make it better",
          }),
        })
      );
    });

    it("sends empty strings for optional params", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        result.current.syncEditor("<h1>Resume</h1>");
        await new Promise((r) => setTimeout(r, 0));
      });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.original).toBe("");
      expect(body.suggestion).toBe("");
      expect(body.user_message).toBe("");
    });

    it("does not call fetch when threadId is null", () => {
      const { result } = renderHook(() => useEditorAssist(null));

      act(() => {
        result.current.syncEditor("<h1>Resume</h1>");
      });

      expect(mockFetch).not.toHaveBeenCalled();
    });

    it("aborts previous sync when new one is triggered", () => {
      const abortSpies: ReturnType<typeof vi.fn>[] = [];
      const originalAbortController = global.AbortController;

      class MockAbortController {
        signal = {};
        abort = vi.fn();
        constructor() {
          abortSpies.push(this.abort);
        }
      }
      global.AbortController = MockAbortController as any;

      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolves

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      act(() => {
        result.current.syncEditor("<h1>V1</h1>");
      });

      act(() => {
        result.current.syncEditor("<h1>V2</h1>");
      });

      // First controller should have been aborted
      expect(abortSpies[0]).toHaveBeenCalledTimes(1);

      global.AbortController = originalAbortController;
    });

    it("ignores fetch errors silently", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Sync failed"));

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      // Should not throw
      await act(async () => {
        result.current.syncEditor("<h1>Resume</h1>");
        // Wait for the rejection to be handled
        await new Promise((r) => setTimeout(r, 10));
      });

      // No error state set (fire and forget)
      expect(result.current.error).toBeNull();
    });
  });
});
