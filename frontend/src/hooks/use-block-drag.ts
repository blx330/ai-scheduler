import { useEffect, useRef, useState, type RefObject } from "react";

import {
  WEEK_FLIP_DWELL_MS,
  exceedsMoveThreshold,
  pointerDay,
  snapStartMinute,
  weekFlipDirection,
  type WeekFlipDirection,
} from "@/lib/dragGeometry";

export type DragBlockKind = "suggested" | "confirmed";

export interface DragPreview {
  kind: DragBlockKind;
  id: string;
  day: number;
  startMin: number;
}

export interface DropResult {
  finalDay: number;
  finalStartMin: number;
  /** False for a click with no meaningful movement. */
  moved: boolean;
  /** Net weeks the visible calendar was flipped during the drag. */
  weeksShifted: number;
}

interface UseBlockDragOptions {
  gridRef: RefObject<HTMLDivElement | null>;
  /** The scrollable viewport around the grid; its edges are the week-flip zones. */
  viewportRef: RefObject<HTMLDivElement | null>;
  pxPerMin: number;
  dayStartMin: number;
  dayEndMin: number;
  /** Called when the pointer dwells at the left/right edge; the caller changes the week. */
  onWeekFlip?: (direction: WeekFlipDirection) => void;
  /** Called when a drag is abandoned with Escape (no drop happens). */
  onCancel?: () => void;
}

/**
 * Mouse drag for calendar blocks. The preview follows the pointer's column rather
 * than a delta from the grab point, so flipping the visible week mid-drag (dwell at
 * an edge) keeps the block under the cursor and the drop lands in the week that is
 * actually on screen.
 */
export function useBlockDrag({
  gridRef,
  viewportRef,
  pxPerMin,
  dayStartMin,
  dayEndMin,
  onWeekFlip,
  onCancel,
}: UseBlockDragOptions) {
  const [dragPreview, setDragPreview] = useState<DragPreview | null>(null);
  const detachDragRef = useRef<(() => void) | null>(null);
  const isDraggingRef = useRef(false);

  // Navigating away mid-drag would otherwise leave the window listeners attached and
  // have them call setState on an unmounted tree.
  useEffect(() => () => detachDragRef.current?.(), []);

  function beginBlockDrag(
    e: React.MouseEvent,
    kind: DragBlockKind,
    id: string,
    day: number,
    startMin: number,
    durationMin: number,
    onDrop: (result: DropResult) => void,
  ) {
    e.preventDefault();
    const grid = gridRef.current;
    const gridRect = grid?.getBoundingClientRect();
    const grabDay = gridRect ? pointerDay(e.clientX, gridRect.left, gridRect.width) : day;
    const drag = {
      startClientX: e.clientX,
      startClientY: e.clientY,
      origStartMin: startMin,
      // Column the block sits in relative to the column under the pointer, so a
      // block grabbed by its middle stays where it was grabbed.
      dayOffset: day - grabDay,
      durationMin,
      moved: false,
      finalDay: day,
      finalStartMin: startMin,
      weeksShifted: 0,
      edgeDirection: null as WeekFlipDirection | null,
      flipTimer: null as ReturnType<typeof setTimeout> | null,
    };
    isDraggingRef.current = true;
    setDragPreview({ kind, id, day, startMin });

    function clearFlipTimer() {
      if (drag.flipTimer !== null) clearTimeout(drag.flipTimer);
      drag.flipTimer = null;
    }

    function scheduleFlip(direction: WeekFlipDirection) {
      drag.flipTimer = setTimeout(() => {
        drag.weeksShifted += direction;
        drag.moved = true;
        onWeekFlip?.(direction);
        // Keep flipping while the pointer stays parked at the edge.
        scheduleFlip(direction);
      }, WEEK_FLIP_DWELL_MS);
    }

    function onMove(ev: MouseEvent) {
      const rect = gridRef.current?.getBoundingClientRect();
      if (!rect) return;
      if (exceedsMoveThreshold(ev.clientX - drag.startClientX, ev.clientY - drag.startClientY)) {
        drag.moved = true;
      }
      const newDay = Math.max(0, Math.min(6, pointerDay(ev.clientX, rect.left, rect.width) + drag.dayOffset));
      const rawStartMin = drag.origStartMin + (ev.clientY - drag.startClientY) / pxPerMin;
      const newStartMin = snapStartMinute(rawStartMin, drag.durationMin, dayStartMin, dayEndMin);
      drag.finalDay = newDay;
      drag.finalStartMin = newStartMin;
      setDragPreview({ kind, id, day: newDay, startMin: newStartMin });

      const viewport = viewportRef.current?.getBoundingClientRect();
      const direction = viewport && onWeekFlip ? weekFlipDirection(ev.clientX, viewport.left, viewport.right) : null;
      if (direction !== drag.edgeDirection) {
        clearFlipTimer();
        drag.edgeDirection = direction;
        if (direction !== null) scheduleFlip(direction);
      }
    }

    function onUp() {
      detach();
      onDrop({
        finalDay: drag.finalDay,
        finalStartMin: drag.finalStartMin,
        moved: drag.moved,
        weeksShifted: drag.weeksShifted,
      });
    }

    function onKeyDown(ev: KeyboardEvent) {
      if (ev.key !== "Escape") return;
      detach();
      setDragPreview(null);
      onCancel?.();
    }

    function detach() {
      clearFlipTimer();
      isDraggingRef.current = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("keydown", onKeyDown);
      detachDragRef.current = null;
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("keydown", onKeyDown);
    detachDragRef.current = detach;
  }

  return { dragPreview, setDragPreview, beginBlockDrag, isDraggingRef };
}
