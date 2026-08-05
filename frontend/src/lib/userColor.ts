import { hashIndex } from "@/lib/hash";

const PASTEL_PALETTE = [
  "#bbf7d0", // pastel green
  "#bfdbfe", // pastel blue
  "#fde68a", // pastel amber
  "#fecaca", // pastel red
  "#ddd6fe", // pastel violet
  "#99f6e4", // pastel teal
  "#fbcfe8", // pastel pink
  "#c7d2fe", // pastel indigo
  "#fed7aa", // pastel orange
  "#d9f99d", // pastel lime
  "#a5f3fc", // pastel cyan
  "#fecdd3", // pastel rose
];

export function userColor(id: string): string {
  return PASTEL_PALETTE[hashIndex(id, PASTEL_PALETTE.length)];
}

/**
 * Assigns every id a color, guaranteed unique up to PASTEL_PALETTE.length ids.
 * Each id keeps its `userColor` slot when possible so colors stay stable as the
 * roster changes; only ids that collide on the same slot get bumped to the next
 * free one, walked in sorted-id order for a deterministic tie-break.
 */
export function buildMemberColorMap(userIds: string[]): Map<string, string> {
  const sorted = [...userIds].sort();
  const takenSlots = new Set<number>();
  const map = new Map<string, string>();

  for (const id of sorted) {
    let slot = hashIndex(id, PASTEL_PALETTE.length);
    if (takenSlots.size < PASTEL_PALETTE.length) {
      while (takenSlots.has(slot)) {
        slot = (slot + 1) % PASTEL_PALETTE.length;
      }
      takenSlots.add(slot);
    }
    map.set(id, PASTEL_PALETTE[slot]);
  }

  return map;
}
