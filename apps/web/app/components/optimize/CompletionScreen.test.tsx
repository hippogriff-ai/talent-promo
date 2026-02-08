import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CompletionScreen from "./CompletionScreen";

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("CompletionScreen", () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  const mockDownloads = [
    { format: "pdf", label: "Resume (PDF)", url: "/api/download/pdf" },
    { format: "docx", label: "Resume (Word)", url: "/api/download/docx" },
    { format: "txt", label: "Resume (Plain Text)", url: "/api/download/txt" },
    { format: "json", label: "Data Export (JSON)", url: "/api/download/json" },
  ];

  describe("Workflow Complete State", () => {
    it("GIVEN Export complete, THEN shows success message", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      expect(screen.getByText("Resume Optimization Complete!")).toBeInTheDocument();
      expect(
        screen.getByText("Your tailored resume is ready for download")
      ).toBeInTheDocument();
    });

    it("shows all download links", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      expect(screen.getByText("Resume (PDF)")).toBeInTheDocument();
      expect(screen.getByText("Resume (Word)")).toBeInTheDocument();
      expect(screen.getByText("Resume (Plain Text)")).toBeInTheDocument();
      expect(screen.getByText("Data Export (JSON)")).toBeInTheDocument();
    });

    it("download links have correct URLs", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      const pdfLink = screen.getByText("Resume (PDF)").closest("a");
      expect(pdfLink).toHaveAttribute("href", "/api/download/pdf");
    });
  });

  describe("ATS Score Display", () => {
    it("shows ATS score when provided", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
          atsScore={85}
        />
      );

      expect(screen.getByText("85%")).toBeInTheDocument();
      expect(screen.getByText("ATS Compatibility")).toBeInTheDocument();
    });

    it("does not show ATS section when score not provided", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      expect(screen.queryByText("ATS Compatibility")).not.toBeInTheDocument();
    });
  });

  describe("Next Steps", () => {
    it("shows next steps guidance", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      expect(screen.getByText("Next Steps")).toBeInTheDocument();
      expect(
        screen.getByText(/Download your resume in PDF format/)
      ).toBeInTheDocument();
    });
  });

  describe("New Session", () => {
    it("GIVEN workflow complete, WHEN Start New clicked, THEN calls onStartNew", () => {
      const onStartNew = vi.fn();

      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={onStartNew}
        />
      );

      fireEvent.click(screen.getByText("Start New Application"));

      expect(onStartNew).toHaveBeenCalled();
    });

    it("shows prompt for new application", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      expect(
        screen.getByText("Ready to optimize for another job?")
      ).toBeInTheDocument();
    });
  });

  describe("Go Back to Edit", () => {
    it("shows Edit Resume button when onGoBackToEdit is provided", () => {
      const onGoBackToEdit = vi.fn();

      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
          onGoBackToEdit={onGoBackToEdit}
        />
      );

      const editButton = screen.getByTestId("go-back-to-edit");
      expect(editButton).toBeInTheDocument();
      expect(editButton).toHaveTextContent("Edit Resume");
    });

    it("does not show Edit Resume button when onGoBackToEdit is not provided", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      expect(screen.queryByTestId("go-back-to-edit")).not.toBeInTheDocument();
    });

    it("calls onGoBackToEdit when button is clicked", () => {
      const onGoBackToEdit = vi.fn();

      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
          onGoBackToEdit={onGoBackToEdit}
        />
      );

      fireEvent.click(screen.getByTestId("go-back-to-edit"));
      expect(onGoBackToEdit).toHaveBeenCalledTimes(1);
    });
  });

  describe("File Type Icons", () => {
    it("renders correct file type indicators", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
        />
      );

      // Check for the format labels in download links
      expect(screen.getByText("Resume (PDF)")).toBeInTheDocument();
      expect(screen.getByText("Resume (Word)")).toBeInTheDocument();
      expect(screen.getByText("Resume (Plain Text)")).toBeInTheDocument();
      expect(screen.getByText("Data Export (JSON)")).toBeInTheDocument();
    });
  });
});
