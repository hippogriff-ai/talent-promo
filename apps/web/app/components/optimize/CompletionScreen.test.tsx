import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CompletionScreen from "./CompletionScreen";

describe("CompletionScreen", () => {
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

  describe("LinkedIn Status", () => {
    it("shows LinkedIn ready indicator when optimized", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
          linkedinOptimized={true}
        />
      );

      expect(screen.getByText("LinkedIn Ready")).toBeInTheDocument();
    });

    it("does not show LinkedIn indicator when not optimized", () => {
      render(
        <CompletionScreen
          downloads={mockDownloads}
          onStartNew={vi.fn()}
          linkedinOptimized={false}
        />
      );

      expect(screen.queryByText("LinkedIn Ready")).not.toBeInTheDocument();
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
