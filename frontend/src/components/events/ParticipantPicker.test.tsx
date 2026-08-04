import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ParticipantPicker } from "./ParticipantPicker";
import type { UserRead } from "@/api/types";

function makeUser(overrides: Partial<UserRead>): UserRead {
  return {
    id: "u1",
    display_name: "Alice",
    timezone: "America/New_York",
    email: null,
    preferred_practice_time: null,
    preferred_practice_time_raw: null,
    preferred_practice_time_parsed: null,
    preferred_practice_time_summary: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("ParticipantPicker", () => {
  it("prompts to add members when there are none yet", () => {
    render(<ParticipantPicker users={[]} value={{}} onChange={vi.fn()} />);
    expect(screen.getByText(/add members first/i)).toBeInTheDocument();
  });

  it("lists every user with their current selection", () => {
    const users = [makeUser({ id: "u1", display_name: "Alice" }), makeUser({ id: "u2", display_name: "Bob" })];
    render(<ParticipantPicker users={users} value={{ u1: "required" }} onChange={vi.fn()} />);

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
    // u1 is explicitly "required"; u2 has no entry and defaults to "Not involved".
    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.getByText("Not involved")).toBeInTheDocument();
  });
});
