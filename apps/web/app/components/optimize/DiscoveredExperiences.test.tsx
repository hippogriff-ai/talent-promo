import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DiscoveredExperiences from "./DiscoveredExperiences";

describe("DiscoveredExperiences", () => {
  const mockExperiences = [
    {
      id: "exp-1",
      description: "Led Docker migration for 15 microservices",
      sourceQuote: "I led our Docker migration last year",
      mappedRequirements: ["Container experience", "Technical leadership"],
      discoveredAt: "2024-01-01T12:00:00.000Z",
    },
    {
      id: "exp-2",
      description: "Built CI/CD pipeline from scratch",
      sourceQuote: "I set up our entire deployment system",
      mappedRequirements: ["CI/CD experience"],
      discoveredAt: "2024-01-01T12:30:00.000Z",
    },
  ];

  describe("Experience Display", () => {
    it("displays experience description", () => {
      render(<DiscoveredExperiences experiences={mockExperiences} />);

      expect(
        screen.getByText("Led Docker migration for 15 microservices")
      ).toBeInTheDocument();
    });

    it("displays source quote from conversation", () => {
      render(<DiscoveredExperiences experiences={mockExperiences} />);

      expect(
        screen.getByText(/"I led our Docker migration last year"/i)
      ).toBeInTheDocument();
    });

    it("displays mapped requirements", () => {
      render(<DiscoveredExperiences experiences={mockExperiences} />);

      expect(screen.getByText("Container experience")).toBeInTheDocument();
      expect(screen.getByText("Technical leadership")).toBeInTheDocument();
    });

    it("shows count badge", () => {
      render(<DiscoveredExperiences experiences={mockExperiences} />);

      expect(screen.getByText("2 found")).toBeInTheDocument();
    });
  });

  describe("Empty State", () => {
    it("shows message when no experiences discovered", () => {
      render(<DiscoveredExperiences experiences={[]} />);

      expect(
        screen.getByText(/No experiences discovered yet/i)
      ).toBeInTheDocument();
    });
  });

  describe("Compact Mode", () => {
    it("limits displayed experiences in compact mode", () => {
      const manyExperiences = [
        ...mockExperiences,
        {
          id: "exp-3",
          description: "Third experience",
          sourceQuote: "Quote",
          mappedRequirements: [],
          discoveredAt: "2024-01-01",
        },
        {
          id: "exp-4",
          description: "Fourth experience",
          sourceQuote: "Quote",
          mappedRequirements: [],
          discoveredAt: "2024-01-01",
        },
      ];

      render(<DiscoveredExperiences experiences={manyExperiences} compact />);

      // Should show "+1 more" for compact mode with 4 experiences (shows 3)
      expect(screen.getByText("+1 more")).toBeInTheDocument();
    });

    it("truncates requirement text in compact mode", () => {
      const longReq = {
        id: "exp-1",
        description: "Experience",
        sourceQuote: "Quote",
        mappedRequirements: ["This is a very long requirement text that should be truncated"],
        discoveredAt: "2024-01-01",
      };

      render(<DiscoveredExperiences experiences={[longReq]} compact />);

      // Should truncate the requirement text
      expect(screen.getByText(/This is a very long.../i)).toBeInTheDocument();
    });
  });

  describe("Multiple Experiences", () => {
    it("displays all experiences", () => {
      render(<DiscoveredExperiences experiences={mockExperiences} />);

      expect(
        screen.getByText("Led Docker migration for 15 microservices")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Built CI/CD pipeline from scratch")
      ).toBeInTheDocument();
    });
  });

  describe("Footer Message", () => {
    it("shows integration message when experiences exist", () => {
      render(<DiscoveredExperiences experiences={mockExperiences} />);

      expect(
        screen.getByText(/incorporated into your optimized resume/i)
      ).toBeInTheDocument();
    });
  });
});
