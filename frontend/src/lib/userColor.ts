const PASTEL_PALETTE = [
  "#bbf7d0", // pastel green
  "#bfdbfe", // pastel blue
  "#fde68a", // pastel amber
  "#fecaca", // pastel red
  "#ddd6fe", // pastel violet
  "#99f6e4", // pastel teal
  "#fbcfe8", // pastel pink
  "#c7d2fe", // pastel indigo
];

export function userColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  const index = Math.abs(hash) % PASTEL_PALETTE.length;
  return PASTEL_PALETTE[index];
}
