/** Deterministic string hash used to assign stable palette slots to ids. */
export function hashIndex(id: string, paletteLength: number): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % paletteLength;
}
