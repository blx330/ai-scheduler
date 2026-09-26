import { describe, expect, it } from "vitest";

import { exceedsMoveThreshold, pointerDay, snapStartMinute, weekFlipDirection } from "./dragGeometry";

describe("pointerDay", () => {
  it("maps x positions across the grid to columns 0..6", () => {
    expect(pointerDay(100, 100, 700)).toBe(0);
    expect(pointerDay(199, 100, 700)).toBe(0);
    expect(pointerDay(200, 100, 700)).toBe(1);
    expect(pointerDay(799, 100, 700)).toBe(6);
  });

  it("clamps pointers outside the grid to the edge columns", () => {
    expect(pointerDay(-50, 100, 700)).toBe(0);
    expect(pointerDay(5000, 100, 700)).toBe(6);
  });

  it("tolerates a zero-width grid", () => {
    expect(pointerDay(10, 0, 0)).toBe(0);
  });
});

describe("snapStartMinute", () => {
  it("snaps to 15-minute steps", () => {
    expect(snapStartMinute(9 * 60 + 7, 60, 0, 1440)).toBe(9 * 60);
    expect(snapStartMinute(9 * 60 + 8, 60, 0, 1440)).toBe(9 * 60 + 15);
  });

  it("keeps the whole block inside the day", () => {
    expect(snapStartMinute(23 * 60 + 30, 90, 0, 1440)).toBe(1440 - 90);
    expect(snapStartMinute(-30, 60, 0, 1440)).toBe(0);
  });
});

describe("weekFlipDirection", () => {
  it("flips to the previous week in the left edge zone and past it", () => {
    expect(weekFlipDirection(110, 100, 900)).toBe(-1);
    expect(weekFlipDirection(20, 100, 900)).toBe(-1);
  });

  it("flips to the next week in the right edge zone and past it", () => {
    expect(weekFlipDirection(890, 100, 900)).toBe(1);
    expect(weekFlipDirection(1500, 100, 900)).toBe(1);
  });

  it("does nothing in the middle", () => {
    expect(weekFlipDirection(500, 100, 900)).toBeNull();
  });
});

describe("exceedsMoveThreshold", () => {
  it("treats a jitter of a few pixels as a click", () => {
    expect(exceedsMoveThreshold(3, -4)).toBe(false);
    expect(exceedsMoveThreshold(0, 6)).toBe(true);
  });
});
