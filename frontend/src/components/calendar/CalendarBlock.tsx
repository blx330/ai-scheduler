import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { DAY_START_MIN, PX_PER_MIN } from "@/lib/calendarGrid";
import { cn } from "@/lib/utils";

interface CalendarBlockProps extends Omit<ComponentPropsWithoutRef<"div">, "children"> {
  day: number;
  startMin: number;
  durationMin: number;
  lane?: number;
  laneCount?: number;
  children: ReactNode;
}

/**
 * Absolutely-positions a block on the week grid from (day, startMin, durationMin),
 * optionally split into side-by-side lanes for overlapping blocks on the same day.
 * Shared by the busy/confirmed/suggested block loops in WeekGrid, which only differ
 * in their `style`, `children` and interaction props (all forwarded to the div).
 */
export function CalendarBlock({
  day,
  startMin,
  durationMin,
  lane = 0,
  laneCount = 1,
  className,
  style,
  children,
  ...rest
}: CalendarBlockProps) {
  const top = (startMin - DAY_START_MIN) * PX_PER_MIN;
  const height = durationMin * PX_PER_MIN;
  const dayWidthPct = 100 / 7;
  const laneWidthPct = dayWidthPct / laneCount;
  const left = day * dayWidthPct + lane * laneWidthPct;

  return (
    <div
      {...rest}
      className={cn("focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1", className)}
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
