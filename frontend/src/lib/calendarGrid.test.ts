import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DAY_END_MIN,
  addMinutesToDateTime,
  assignLanes,
  clampDurationToDay,
  gridPlacement,
  initialScrollMinute,
  planningHorizonStart,
} from "./calendarGrid";

// Mon 21 Sep 2026 .. Sun 27 Sep 2026, as CalendarPage builds them from the viewer's clock.
const WEEK = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"];

describe("gridPlacement", () => {
  it("places an in-week instant on its local day and minute", () => {
    // No trailing Z: parsed in the local zone, the same zone the day columns use.
    const iso = new Date("2026-09-23T18:30:00").toISOString();
    expect(gridPlacement(iso, WEEK)).toEqual({ day: 2, startMin: 18 * 60 + 30 });
  });

  it("returns null for an instant outside the viewed week", () => {
    const iso = new Date("2026-09-28T10:00:00").toISOString();
    expect(gridPlacement(iso, WEEK)).toBeNull();
  });

  it("returns null for an unparseable timestamp", () => {
    expect(gridPlacement("not-a-date", WEEK)).toBeNull();
  });
});

describe("clampDurationToDay", () => {
  it("leaves a block that ends before midnight alone", () => {
    expect(clampDurationToDay(18 * 60, 120)).toBe(120);
  });

  it("truncates a block that would run past the bottom of the grid", () => {
    expect(clampDurationToDay(23 * 60, 120)).toBe(60);
    expect(clampDurationToDay(23 * 60, 120) + 23 * 60).toBe(DAY_END_MIN);
  });

  it("never returns a negative duration", () => {
    expect(clampDurationToDay(DAY_END_MIN, 30)).toBe(0);
  });
});

describe("addMinutesToDateTime", () => {
  it("keeps the date for minutes within the day", () => {
    expect(addMinutesToDateTime("2026-09-27", 90)).toEqual({ date: "2026-09-27", time: "01:30" });
  });

  it("rolls over to the next date past 1440 minutes", () => {
    expect(addMinutesToDateTime("2026-09-27", 1500)).toEqual({ date: "2026-09-28", time: "01:00" });
  });

  it("rolls over across a month boundary", () => {
    expect(addMinutesToDateTime("2026-09-30", 1440 + 15)).toEqual({ date: "2026-10-01", time: "00:15" });
  });
});

describe("planningHorizonStart", () => {
  afterEach(() => vi.useRealTimers());

  it("clamps a week that already started to now", () => {
    const now = new Date("2026-09-24T15:00:00Z");
    vi.useFakeTimers();
    vi.setSystemTime(now);
    expect(planningHorizonStart(new Date("2026-09-21T00:00:00Z")).getTime()).toBe(now.getTime());
  });

  it("keeps a future week start as-is", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-24T15:00:00Z"));
    const nextWeek = new Date("2026-09-28T00:00:00Z");
    expect(planningHorizonStart(nextWeek)).toBe(nextWeek);
  });
});

describe("assignLanes", () => {
  const block = (key: string, day: number, startMin: number, durationMin: number) => ({ key, day, startMin, durationMin });

  it("gives non-overlapping blocks a single lane each", () => {
    const result = assignLanes([block("a", 0, 540, 60), block("b", 0, 600, 60), block("c", 1, 540, 60)]);
    for (const item of result) {
      expect(item.lane).toBe(0);
      expect(item.laneCount).toBe(1);
    }
  });

  it("sizes lanes per overlap cluster, not per day", () => {
    const result = assignLanes([
      block("morning", 0, 540, 60), // 9:00-10:00, alone
      block("e1", 0, 1020, 120), // 17:00-19:00
      block("e2", 0, 1050, 60), // 17:30-18:30
      block("e3", 0, 1080, 90), // 18:00-19:30
    ]);
    const byKey = new Map(result.map((item) => [item.key, item]));

    expect(byKey.get("morning")).toMatchObject({ lane: 0, laneCount: 1 });
    expect(byKey.get("e1")?.laneCount).toBe(3);
    expect(byKey.get("e2")?.laneCount).toBe(3);
    expect(byKey.get("e3")?.laneCount).toBe(3);
    expect(new Set([byKey.get("e1")?.lane, byKey.get("e2")?.lane, byKey.get("e3")?.lane]).size).toBe(3);
  });

  it("reuses a lane once the earlier block in it has ended", () => {
    // a: 9-10, b: 9:30-11, c: 10-10:30 -> c fits back into a's lane; cluster needs 2 lanes.
    const result = assignLanes([block("a", 0, 540, 60), block("b", 0, 570, 90), block("c", 0, 600, 30)]);
    const byKey = new Map(result.map((item) => [item.key, item]));
    expect(byKey.get("a")?.lane).toBe(0);
    expect(byKey.get("b")?.lane).toBe(1);
    expect(byKey.get("c")?.lane).toBe(0);
    for (const item of result) expect(item.laneCount).toBe(2);
  });

  it("treats blocks that merely touch as non-overlapping", () => {
    const result = assignLanes([block("a", 0, 540, 60), block("b", 0, 600, 60)]);
    for (const item of result) expect(item.laneCount).toBe(1);
  });

  it("preserves every input block and its fields", () => {
    const input = [block("a", 3, 100, 10), block("b", 3, 105, 10)];
    const result = assignLanes(input);
    expect(result).toHaveLength(2);
    expect(result.map((item) => item.key).sort()).toEqual(["a", "b"]);
    expect(result[0]).toMatchObject({ day: 3 });
  });
});

describe("initialScrollMinute", () => {
  it("defaults to 7 AM when the week has no practices", () => {
    expect(initialScrollMinute([])).toBe(7 * 60);
  });

  it("opens an hour before the earliest practice of the week", () => {
    expect(initialScrollMinute([20 * 60, 18 * 60 + 30, 21 * 60])).toBe(17 * 60 + 30);
  });

  it("never scrolls above 7 AM", () => {
    expect(initialScrollMinute([7 * 60 + 15])).toBe(7 * 60);
  });
});
