/**
 * Pure geometry for dragging blocks around the week grid. Positions are derived
 * from where the pointer *is*, not from how far it has moved, so the same maths
 * keeps working after the visible week flips underneath a drag in progress.
 */

export const DRAG_SNAP_MINUTES = 15;
/** How close to the grid's left/right edge the pointer must be to flip the week. */
export const WEEK_FLIP_EDGE_PX = 28;
/** How long the pointer must dwell in an edge zone before the week flips. */
export const WEEK_FLIP_DWELL_MS = 550;

export type WeekFlipDirection = -1 | 1;

/** Column index (0-6) under a pointer x position, clamped to the grid. */
export function pointerDay(clientX: number, gridLeft: number, gridWidth: number): number {
  if (gridWidth <= 0) return 0;
  const raw = Math.floor(((clientX - gridLeft) / gridWidth) * 7);
  return Math.max(0, Math.min(6, raw));
}

/** Snap a minute-of-day to the drag grid and keep the whole block inside the day. */
export function snapStartMinute(startMin: number, durationMin: number, dayStartMin: number, dayEndMin: number): number {
  const snapped = Math.round(startMin / DRAG_SNAP_MINUTES) * DRAG_SNAP_MINUTES;
  return Math.max(dayStartMin, Math.min(dayEndMin - durationMin, snapped));
}

/**
 * -1 / +1 when the pointer sits in (or past) the left / right edge zone of the
 * viewport rectangle, null otherwise. Uses the *visible* container, not the grid:
 * the grid can be wider than what is on screen.
 */
export function weekFlipDirection(
  clientX: number,
  viewportLeft: number,
  viewportRight: number,
  edgePx = WEEK_FLIP_EDGE_PX,
): WeekFlipDirection | null {
  if (clientX <= viewportLeft + edgePx) return -1;
  if (clientX >= viewportRight - edgePx) return 1;
  return null;
}

export function exceedsMoveThreshold(dx: number, dy: number, thresholdPx = 5): boolean {
  return Math.abs(dx) > thresholdPx || Math.abs(dy) > thresholdPx;
}
