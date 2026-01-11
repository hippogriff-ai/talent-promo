import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GapAnalysisDisplay from "./GapAnalysisDisplay";

const mockGapAnalysis = {
  strengths: ["5+ years Python experience", "AWS certified"],
  gaps: ["No Kubernetes experience", "Limited TypeScript"],
  gaps_detailed: [
    {
      description: "No Kubernetes experience",
      requirement_id: "req_1",
      requirement_text: "Experience with Kubernetes",
      priority: 1,
    },
  ],
  opportunities: [
    {
      description: "Docker experience may transfer",
      related_gaps: ["No Kubernetes experience"],
      potential_impact: "high",
    },
  ],
  recommended_emphasis: ["Python expertise"],
  transferable_skills: ["Container basics"],
  keywords_to_include: ["Kubernetes"],
  potential_concerns: [],
};

describe("GapAnalysisDisplay", () => {
  describe("Gap Display", () => {
    it("displays gaps array", () => {
      render(<GapAnalysisDisplay gapAnalysis={mockGapAnalysis} />);

      expect(
        screen.getByText("No Kubernetes experience")
      ).toBeInTheDocument();
    });

    it("links gaps to job requirements when gaps_detailed present", () => {
      render(<GapAnalysisDisplay gapAnalysis={mockGapAnalysis} />);

      expect(
        screen.getByText(/Experience with Kubernetes/i)
      ).toBeInTheDocument();
    });
  });

  describe("Strengths Display", () => {
    it("displays strengths array", () => {
      render(<GapAnalysisDisplay gapAnalysis={mockGapAnalysis} />);

      expect(
        screen.getByText("5+ years Python experience")
      ).toBeInTheDocument();
      expect(screen.getByText("AWS certified")).toBeInTheDocument();
    });
  });

  describe("Opportunities Display", () => {
    it("displays opportunities array", () => {
      render(<GapAnalysisDisplay gapAnalysis={mockGapAnalysis} />);

      expect(
        screen.getByText("Docker experience may transfer")
      ).toBeInTheDocument();
    });

    it("shows potential impact badge", () => {
      render(<GapAnalysisDisplay gapAnalysis={mockGapAnalysis} />);

      expect(screen.getByText("high impact")).toBeInTheDocument();
    });
  });

  describe("Compact Mode", () => {
    it("shows compact view when compact=true", () => {
      render(<GapAnalysisDisplay gapAnalysis={mockGapAnalysis} compact />);

      // Compact mode should show limited items
      expect(
        screen.getByText("5+ years Python experience")
      ).toBeInTheDocument();
    });
  });

  describe("Empty States", () => {
    it("handles empty gaps", () => {
      const emptyGaps = {
        ...mockGapAnalysis,
        gaps: [],
        gaps_detailed: [],
      };

      render(<GapAnalysisDisplay gapAnalysis={emptyGaps} />);

      expect(
        screen.getByText(/No gaps identified/i)
      ).toBeInTheDocument();
    });

    it("handles empty opportunities", () => {
      const emptyOpps = {
        ...mockGapAnalysis,
        opportunities: [],
      };

      render(<GapAnalysisDisplay gapAnalysis={emptyOpps} />);

      expect(
        screen.getByText(/Discovery will help find opportunities/i)
      ).toBeInTheDocument();
    });
  });
});
