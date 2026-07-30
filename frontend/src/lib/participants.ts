import type { ParticipantSelection } from "@/components/events/ParticipantPicker";

export function hasRequiredParticipant(selection: Record<string, ParticipantSelection>): boolean {
  return Object.values(selection).some((role) => role === "required");
}
