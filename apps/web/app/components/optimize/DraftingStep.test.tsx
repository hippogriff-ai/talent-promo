import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock the hooks
vi.mock("../../hooks/useDraftingStorage", () => ({
  useDraftingStorage: () => ({
    session: null,
    existingSession: null,
    isLoading: false,
    checkExistingSession: vi.fn().mockReturnValue(null),
    startSession: vi.fn(),
    updateResumeHtml: vi.fn(),
    acceptSuggestion: vi.fn(),
    declineSuggestion: vi.fn(),
    recordEdit: vi.fn(),
    manualSave: vi.fn(),
    restoreVersion: vi.fn(),
    approveDraft: vi.fn(),
    resumeSession: vi.fn(),
    clearSession: vi.fn(),
    syncFromBackend: vi.fn(),
    allSuggestionsResolved: vi.fn().mockReturnValue(false),
    pendingSuggestionsCount: vi.fn().mockReturnValue(2),
  }),
}));

vi.mock("../../hooks/useSuggestions", () => ({
  useSuggestions: () => ({
    isLoading: false,
    error: null,
    acceptSuggestion: vi.fn().mockResolvedValue({ version: "1.1" }),
    declineSuggestion: vi.fn().mockResolvedValue({ version: "1.1" }),
  }),
  useDraftingState: () => ({
    isLoading: false,
    error: null,
    fetchState: vi.fn().mockResolvedValue({}),
    saveManually: vi.fn().mockResolvedValue({ version: "1.1", message: "Saved" }),
    restoreVersion: vi.fn().mockResolvedValue({ version: "1.2" }),
    approveDraft: vi.fn().mockResolvedValue({ success: true }),
  }),
}));

// Mock Tiptap
vi.mock("@tiptap/react", () => ({
  useEditor: () => ({
    chain: () => ({
      focus: () => ({
        toggleBold: () => ({ run: vi.fn() }),
        toggleItalic: () => ({ run: vi.fn() }),
        toggleUnderline: () => ({ run: vi.fn() }),
        toggleHeading: () => ({ run: vi.fn() }),
        toggleBulletList: () => ({ run: vi.fn() }),
      }),
    }),
    isActive: () => false,
    getHTML: () => "<h1>Test</h1>",
    commands: {
      setContent: vi.fn(),
    },
  }),
  EditorContent: ({ editor }: { editor: any }) => (
    <div data-testid="editor-content">Editor Content</div>
  ),
}));

vi.mock("@tiptap/starter-kit", () => ({
  default: {
    configure: () => ({}),
  },
}));

vi.mock("@tiptap/extension-placeholder", () => ({
  default: {
    configure: () => ({}),
  },
}));

vi.mock("@tiptap/extension-underline", () => ({
  default: {},
}));

vi.mock("@tiptap/extension-highlight", () => ({
  default: {
    configure: () => ({}),
  },
}));

// Import after mocks
import DraftingStep from "./DraftingStep";
import { SuggestionList } from "./SuggestionCard";
import VersionHistory from "./VersionHistory";

describe("DraftingStep", () => {
  const defaultProps = {
    threadId: "test-thread-123",
    initialHtml: "<h1>John Doe</h1><h2>Summary</h2><p>Test summary</p>",
    suggestions: [
      {
        id: "sug_1",
        location: "summary",
        original_text: "Test summary",
        proposed_text: "Improved summary with metrics",
        rationale: "More impactful",
        status: "pending",
        created_at: new Date().toISOString(),
      },
      {
        id: "sug_2",
        location: "experience.0",
        original_text: "Worked on projects",
        proposed_text: "Led 5 cross-functional projects",
        rationale: "Quantified achievement",
        status: "pending",
        created_at: new Date().toISOString(),
      },
    ],
    versions: [
      {
        version: "1.0",
        html_content: "<h1>John Doe</h1>",
        trigger: "initial",
        description: "Initial draft",
        created_at: new Date().toISOString(),
      },
    ],
    currentVersion: "1.0",
    draftApproved: false,
    onApprove: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the drafting step", () => {
    render(<DraftingStep {...defaultProps} />);

    expect(screen.getByText("Review & Edit Resume")).toBeInTheDocument();
    expect(screen.getByTestId("editor-content")).toBeInTheDocument();
  });

  it("shows pending suggestions count", () => {
    render(<DraftingStep {...defaultProps} />);

    expect(screen.getByText(/Suggestions/)).toBeInTheDocument();
    expect(screen.getByText(/2 pending/)).toBeInTheDocument();
  });

  it("shows version history button", () => {
    render(<DraftingStep {...defaultProps} />);

    expect(screen.getByText("v1.0")).toBeInTheDocument();
  });

  it("disables approve button when suggestions are pending", () => {
    render(<DraftingStep {...defaultProps} />);

    const approveButton = screen.getByText(/Resolve 2 suggestions first/);
    expect(approveButton).toBeDisabled();
  });

  it("enables approve button when all suggestions resolved", () => {
    const propsWithResolvedSuggestions = {
      ...defaultProps,
      suggestions: [
        { ...defaultProps.suggestions[0], status: "accepted" },
        { ...defaultProps.suggestions[1], status: "declined" },
      ],
    };

    render(<DraftingStep {...propsWithResolvedSuggestions} />);

    const approveButton = screen.getByText("Approve Draft & Continue");
    expect(approveButton).not.toBeDisabled();
  });

  it("shows approved state", () => {
    render(<DraftingStep {...defaultProps} draftApproved={true} />);

    expect(screen.getByText("Draft Approved!")).toBeInTheDocument();
  });
});

