import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EventStatusBadge } from "./EventStatusBadge";
import type { DanceEventStatus } from "@/api/types";

describe("EventStatusBadge", () => {
  it.each<[DanceEventStatus, string]>([
    ["unscheduled", "unscheduled"],
    ["partially_scheduled", "partially scheduled"],
    ["scheduled", "scheduled"],
  ])("renders the human-readable label for status=%s", (status, expectedText) => {
    render(<EventStatusBadge status={status} />);
    expect(screen.getByText(expectedText)).toBeInTheDocument();
  });
});
