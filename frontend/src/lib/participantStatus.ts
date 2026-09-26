import type { PlanningParticipantStatus, UserRead } from "@/api/types";

/** Plain-English cause for an unavailable participant, matching the backend's reason codes. */
export function describeUnavailability(status: PlanningParticipantStatus): string {
  switch (status.reason) {
    case "booked":
      return status.detail ? `already booked for ${status.detail}` : "already booked for another practice";
    case "busy":
      return "busy on their calendar";
    case "not_declared":
      return "hasn't declared availability at this time";
    default:
      return "unavailable";
  }
}

export interface MissingParticipant {
  userId: string;
  name: string;
  role: PlanningParticipantStatus["role"];
  why: string;
}

/** Unavailable participants with names and causes, required first, for dialogs and tooltips. */
export function missingParticipants(
  statuses: PlanningParticipantStatus[],
  usersById: Map<string, Pick<UserRead, "display_name">>,
): MissingParticipant[] {
  return statuses
    .filter((status) => !status.available)
    .sort((a, b) => (a.role === b.role ? 0 : a.role === "required" ? -1 : 1))
    .map((status) => ({
      userId: status.user_id,
      name: usersById.get(status.user_id)?.display_name ?? "Unknown member",
      role: status.role,
      why: describeUnavailability(status),
    }));
}
