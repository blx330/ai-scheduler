import { describe, expect, it } from "vitest";
import { formatTimeRange, isoToZonedParts, localPartsToIso } from "./datetime";

describe("localPartsToIso / isoToZonedParts", () => {
  it("round-trips date/time parts through a non-UTC timezone without drifting", () => {
    // Regression test for the double-offset bug described in isoToZonedParts:
    // converting local parts -> instant -> local parts must return the same
    // wall-clock values, not shift by (zone offset - browser offset).
    const iso = localPartsToIso("2026-03-15", "09:30", "America/New_York");
    const parts = isoToZonedParts(iso, "America/New_York");
    expect(parts).toEqual({ date: "2026-03-15", time: "09:30" });
  });

  it("produces different instants for the same wall-clock time in different zones", () => {
    const ny = localPartsToIso("2026-06-01", "12:00", "America/New_York");
    const la = localPartsToIso("2026-06-01", "12:00", "America/Los_Angeles");
    expect(ny).not.toEqual(la);
  });
});

describe("formatTimeRange", () => {
  it("formats a same-day range with an explicit timezone", () => {
    const startIso = localPartsToIso("2026-03-15", "09:00", "America/New_York");
    const endIso = localPartsToIso("2026-03-15", "10:30", "America/New_York");
    expect(formatTimeRange(startIso, endIso, "America/New_York")).toBe("Sun Mar 15, 9:00 AM - 10:30 AM EDT");
  });
});
