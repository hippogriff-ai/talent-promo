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
      expect(typeof result.current.applyRevision).toBe("function");
    });
  });

  describe("requestSuggestion", () => {
    it("calls /api/resume revision with correct payload", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, proposedText: "Improved text" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "original text");
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/resume/documents/thread-123/revision",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "improve",
            user_message: "Improve the selected resume text.",
            selected_text: "original text",
          }),
        })
      );
    });

    it("sends editor selection context when provided", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, proposedText: "Improved text" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "original text", undefined, {
          from: 10,
          to: 23,
          context_before: "Acme Corp",
          context_after: "Next bullet",
        });
      });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.editor_selection).toEqual({
        from: 10,
        to: 23,
        context_before: "Acme Corp",
        context_after: "Next bullet",
      });
    });

    it("sets suggestion on success", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            revisionId: "rev-1",
            proposedText: "Better text",
            targetUnit: { text: "original text", label: "Experience > bullet 1" },
            canApply: true,
          }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      await act(async () => {
        await result.current.requestSuggestion("improve", "original text");
      });

      expect(result.current.suggestion).toEqual(expect.objectContaining({
        success: true,
        original: "original text",
        suggestion: "Better text",
        action: "improve",
        revisionId: "rev-1",
        canApply: true,
      }));
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
      expect(body.user_message).toBe("make it shorter");
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
          Promise.resolve({
            success: true,
            proposedText: "Chat reply",
            revisionId: "revision-1",
            canApply: true,
            verification: { passed: true, summary: "Verification passed." },
          }),
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
      expect(body.action).toBe("custom");
      expect(body.chat_history).toEqual(history);

      expect(returnValue).toEqual(expect.objectContaining({
        suggestion: "Chat reply",
        cacheHit: false,
        revisionId: "revision-1",
        canApply: true,
      }));
      // Also sets as current suggestion for apply flow
      expect(result.current.suggestion).toEqual(expect.objectContaining({
        success: true,
        original: "selected",
        suggestion: "Chat reply",
        action: "custom",
        revisionId: "revision-1",
      }));
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

  describe("applyRevision", () => {
    it("calls /api/resume apply with revision id", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, resumeHtml: "<h1>Updated</h1>" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      let returnValue: any;
      await act(async () => {
        returnValue = await result.current.applyRevision("revision-1", true);
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/resume/documents/thread-123/apply",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            revision_id: "revision-1",
            override_verification: true,
          }),
        })
      );
      expect(returnValue.resumeHtml).toBe("<h1>Updated</h1>");
    });

    it("sets error when apply fails", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: false, error: "Patch mismatch" }),
      });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      let returnValue: any;
      await act(async () => {
        returnValue = await result.current.applyRevision("revision-1");
      });
      expect(returnValue).toBeNull();
      expect(result.current.error).toBe("Patch mismatch");
    });
  });

  describe("syncEditor", () => {
    it("calls /editor/sync with HTML and tracking data", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      let synced: boolean | undefined;
      await act(async () => {
        synced = await result.current.syncEditor("<h1>Resume</h1>", "old text", "new text", "make it better");
      });

      expect(synced).toBe(true);
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
        await result.current.syncEditor("<h1>Resume</h1>");
      });

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.original).toBe("");
      expect(body.suggestion).toBe("");
      expect(body.user_message).toBe("");
    });

    it("does not call fetch when threadId is null", async () => {
      const { result } = renderHook(() => useEditorAssist(null));

      let synced: boolean | undefined;
      await act(async () => {
        synced = await result.current.syncEditor("<h1>Resume</h1>");
      });

      expect(synced).toBe(false);
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

    it("sets error and returns false when sync fails", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Sync failed"));

      const { result } = renderHook(() => useEditorAssist("thread-123"));

      let synced: boolean | undefined;
      await act(async () => {
        synced = await result.current.syncEditor("<h1>Resume</h1>");
      });

      expect(synced).toBe(false);
      expect(result.current.error).toBe("Sync failed");
    });
  });
});
