import { describe, expect, it } from "vitest";

import { describeUnavailability, missingParticipants } from "./participantStatus";
import type { PlanningParticipantStatus } from "@/api/types";

const users = new Map([
  ["u1", { display_name: "Jordan Rivera" }],
  ["u2", { display_name: "Maya Chen" }],
]);

describe("describeUnavailability", () => {
  it("names the practice someone is already booked for", () => {
    expect(
      describeUnavailability({ user_id: "u1", role: "required", available: false, reason: "booked", detail: "Hip Hop Set session 2" }),
    ).toBe("already booked for Hip Hop Set session 2");
  });

  it("distinguishes a calendar conflict from never having declared free time", () => {
    expect(describeUnavailability({ user_id: "u1", role: "required", available: false, reason: "busy", detail: null })).toBe(
      "busy on their calendar",
    );
    expect(
      describeUnavailability({ user_id: "u1", role: "required", available: false, reason: "not_declared", detail: null }),
    ).toBe("hasn't declared availability at this time");
  });
});

describe("missingParticipants", () => {
  it("lists only unavailable people, required first, with names", () => {
    const statuses: PlanningParticipantStatus[] = [
      { user_id: "u2", role: "optional", available: false, reason: "busy", detail: null },
      { user_id: "u1", role: "required", available: false, reason: "not_declared", detail: null },
      { user_id: "u3", role: "required", available: true, reason: null, detail: null },
    ];
    expect(missingParticipants(statuses, users)).toEqual([
      { userId: "u1", name: "Jordan Rivera", role: "required", why: "hasn't declared availability at this time" },
      { userId: "u2", name: "Maya Chen", role: "optional", why: "busy on their calendar" },
    ]);
  });
});
