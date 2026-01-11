import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DiscoveryChat from "./DiscoveryChat";

describe("DiscoveryChat", () => {
  const defaultProps = {
    messages: [],
    pendingPrompt: null,
    totalPrompts: 5,
    currentPromptNumber: 1,
    exchanges: 0,
    canConfirm: false,
    onSubmitResponse: vi.fn().mockResolvedValue(undefined),
    onConfirmComplete: vi.fn().mockResolvedValue(undefined),
    isSubmitting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Message Display", () => {
    it("displays agent messages", () => {
      const props = {
        ...defaultProps,
        messages: [
          {
            role: "agent" as const,
            content: "Tell me about your experience",
            timestamp: "2024-01-01",
          },
        ],
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.getByText("Tell me about your experience")
      ).toBeInTheDocument();
    });

    it("displays user messages", () => {
      const props = {
        ...defaultProps,
        messages: [
          {
            role: "user" as const,
            content: "I worked on Docker projects",
            timestamp: "2024-01-01",
          },
        ],
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.getByText("I worked on Docker projects")
      ).toBeInTheDocument();
    });

    it("shows experiences captured badge when present", () => {
      const props = {
        ...defaultProps,
        messages: [
          {
            role: "user" as const,
            content: "I led migration",
            timestamp: "2024-01-01",
            experiencesExtracted: ["exp-1"],
          },
        ],
      };

      render(<DiscoveryChat {...props} />);

      expect(screen.getByText(/1 experience\(s\) captured/i)).toBeInTheDocument();
    });
  });

  describe("Pending Prompt", () => {
    it("displays pending prompt", () => {
      const props = {
        ...defaultProps,
        pendingPrompt: {
          id: "p1",
          question: "What side projects have you worked on?",
          intent: "Surface non-work experience",
          relatedGaps: ["Limited exposure"],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.getByText("What side projects have you worked on?")
      ).toBeInTheDocument();
    });

    it("shows intent hint", () => {
      const props = {
        ...defaultProps,
        pendingPrompt: {
          id: "p1",
          question: "Test question?",
          intent: "Surface non-work experience",
          relatedGaps: [],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.getByText(/Surface non-work experience/i)
      ).toBeInTheDocument();
    });

    it("shows related gaps as tags", () => {
      const props = {
        ...defaultProps,
        pendingPrompt: {
          id: "p1",
          question: "Test?",
          intent: "Intent",
          relatedGaps: ["No Kubernetes experience"],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.getByText("No Kubernetes experience")
      ).toBeInTheDocument();
    });
  });

  describe("Input and Submission", () => {
    it("shows input area when pending prompt exists", () => {
      const props = {
        ...defaultProps,
        pendingPrompt: {
          id: "p1",
          question: "Test?",
          intent: "",
          relatedGaps: [],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.getByPlaceholderText(/Share your experience/i)
      ).toBeInTheDocument();
    });

    it("submits response on button click", async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      const props = {
        ...defaultProps,
        onSubmitResponse: onSubmit,
        pendingPrompt: {
          id: "p1",
          question: "Test?",
          intent: "",
          relatedGaps: [],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      const input = screen.getByPlaceholderText(/Share your experience/i);
      fireEvent.change(input, { target: { value: "My response" } });

      const sendButton = screen.getByRole("button", { name: /send/i });
      fireEvent.click(sendButton);

      expect(onSubmit).toHaveBeenCalledWith("My response");
    });

    it("disables submit when empty", () => {
      const props = {
        ...defaultProps,
        pendingPrompt: {
          id: "p1",
          question: "Test?",
          intent: "",
          relatedGaps: [],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      const sendButton = screen.getByRole("button", { name: /send/i });
      expect(sendButton).toBeDisabled();
    });

    it("has skip button", () => {
      const props = {
        ...defaultProps,
        pendingPrompt: {
          id: "p1",
          question: "Test?",
          intent: "",
          relatedGaps: [],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
    });
  });

  describe("Progress Indicator", () => {
    it("shows question number and total", () => {
      const props = {
        ...defaultProps,
        currentPromptNumber: 3,
        totalPrompts: 5,
      };

      render(<DiscoveryChat {...props} />);

      expect(screen.getByText(/Question 3 of 5/i)).toBeInTheDocument();
    });

    it("shows exchange count", () => {
      const props = {
        ...defaultProps,
        exchanges: 2,
      };

      render(<DiscoveryChat {...props} />);

      expect(screen.getByText(/Exchanges: 2\/3/i)).toBeInTheDocument();
    });
  });

  describe("Completion", () => {
    it("shows Complete Discovery button when canConfirm is true", () => {
      const props = {
        ...defaultProps,
        canConfirm: true,
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.getByRole("button", { name: /Complete Discovery/i })
      ).toBeInTheDocument();
    });

    it("does not show Complete Discovery when canConfirm is false", () => {
      const props = {
        ...defaultProps,
        canConfirm: false,
      };

      render(<DiscoveryChat {...props} />);

      expect(
        screen.queryByRole("button", { name: /Complete Discovery/i })
      ).not.toBeInTheDocument();
    });

    it("calls onConfirmComplete when Complete Discovery clicked", () => {
      const onConfirm = vi.fn().mockResolvedValue(undefined);
      const props = {
        ...defaultProps,
        canConfirm: true,
        onConfirmComplete: onConfirm,
      };

      render(<DiscoveryChat {...props} />);

      fireEvent.click(
        screen.getByRole("button", { name: /Complete Discovery/i })
      );

      expect(onConfirm).toHaveBeenCalled();
    });

    it("shows ready to complete message when 3+ exchanges", () => {
      const props = {
        ...defaultProps,
        exchanges: 3,
        canConfirm: true,
      };

      render(<DiscoveryChat {...props} />);

      expect(screen.getByText(/Ready to complete/i)).toBeInTheDocument();
    });
  });

  describe("Loading State", () => {
    it("shows typing indicator when waiting for response", () => {
      const props = {
        ...defaultProps,
        messages: [
          { role: "agent" as const, content: "Question", timestamp: "2024-01-01" },
          { role: "user" as const, content: "Answer", timestamp: "2024-01-01" },
        ],
        pendingPrompt: null,
      };

      render(<DiscoveryChat {...props} />);

      // Should show typing indicator (bouncing dots)
      const bouncingDots = document.querySelectorAll(".animate-bounce");
      expect(bouncingDots.length).toBeGreaterThan(0);
    });

    it("disables input when submitting", () => {
      const props = {
        ...defaultProps,
        isSubmitting: true,
        pendingPrompt: {
          id: "p1",
          question: "Test?",
          intent: "",
          relatedGaps: [],
          priority: 1,
          asked: false,
        },
      };

      render(<DiscoveryChat {...props} />);

      const input = screen.getByPlaceholderText(/Share your experience/i);
      expect(input).toBeDisabled();
    });
  });
});
