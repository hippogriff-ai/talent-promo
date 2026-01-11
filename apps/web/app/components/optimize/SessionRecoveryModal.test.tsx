import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SessionRecoveryModal from "./SessionRecoveryModal";
import { WorkflowSession } from "../../hooks/useWorkflowSession";

describe("SessionRecoveryModal", () => {
  const createMockSession = (
    overrides: Partial<WorkflowSession> = {}
  ): WorkflowSession => ({
    sessionId: "linkedin.com/in/user||job.com/posting",
    linkedinUrl: "linkedin.com/in/user",
    jobUrl: "job.com/posting",
    threadId: "thread-123",
    stages: {
      research: "completed",
      discovery: "active",
      drafting: "locked",
      export: "locked",
    },
    currentStage: "discovery",
    researchComplete: true,
    discoveryConfirmed: false,
    draftApproved: false,
    exportComplete: false,
    lastError: null,
    errorStage: null,
    startedAt: new Date().toISOString(),
    updatedAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
    ...overrides,
  });

  describe("Session Recovery Prompt", () => {
    it("GIVEN user returns, WHEN existing session found, THEN shows recovery modal", () => {
      const session = createMockSession();
      const onResume = vi.fn();
      const onStartFresh = vi.fn();

      render(
        <SessionRecoveryModal
          session={session}
          onResume={onResume}
          onStartFresh={onStartFresh}
        />
      );

      expect(screen.getByText("Welcome Back!")).toBeInTheDocument();
      expect(screen.getByText(/We found an existing session/)).toBeInTheDocument();
    });

    it("shows current stage", () => {
      const session = createMockSession();

      render(
        <SessionRecoveryModal
          session={session}
          onResume={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      // The heading "Current Stage" should be in the document
      expect(screen.getByText("Current Stage")).toBeInTheDocument();
      // Discovery should appear in the stage list
      expect(screen.getAllByText("Discovery").length).toBeGreaterThan(0);
    });

    it("shows progress percentage", () => {
      const session = createMockSession();

      render(
        <SessionRecoveryModal
          session={session}
          onResume={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      // 1 of 4 stages complete = 25%
      expect(screen.getByText("25%")).toBeInTheDocument();
    });

    it("shows stage breakdown with completion status", () => {
      const session = createMockSession({
        researchComplete: true,
        discoveryConfirmed: true,
        stages: {
          research: "completed",
          discovery: "completed",
          drafting: "active",
          export: "locked",
        },
        currentStage: "drafting",
      });

      render(
        <SessionRecoveryModal
          session={session}
          onResume={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByText("50%")).toBeInTheDocument();
    });

    it("shows error state if session has error", () => {
      const session = createMockSession({
        lastError: "API connection failed",
        errorStage: "discovery",
      });

      render(
        <SessionRecoveryModal
          session={session}
          onResume={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByText("Previous session had an error")).toBeInTheDocument();
      expect(screen.getByText("API connection failed")).toBeInTheDocument();
    });
  });

  describe("User Actions", () => {
    it("clicking Resume Session calls onResume", () => {
      const onResume = vi.fn();
      const session = createMockSession();

      render(
        <SessionRecoveryModal
          session={session}
          onResume={onResume}
          onStartFresh={vi.fn()}
        />
      );

      fireEvent.click(screen.getByText("Resume Session"));

      expect(onResume).toHaveBeenCalled();
    });

    it("clicking Start Fresh calls onStartFresh", () => {
      const onStartFresh = vi.fn();
      const session = createMockSession();

      render(
        <SessionRecoveryModal
          session={session}
          onResume={vi.fn()}
          onStartFresh={onStartFresh}
        />
      );

      fireEvent.click(screen.getByText("Start Fresh"));

      expect(onStartFresh).toHaveBeenCalled();
    });
  });

  describe("Time Display", () => {
    it("shows time ago for recent sessions", () => {
      const session = createMockSession({
        updatedAt: new Date(Date.now() - 60000).toISOString(), // 1 minute ago
      });

      render(
        <SessionRecoveryModal
          session={session}
          onResume={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByText(/1 minute ago/)).toBeInTheDocument();
    });

    it("shows hours for older sessions", () => {
      const session = createMockSession({
        updatedAt: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
      });

      render(
        <SessionRecoveryModal
          session={session}
          onResume={vi.fn()}
          onStartFresh={vi.fn()}
        />
      );

      expect(screen.getByText(/2 hours ago/)).toBeInTheDocument();
    });
  });
});
