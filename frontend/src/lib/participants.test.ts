import { describe, expect, it } from "vitest";
import { hasRequiredParticipant } from "./participants";

describe("hasRequiredParticipant", () => {
  it("is false when there are no participants", () => {
    expect(hasRequiredParticipant({})).toBe(false);
  });

  it("is false when every participant is optional or none", () => {
    expect(hasRequiredParticipant({ u1: "optional", u2: "none" })).toBe(false);
  });

  it("is true when at least one participant is required", () => {
    expect(hasRequiredParticipant({ u1: "optional", u2: "required" })).toBe(true);
  });
});
