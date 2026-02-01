import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DraftingChat from "./DraftingChat";

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("DraftingChat", () => {
  const defaultProps = {
    threadId: "test-thread-123",
    selectedText: "",
    onApplySuggestion: vi.fn(),
    onClearSelection: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Initial State", () => {
    /**
     * Tests that the chat shows helpful placeholder when no text is selected.
     */
    it("shows instruction when no text selected", () => {
      render(<DraftingChat {...defaultProps} />);

      expect(screen.getByText(/Select text in the editor/i)).toBeInTheDocument();
    });

    /**
     * Tests that input is disabled when no text is selected.
     */
    it("disables input when no text selected", () => {
      render(<DraftingChat {...defaultProps} />);

      const input = screen.getByPlaceholderText(/Select text first/i);
      expect(input).toBeDisabled();
    });

    /**
     * Tests that the header displays correctly.
     */
    it("displays header with title", () => {
      render(<DraftingChat {...defaultProps} />);

      expect(screen.getByText("AI Assistant")).toBeInTheDocument();
    });
  });

  describe("Text Selection", () => {
    /**
     * Tests that selected text preview appears when text is selected.
     */
    it("shows selected text preview", () => {
      render(<DraftingChat {...defaultProps} selectedText="Led development team" />);

      expect(screen.getByText(/Selected:/i)).toBeInTheDocument();
      expect(screen.getByText(/Led development team/i)).toBeInTheDocument();
    });

    /**
     * Tests that quick action buttons appear when text is selected.
     */
    it("shows quick action buttons when text selected", () => {
      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      expect(screen.getByRole("button", { name: /Improve/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Shorten/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Rewrite/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Remove/i })).toBeInTheDocument();
    });

    /**
     * Tests that clear button calls onClearSelection callback.
     */
    it("calls onClearSelection when clear button clicked", () => {
      const onClearSelection = vi.fn();
      render(
        <DraftingChat
          {...defaultProps}
          selectedText="Some text"
          onClearSelection={onClearSelection}
        />
      );

      fireEvent.click(screen.getByText("Clear"));
      expect(onClearSelection).toHaveBeenCalled();
    });

    /**
     * Tests that input is enabled when text is selected.
     */
    it("enables input when text is selected", () => {
      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      expect(input).not.toBeDisabled();
    });
  });

  describe("User Input", () => {
    /**
     * Tests that user can type in the input field.
     */
    it("allows typing in input", () => {
      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "rewrite this" } });

      expect(input).toHaveValue("rewrite this");
    });

    /**
     * Tests that pressing Enter sends the message.
     */
    it("sends message on Enter key", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ suggestion: "Improved text", explanation: "Made it better" }),
      });

      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "improve" } });
      fireEvent.keyDown(input, { key: "Enter" });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });
    });

    /**
     * Tests that Shift+Enter does not send message (for multiline).
     */
    it("does not send on Shift+Enter", () => {
      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "improve" } });
      fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe("Remove Command", () => {
    /**
     * Tests that remove command is handled locally without API call.
     */
    it("handles remove command locally", async () => {
      render(<DraftingChat {...defaultProps} selectedText="Text to remove" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "remove this" } });
      fireEvent.click(screen.getByRole("button", { name: /Send/i }));

      await waitFor(() => {
        expect(screen.getByText(/I'll remove the selected text/i)).toBeInTheDocument();
      });

      // Should not call API for remove
      expect(mockFetch).not.toHaveBeenCalled();
    });

    /**
     * Tests that remove command shows Apply button.
     */
    it("shows Apply button after remove command", async () => {
      render(<DraftingChat {...defaultProps} selectedText="Text to remove" />);

      fireEvent.click(screen.getByRole("button", { name: /Remove/i }));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Apply Suggestion/i })).toBeInTheDocument();
      });
    });
  });

  describe("API Integration", () => {
    /**
     * Tests that improve command calls API with correct parameters.
     */
    it("calls API for improve command", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          suggestion: "Led cross-functional development team of 8 engineers",
          explanation: "Added quantification and action verb",
        }),
      });

      render(<DraftingChat {...defaultProps} selectedText="Led development team" />);

      fireEvent.click(screen.getByRole("button", { name: /Improve/i }));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining("/editor/assist"),
          expect.objectContaining({
            method: "POST",
            body: expect.stringContaining("improve"),
          })
        );
      });
    });

    /**
     * Tests that API response suggestion is displayed.
     */
    it("displays API suggestion in message", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          suggestion: "Improved text content",
          explanation: "Here's a better version",
        }),
      });

      render(<DraftingChat {...defaultProps} selectedText="Original text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "improve" } });
      fireEvent.click(screen.getByRole("button", { name: /Send/i }));

      await waitFor(() => {
        expect(screen.getByText(/Improved text content/i)).toBeInTheDocument();
      });
    });

    /**
     * Tests that API error is handled gracefully.
     */
    it("handles API error gracefully", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "improve" } });
      fireEvent.click(screen.getByRole("button", { name: /Send/i }));

      await waitFor(() => {
        expect(screen.getByText(/Sorry, I encountered an error/i)).toBeInTheDocument();
      });
    });
  });

  describe("Apply Suggestion", () => {
    /**
     * Tests that Apply button calls onApplySuggestion with correct parameters.
     */
    it("calls onApplySuggestion when Apply clicked", async () => {
      const onApplySuggestion = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          suggestion: "New improved text",
          explanation: "Better version",
        }),
      });

      render(
        <DraftingChat
          {...defaultProps}
          selectedText="Original text"
          onApplySuggestion={onApplySuggestion}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: /Improve/i }));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Apply Suggestion/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /Apply Suggestion/i }));

      expect(onApplySuggestion).toHaveBeenCalledWith("Original text", "New improved text");
    });

    /**
     * Tests that Apply shows confirmation message.
     */
    it("shows confirmation after applying suggestion", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          suggestion: "New text",
          explanation: "Done",
        }),
      });

      render(<DraftingChat {...defaultProps} selectedText="Old text" />);

      fireEvent.click(screen.getByRole("button", { name: /Improve/i }));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Apply Suggestion/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /Apply Suggestion/i }));

      await waitFor(() => {
        expect(screen.getByText(/Applied!/i)).toBeInTheDocument();
      });
    });
  });

  describe("Command Parsing", () => {
    /**
     * Tests that various command keywords are recognized.
     */
    it("recognizes shorten command", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ suggestion: "Shorter", explanation: "Condensed" }),
      });

      render(<DraftingChat {...defaultProps} selectedText="Long text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "make shorter" } });
      fireEvent.click(screen.getByRole("button", { name: /Send/i }));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            body: expect.stringContaining('"action":"shorten"'),
          })
        );
      });
    });

    /**
     * Tests that keyword/ATS commands are recognized.
     */
    it("recognizes keyword command", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ suggestion: "With keywords", explanation: "Added ATS keywords" }),
      });

      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      const input = screen.getByPlaceholderText(/What should I do/i);
      fireEvent.change(input, { target: { value: "add keywords for ATS" } });
      fireEvent.click(screen.getByRole("button", { name: /Send/i }));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            body: expect.stringContaining('"action":"add_keywords"'),
          })
        );
      });
    });
  });

  describe("Loading State", () => {
    /**
     * Tests that loading indicator appears while waiting for API.
     */
    it("shows loading indicator while waiting", async () => {
      // Create a promise that doesn't resolve immediately
      mockFetch.mockImplementation(() => new Promise(() => {}));

      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      fireEvent.click(screen.getByRole("button", { name: /Improve/i }));

      await waitFor(() => {
        // Check for bouncing dots animation
        const dots = document.querySelectorAll(".animate-bounce");
        expect(dots.length).toBeGreaterThan(0);
      });
    });

    /**
     * Tests that buttons are disabled during loading.
     */
    it("disables buttons during loading", async () => {
      mockFetch.mockImplementation(() => new Promise(() => {}));

      render(<DraftingChat {...defaultProps} selectedText="Some text" />);

      fireEvent.click(screen.getByRole("button", { name: /Improve/i }));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Shorten/i })).toBeDisabled();
      });
    });
  });
});
