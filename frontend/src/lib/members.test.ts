import { describe, expect, it } from "vitest";

import { DEFAULT_VISIBLE_MEMBER_LIMIT, initialVisibleMemberIds } from "./members";

describe("initialVisibleMemberIds", () => {
  it("shows every member when the roster is small", () => {
    expect([...initialVisibleMemberIds(["a", "b"])]).toEqual(["a", "b"]);
  });

  it("caps a large roster at the default limit, keeping roster order", () => {
    const ids = Array.from({ length: 10 }, (_, i) => `m${i}`);
    const visible = [...initialVisibleMemberIds(ids)];
    expect(visible).toHaveLength(DEFAULT_VISIBLE_MEMBER_LIMIT);
    expect(visible).toEqual(ids.slice(0, DEFAULT_VISIBLE_MEMBER_LIMIT));
  });

  it("treats a non-positive limit as nobody visible", () => {
    expect(initialVisibleMemberIds(["a"], 0).size).toBe(0);
  });
});
