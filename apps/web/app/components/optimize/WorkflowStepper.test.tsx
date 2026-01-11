import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import WorkflowStepper from "./WorkflowStepper";
import { StageStatus } from "../../hooks/useWorkflowSession";

describe("WorkflowStepper", () => {
  const defaultStages: Record<string, StageStatus> = {
    research: "active",
    discovery: "locked",
    drafting: "locked",
    export: "locked",
  };

  describe("Workflow Navigation", () => {
    it("GIVEN user on any stage, WHEN viewing UI, THEN stepper shows all 4 stages", () => {
      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
        />
      );

      expect(screen.getByText("Research")).toBeInTheDocument();
      expect(screen.getByText("Discovery")).toBeInTheDocument();
      expect(screen.getByText("Drafting")).toBeInTheDocument();
      expect(screen.getByText("Export")).toBeInTheDocument();
    });

    it("GIVEN current stage is Research, WHEN stepper displayed, THEN Research shows as active, others locked", () => {
      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
        />
      );

      const researchButton = screen.getByRole("button", { name: /Research/ });
      const discoveryButton = screen.getByRole("button", { name: /Discovery/ });

      expect(researchButton).toHaveClass("bg-blue-500");
      expect(discoveryButton).toHaveClass("bg-gray-200");
      expect(discoveryButton).toBeDisabled();
    });

    it("GIVEN stage complete, WHEN stepper displayed, THEN completed stage shows checkmark", () => {
      const stagesWithComplete: Record<string, StageStatus> = {
        research: "completed",
        discovery: "active",
        drafting: "locked",
        export: "locked",
      };

      render(
        <WorkflowStepper
          stages={stagesWithComplete}
          currentStage="discovery"
        />
      );

      const researchButton = screen.getByRole("button", { name: /Research/ });
      expect(researchButton).toHaveClass("bg-green-500");

      // Check for checkmark SVG
      const checkmark = researchButton.querySelector("svg");
      expect(checkmark).toBeInTheDocument();
    });
  });

  describe("Stage Transitions", () => {
    it("clicking on completed stage allows navigation", () => {
      const onStageClick = vi.fn();
      const stagesWithComplete: Record<string, StageStatus> = {
        research: "completed",
        discovery: "completed",
        drafting: "active",
        export: "locked",
      };

      render(
        <WorkflowStepper
          stages={stagesWithComplete}
          currentStage="drafting"
          onStageClick={onStageClick}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: /Research/ }));

      expect(onStageClick).toHaveBeenCalledWith("research");
    });

    it("clicking on locked stage does not trigger callback", () => {
      const onStageClick = vi.fn();

      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
          onStageClick={onStageClick}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: /Discovery/ }));

      expect(onStageClick).not.toHaveBeenCalled();
    });
  });

  describe("Stage Guards", () => {
    it("locked stages are disabled", () => {
      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
        />
      );

      const discoveryButton = screen.getByRole("button", { name: /Discovery/ });
      const draftingButton = screen.getByRole("button", { name: /Drafting/ });
      const exportButton = screen.getByRole("button", { name: /Export/ });

      expect(discoveryButton).toBeDisabled();
      expect(draftingButton).toBeDisabled();
      expect(exportButton).toBeDisabled();
    });

    it("locked stages show lock icon", () => {
      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
        />
      );

      const discoveryButton = screen.getByRole("button", { name: /Discovery/ });
      const lockIcon = discoveryButton.querySelector("svg");

      expect(lockIcon).toBeInTheDocument();
    });
  });

  describe("Error State", () => {
    it("error stage shows error styling", () => {
      const stagesWithError: Record<string, StageStatus> = {
        research: "completed",
        discovery: "error",
        drafting: "locked",
        export: "locked",
      };

      render(
        <WorkflowStepper
          stages={stagesWithError}
          currentStage="discovery"
        />
      );

      const discoveryButton = screen.getByRole("button", { name: /Discovery/ });
      expect(discoveryButton).toHaveClass("bg-red-500");
    });

    it("error stage is clickable for retry", () => {
      const onStageClick = vi.fn();
      const stagesWithError: Record<string, StageStatus> = {
        research: "completed",
        discovery: "error",
        drafting: "locked",
        export: "locked",
      };

      render(
        <WorkflowStepper
          stages={stagesWithError}
          currentStage="discovery"
          onStageClick={onStageClick}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: /Discovery/ }));

      expect(onStageClick).toHaveBeenCalledWith("discovery");
    });
  });

  describe("Accessibility", () => {
    it("has correct aria-label for each stage", () => {
      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
        />
      );

      expect(screen.getByRole("button", { name: /Research - active/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Discovery - locked/ })).toBeInTheDocument();
    });

    it("marks current step with aria-current", () => {
      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
        />
      );

      const researchButton = screen.getByRole("button", { name: /Research/ });
      expect(researchButton).toHaveAttribute("aria-current", "step");
    });

    it("has navigation landmark", () => {
      render(
        <WorkflowStepper
          stages={defaultStages}
          currentStage="research"
        />
      );

      expect(screen.getByRole("navigation", { name: /Workflow progress/ })).toBeInTheDocument();
    });
  });

  describe("Connector Lines", () => {
    it("completed stage connector is green", () => {
      const stagesWithComplete: Record<string, StageStatus> = {
        research: "completed",
        discovery: "active",
        drafting: "locked",
        export: "locked",
      };

      const { container } = render(
        <WorkflowStepper
          stages={stagesWithComplete}
          currentStage="discovery"
        />
      );

      const connectors = container.querySelectorAll(".h-1.rounded-full");
      expect(connectors[0]).toHaveClass("bg-green-500");
    });
  });
});
