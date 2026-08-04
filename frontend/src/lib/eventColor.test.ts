import { describe, expect, it } from "vitest";
import { eventColor } from "./eventColor";

describe("eventColor", () => {
  it("is deterministic for the same id", () => {
    expect(eventColor("dance-1")).toBe(eventColor("dance-1"));
  });

  it("returns a valid hex color for arbitrary ids, including empty string", () => {
    for (const id of ["", "a", "dance-1", "11111111-1111-1111-1111-111111111111"]) {
      expect(eventColor(id)).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
