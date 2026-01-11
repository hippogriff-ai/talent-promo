import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import StartNewSessionDialog from "./StartNewSessionDialog";

describe("StartNewSessionDialog", () => {
  describe("Confirmation Dialog", () => {
    it("GIVEN user clicks Start New, WHEN dialog shown, THEN prompts for confirmation", () => {
      render(
        <StartNewSessionDialog
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      );

      expect(screen.getByText("Start New Application?")).toBeInTheDocument();
    });

    it("shows warning about data loss", () => {
      render(
        <StartNewSessionDialog
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      );

      expect(
        screen.getByText(/This will clear all data from your current session/)
      ).toBeInTheDocument();
    });

    it("lists what will be cleared", () => {
      render(
        <StartNewSessionDialog
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      );

      expect(
        screen.getByText(/Research data \(profile, job, company analysis\)/)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Discovery conversation and experiences/)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/All resume drafts and version history/)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Export settings and ATS reports/)
      ).toBeInTheDocument();
    });
  });

  describe("User Actions", () => {
    it("GIVEN user confirms, WHEN Start Fresh clicked, THEN calls onConfirm", () => {
      const onConfirm = vi.fn();

      render(
        <StartNewSessionDialog
          onConfirm={onConfirm}
          onCancel={vi.fn()}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: "Start Fresh" }));

      expect(onConfirm).toHaveBeenCalled();
    });

    it("GIVEN user cancels, WHEN Cancel clicked, THEN calls onCancel", () => {
      const onCancel = vi.fn();

      render(
        <StartNewSessionDialog
          onConfirm={vi.fn()}
          onCancel={onCancel}
        />
      );

      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe("Visual Elements", () => {
    it("shows warning icon", () => {
      const { container } = render(
        <StartNewSessionDialog
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      );

      const warningIcon = container.querySelector("svg.text-amber-500");
      expect(warningIcon).toBeInTheDocument();
    });

    it("has modal overlay", () => {
      const { container } = render(
        <StartNewSessionDialog
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      );

      const overlay = container.querySelector(".fixed.inset-0.bg-black");
      expect(overlay).toBeInTheDocument();
    });
  });
});
