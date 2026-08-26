/** Verifies that review-sensitivity decoration honors reduced-motion preferences. */

import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import type { DemoCustomerLimits, LiveRunConfiguration } from "../types";
import { RunCliDialog } from "./RunCliDialog";

vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return { ...actual, useReducedMotion: () => true };
});

const customerLimits: DemoCustomerLimits = { minimum: 3, maximum: 24 };
const liveRun: LiveRunConfiguration = {
  backend: "gemini",
  model: "configured model",
  ready: true,
  blockedReason: null,
};

it("removes sensitivity transitions when reduced motion is requested", () => {
  render(
    <RunCliDialog
      open
      running={false}
      error={null}
      customerLimits={customerLimits}
      liveRun={liveRun}
      onClose={vi.fn()}
      onRun={vi.fn()}
    />,
  );

  expect(
    screen.getByRole("group", { name: "Review sensitivity" }),
  ).toHaveAttribute("data-motion", "reduced");
});
