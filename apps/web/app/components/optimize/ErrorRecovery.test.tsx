import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorRecovery from "./ErrorRecovery";
import { WorkflowStage } from "../../hooks/useWorkflowSession";

describe("ErrorRecovery", () => {
  describe("Error Display", () => {
    it("GIVEN error occurs, WHEN error displayed, THEN shows error message", () => {
      render(
        <ErrorRecovery
          error="Failed to connect to API"
          errorStage="discovery"
          completedStages={["research"]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByText("Something went wrong")).toBeInTheDocument();
      expect(screen.getByText("Failed to connect to API")).toBeInTheDocument();
    });

    it("shows which stage the error occurred in", () => {
      render(
        <ErrorRecovery
          error="Drafting failed"
          errorStage="drafting"
          completedStages={["research", "discovery"]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByText(/Error occurred during: Drafting/)).toBeInTheDocument();
    });

    it("GIVEN unrecoverable error, WHEN displayed, THEN shows Start Fresh option", () => {
      render(
        <ErrorRecovery
          error="Cannot recover from this error"
          errorStage="research"
          completedStages={[]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByRole("button", { name: "Start Fresh" })).toBeInTheDocument();
    });
  });

  describe("Preserving Progress", () => {
    it("GIVEN error with completed stages, WHEN displayed, THEN shows preserved progress", () => {
      render(
        <ErrorRecovery
          error="Export failed"
          errorStage="export"
          completedStages={["research", "discovery", "drafting"]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByText("Your progress is preserved")).toBeInTheDocument();
      expect(screen.getByText("Research")).toBeInTheDocument();
      expect(screen.getByText("Discovery")).toBeInTheDocument();
      expect(screen.getByText("Drafting")).toBeInTheDocument();
    });

    it("GIVEN no completed stages, WHEN displayed, THEN does not show preserved progress", () => {
      render(
        <ErrorRecovery
          error="Research failed"
          errorStage="research"
          completedStages={[]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.queryByText("Your progress is preserved")).not.toBeInTheDocument();
    });
  });

  describe("Recovery Actions", () => {
    it("GIVEN error displayed, WHEN user clicks Retry, THEN calls onRetry", () => {
      const onRetry = vi.fn();

      render(
        <ErrorRecovery
          error="Temporary failure"
          errorStage="discovery"
          completedStages={["research"]}
          onRetry={onRetry}
          onStartFresh={vi.fn()}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: "Retry" }));

      expect(onRetry).toHaveBeenCalled();
    });

    it("GIVEN error displayed, WHEN user clicks Start Fresh, THEN calls onStartFresh", () => {
      const onStartFresh = vi.fn();

      render(
        <ErrorRecovery
          error="Unrecoverable error"
          errorStage="discovery"
          completedStages={["research"]}
          onRetry={vi.fn()}
          onStartFresh={onStartFresh}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: "Start Fresh" }));

      expect(onStartFresh).toHaveBeenCalled();
    });
  });

  describe("Recovery Options Explanation", () => {
    it("shows Retry option explanation", () => {
      render(
        <ErrorRecovery
          error="API timeout"
          errorStage="discovery"
          completedStages={["research"]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
      expect(
        screen.getByText("Attempt to resume from where the error occurred")
      ).toBeInTheDocument();
    });

    it("shows Start Fresh option explanation with completed stages context", () => {
      render(
        <ErrorRecovery
          error="Drafting crashed"
          errorStage="drafting"
          completedStages={["research", "discovery"]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(
        screen.getByText(/Reset Drafting and try again/)
      ).toBeInTheDocument();
    });

    it("shows different Start Fresh text when no stages completed", () => {
      render(
        <ErrorRecovery
          error="Research failed"
          errorStage="research"
          completedStages={[]}
          onRetry={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(
        screen.getByText("Start the workflow from the beginning")
      ).toBeInTheDocument();
    });
  });
});