describe("SuggestionList", () => {
  const mockSuggestions = [
    {
      id: "sug_1",
      location: "summary",
      originalText: "Old text",
      proposedText: "New text",
      rationale: "Better version",
      status: "pending" as const,
      createdAt: new Date().toISOString(),
    },
    {
      id: "sug_2",
      location: "experience.0",
      originalText: "Old experience",
      proposedText: "Better experience",
      rationale: "More impactful",
      status: "accepted" as const,
      createdAt: new Date().toISOString(),
      resolvedAt: new Date().toISOString(),
    },
  ];

  it("renders pending suggestions", () => {
    render(
      <SuggestionList
        suggestions={mockSuggestions}
        onAccept={vi.fn()}
        onDecline={vi.fn()}
      />
    );

    expect(screen.getByText("Pending (1)")).toBeInTheDocument();
  });

  it("shows resolved suggestions when toggled", () => {
    render(
      <SuggestionList
        suggestions={mockSuggestions}
        onAccept={vi.fn()}
        onDecline={vi.fn()}
        showResolved={true}
      />
    );

    expect(screen.getByText("Resolved (1)")).toBeInTheDocument();
  });

  it("calls onAccept when accept button clicked", async () => {
    const onAccept = vi.fn().mockResolvedValue(undefined);

    render(
      <SuggestionList
        suggestions={mockSuggestions}
        onAccept={onAccept}
        onDecline={vi.fn()}
      />
    );

    const acceptButton = screen.getByTestId("accept-button");
    fireEvent.click(acceptButton);

    await waitFor(() => {
      expect(onAccept).toHaveBeenCalledWith("sug_1");
    });
  });

  it("calls onDecline when decline button clicked", async () => {
    const onDecline = vi.fn().mockResolvedValue(undefined);

    render(
      <SuggestionList
        suggestions={mockSuggestions}
        onAccept={vi.fn()}
        onDecline={onDecline}
      />
    );

    const declineButton = screen.getByTestId("decline-button");
    fireEvent.click(declineButton);

    await waitFor(() => {
      expect(onDecline).toHaveBeenCalledWith("sug_1");
    });
  });

  it("shows all resolved message", () => {
    const allResolved = mockSuggestions.map((s) => ({
      ...s,
      status: "accepted" as const,
    }));

    render(
      <SuggestionList
        suggestions={allResolved}
        onAccept={vi.fn()}
        onDecline={vi.fn()}
      />
    );

    expect(screen.getByText("All suggestions resolved!")).toBeInTheDocument();
  });
});

describe("VersionHistory", () => {
  const mockVersions = [
    {
      version: "1.0",
      htmlContent: "<h1>Test</h1>",
      trigger: "initial" as const,
      description: "Initial draft",
      changeLog: [],
      createdAt: new Date().toISOString(),
    },
    {
      version: "1.1",
      htmlContent: "<h1>Test Updated</h1>",
      trigger: "accept" as const,
      description: "Accepted suggestion",
      changeLog: [],
      createdAt: new Date().toISOString(),
    },
  ];

  it("renders version indicator", () => {
    render(
      <VersionHistory
        versions={mockVersions}
        currentVersion="1.1"
        onRestore={vi.fn()}
      />
    );

    expect(screen.getByText("v1.1")).toBeInTheDocument();
  });

  it("opens version history dropdown", () => {
    render(
      <VersionHistory
        versions={mockVersions}
        currentVersion="1.1"
        onRestore={vi.fn()}
      />
    );

    const toggleButton = screen.getByTestId("version-history-toggle");
    fireEvent.click(toggleButton);

    expect(screen.getByText("Version History")).toBeInTheDocument();
    expect(screen.getByText("Last 5 versions saved")).toBeInTheDocument();
  });

  it("shows restore button for non-current versions", () => {
    render(
      <VersionHistory
        versions={mockVersions}
        currentVersion="1.1"
        onRestore={vi.fn()}
      />
    );

    const toggleButton = screen.getByTestId("version-history-toggle");
    fireEvent.click(toggleButton);

    // Should show restore button for v1.0 but not for v1.1 (current)
    expect(screen.getByTestId("restore-button-1.0")).toBeInTheDocument();
    expect(screen.queryByTestId("restore-button-1.1")).not.toBeInTheDocument();
  });

  it("calls onRestore when restore button clicked", async () => {
    const onRestore = vi.fn().mockResolvedValue(undefined);

    render(
      <VersionHistory
        versions={mockVersions}
        currentVersion="1.1"
        onRestore={onRestore}
      />
    );

    const toggleButton = screen.getByTestId("version-history-toggle");
    fireEvent.click(toggleButton);

    const restoreButton = screen.getByTestId("restore-button-1.0");
    fireEvent.click(restoreButton);

    await waitFor(() => {
      expect(onRestore).toHaveBeenCalledWith("1.0");
    });
  });
});
