import { hashIndex } from "@/lib/hash";

const PALETTE = [
  "#22c55e",
  "#3b82f6",
  "#f59e0b",
  "#ef5b34",
  "#8b5cf6",
  "#14b8a6",
  "#ec4899",
  "#4f5bd4",
];

export function eventColor(id: string): string {
  return PALETTE[hashIndex(id, PALETTE.length)];
}
