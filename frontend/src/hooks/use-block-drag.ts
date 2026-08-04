import { useEffect, useRef, useState } from "react";

const DRAG_MOVE_THRESHOLD_PX = 5;
const DRAG_SNAP_MINUTES = 15;

export type DragBlockKind = "suggested" | "confirmed";

export interface DragPreview {
  kind: DragBlockKind;
  id: string;
  day: number;
  startMin: number;
}

interface UseBlockDragOptions {
  gridRef: React.RefObject<HTMLDivElement | null>;
  pxPerMin: number;
  dayStartMin: number;
  dayEndMin: number;
}

export function useBlockDrag({ gridRef, pxPerMin, dayStartMin, dayEndMin }: UseBlockDragOptions) {
  const [dragPreview, setDragPreview] = useState<DragPreview | null>(null);
  const detachDragRef = useRef<(() => void) | null>(null);

  // Navigating away mid-drag would otherwise leave both window listeners attached and
  // have them call setState on an unmounted tree.
  useEffect(() => () => detachDragRef.current?.(), []);

  function beginBlockDrag(
    e: React.MouseEvent,
    kind: DragBlockKind,
    id: string,
    day: number,
    startMin: number,
    durationMin: number,
    onDrop: (finalDay: number, finalStartMin: number, moved: boolean) => void,
  ) {
    e.preventDefault();
    const drag = {
      startClientX: e.clientX,
      startClientY: e.clientY,
      origDay: day,
      origStartMin: startMin,
      durationMin,
      moved: false,
      finalDay: day,
      finalStartMin: startMin,
    };
    setDragPreview({ kind, id, day, startMin });

    function onMove(ev: MouseEvent) {
      const grid = gridRef.current;
      if (!grid) return;
      const rect = grid.getBoundingClientRect();
      const colWidth = rect.width / 7;
      const deltaDay = Math.round((ev.clientX - drag.startClientX) / colWidth);
      const deltaMin = Math.round((ev.clientY - drag.startClientY) / pxPerMin / DRAG_SNAP_MINUTES) * DRAG_SNAP_MINUTES;
      if (
        Math.abs(ev.clientX - drag.startClientX) > DRAG_MOVE_THRESHOLD_PX ||
        Math.abs(ev.clientY - drag.startClientY) > DRAG_MOVE_THRESHOLD_PX
      ) {
        drag.moved = true;
      }
      const newDay = Math.max(0, Math.min(6, drag.origDay + deltaDay));
      const newStartMin = Math.max(dayStartMin, Math.min(dayEndMin - drag.durationMin, drag.origStartMin + deltaMin));
      drag.finalDay = newDay;
      drag.finalStartMin = newStartMin;
      setDragPreview({ kind, id, day: newDay, startMin: newStartMin });
    }

    function onUp() {
      detach();
      onDrop(drag.finalDay, drag.finalStartMin, drag.moved);
    }

    function detach() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      detachDragRef.current = null;
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    detachDragRef.current = detach;
  }

  return { dragPreview, setDragPreview, beginBlockDrag };
}
