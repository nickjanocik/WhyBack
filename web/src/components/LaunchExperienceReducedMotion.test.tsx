/** Verifies that the stakeholder launch experience honors reduced-motion preferences. */

import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { LaunchExperience } from "./LaunchExperience";

vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return { ...actual, useReducedMotion: () => true };
});

it("removes launch transitions when reduced motion is requested", () => {
  render(
    <LaunchExperience
      view="welcome"
      collections={[]}
      collectionWarnings={[]}
      analysisReady
      analysisBlockedReason={null}
      onShowHistory={vi.fn()}
      onBack={vi.fn()}
      onSelectCollection={vi.fn()}
      onStartAnalysis={vi.fn()}
    />,
  );

  expect(
    screen.getByRole("region", { name: "Where would you like to begin?" }),
  ).toHaveAttribute("data-motion", "reduced");
  expect(screen.getAllByRole("button")).toHaveLength(2);
});
