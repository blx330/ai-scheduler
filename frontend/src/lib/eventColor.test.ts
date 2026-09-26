import { describe, expect, it } from "vitest";
import { buildEventColorMap, eventColor } from "./eventColor";

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

describe("buildEventColorMap", () => {
  it("assigns every event a color", () => {
    const ids = ["hip-hop", "contemporary", "jazz"];
    const map = buildEventColorMap(ids);
    expect(map.size).toBe(ids.length);
    for (const id of ids) expect(map.get(id)).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it("gives distinct colors up to the palette size even when ids hash to the same slot", () => {
    // Find two ids that collide under the plain hash so the test proves the bump.
    const base = "dance-0";
    let collider = "";
    for (let i = 1; i < 500 && !collider; i++) {
      const candidate = `dance-${i}`;
      if (eventColor(candidate) === eventColor(base)) collider = candidate;
    }
    expect(collider).not.toBe("");

    const map = buildEventColorMap([base, collider]);
    expect(map.get(base)).not.toBe(map.get(collider));
  });

  it("keeps an id on its plain-hash color when nothing collides", () => {
    const map = buildEventColorMap(["solo"]);
    expect(map.get("solo")).toBe(eventColor("solo"));
  });

  it("is deterministic regardless of input order", () => {
    const a = buildEventColorMap(["x", "y", "z"]);
    const b = buildEventColorMap(["z", "x", "y"]);
    for (const id of ["x", "y", "z"]) expect(b.get(id)).toBe(a.get(id));
  });
});
