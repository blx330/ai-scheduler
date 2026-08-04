import type { CSSProperties, MouseEvent, ReactNode } from "react";

import { DAY_START_MIN, PX_PER_MIN } from "@/lib/calendarGrid";

interface CalendarBlockProps {
  day: number;
  startMin: number;
  durationMin: number;
  lane?: number;
  laneCount?: number;
  title?: string;
  onMouseDown?: (e: MouseEvent) => void;
  style?: CSSProperties;
  children: ReactNode;
}

/**
 * Absolutely-positions a block on the week grid from (day, startMin, durationMin),
 * optionally split into side-by-side lanes for overlapping blocks on the same day.
 * Shared by the busy/confirmed/suggested block loops in WeekGrid, which only differ
 * in their `style` and `children`.
 */
export function CalendarBlock({
  day,
  startMin,
  durationMin,
  lane = 0,
  laneCount = 1,
  title,
  onMouseDown,
  style,
  children,
}: CalendarBlockProps) {
  const top = (startMin - DAY_START_MIN) * PX_PER_MIN;
  const height = durationMin * PX_PER_MIN;
  const dayWidthPct = 100 / 7;
  const laneWidthPct = dayWidthPct / laneCount;
  const left = day * dayWidthPct + lane * laneWidthPct;

  return (
    <div
      title={title}
      onMouseDown={onMouseDown}
      style={{
        position: "absolute",
        top,
        height,
        left: `calc(${left}% + 3px)`,
        width: `calc(${laneWidthPct}% - 6px)`,
        boxSizing: "border-box",
        overflow: "hidden",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
