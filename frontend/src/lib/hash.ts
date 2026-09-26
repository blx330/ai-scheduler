/** Deterministic string hash used to assign stable palette slots to ids. */
export function hashIndex(id: string, paletteLength: number): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % paletteLength;
}

/**
 * Assigns every id a palette color, guaranteed unique up to palette.length ids.
 * Each id keeps its plain `hashIndex` slot when possible so colors stay stable as
 * the list changes; only ids that collide on the same slot get bumped to the next
 * free one, walked in sorted-id order for a deterministic tie-break.
 */
export function assignPaletteSlots(ids: readonly string[], palette: readonly string[]): Map<string, string> {
  const sorted = [...ids].sort();
  const takenSlots = new Set<number>();
  const map = new Map<string, string>();

  for (const id of sorted) {
    let slot = hashIndex(id, palette.length);
    if (takenSlots.size < palette.length) {
      while (takenSlots.has(slot)) {
        slot = (slot + 1) % palette.length;
      }
      takenSlots.add(slot);
    }
    map.set(id, palette[slot]);
  }

  return map;
}
