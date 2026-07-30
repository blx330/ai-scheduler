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
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  const index = Math.abs(hash) % PALETTE.length;
  return PALETTE[index];
}
