import { assignPaletteSlots, hashIndex } from "@/lib/hash";

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

/** Every member gets a distinct pastel (up to the palette size); see assignPaletteSlots. */
export function buildMemberColorMap(userIds: readonly string[]): Map<string, string> {
  return assignPaletteSlots(userIds, PASTEL_PALETTE);
}
