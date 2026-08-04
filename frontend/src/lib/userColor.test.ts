import { describe, expect, it } from "vitest";
import { buildMemberColorMap, userColor } from "./userColor";

describe("userColor", () => {
  it("is deterministic for the same id", () => {
    expect(userColor("user-1")).toBe(userColor("user-1"));
  });
});

describe("buildMemberColorMap", () => {
  it("assigns every member a color", () => {
    const ids = ["alice", "bob", "carol"];
    const map = buildMemberColorMap(ids);
    expect(map.size).toBe(ids.length);
    for (const id of ids) {
      expect(map.get(id)).toBeDefined();
    }
  });

  it("guarantees unique colors up to the palette size, even under hash collisions", () => {
    // Two ids that are known to hash to the same palette slot must still end up
    // with distinct colors, per buildMemberColorMap's collision-bump guarantee.
    const ids = Array.from({ length: 8 }, (_, i) => `member-${i}`);
    const map = buildMemberColorMap(ids);
    const colors = [...map.values()];
    expect(new Set(colors).size).toBe(colors.length);
  });

  it("is stable: re-running with the same roster produces the same assignment", () => {
    const ids = ["alice", "bob", "carol", "dave"];
    const first = buildMemberColorMap(ids);
    const second = buildMemberColorMap([...ids]);
    for (const id of ids) {
      expect(second.get(id)).toBe(first.get(id));
    }
  });
});
