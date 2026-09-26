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

describe("DST transition (America/New_York, 2026-11-01)", () => {
  it("round-trips a wall-clock time on the fall-back day without drifting", () => {
    const iso = localPartsToIso("2026-11-01", "09:00", "America/New_York");
    expect(isoToZonedParts(iso, "America/New_York")).toEqual({ date: "2026-11-01", time: "09:00" });
    expect(iso).toBe("2026-11-01T14:00:00.000Z"); // EST (-05:00) after the 2 AM fall-back
  });

  it("puts 25 real hours between 9 AM the day before and 9 AM on the fall-back day", () => {
    const before = new Date(localPartsToIso("2026-10-31", "09:00", "America/New_York"));
    const after = new Date(localPartsToIso("2026-11-01", "09:00", "America/New_York"));
    expect((after.getTime() - before.getTime()) / 3_600_000).toBe(25);
  });

  it("labels the offset change in formatted output", () => {
    const start = localPartsToIso("2026-10-31", "18:00", "America/New_York");
    const end = localPartsToIso("2026-10-31", "19:00", "America/New_York");
    expect(formatTimeRange(start, end, "America/New_York")).toBe("Sat Oct 31, 6:00 PM - 7:00 PM EDT");
    const start2 = localPartsToIso("2026-11-01", "18:00", "America/New_York");
    const end2 = localPartsToIso("2026-11-01", "19:00", "America/New_York");
    expect(formatTimeRange(start2, end2, "America/New_York")).toBe("Sun Nov 1, 6:00 PM - 7:00 PM EST");
  });
});
