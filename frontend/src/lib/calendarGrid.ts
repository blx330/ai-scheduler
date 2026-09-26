import { addDays, format } from "date-fns";

export const DAY_START_MIN = 0;
export const DAY_END_MIN = 24 * 60;
export const PX_PER_MIN = 72 / 60;
export const NUM_HOURS = (DAY_END_MIN - DAY_START_MIN) / 60;

// The grid's day columns are built from the viewer's clock, so every conversion
// between a grid coordinate and an instant has to use the same zone.
export const GRID_TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

export function minutesToHHMM(mins: number): string {
  const clamped = ((mins % 1440) + 1440) % 1440;
  const h = Math.floor(clamped / 60);
  const m = clamped % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function addMinutesToDateTime(dateStr: string, minutesOfDay: number): { date: string; time: string } {
  if (minutesOfDay < 1440) return { date: dateStr, time: minutesToHHMM(minutesOfDay) };
  const rolledDate = format(addDays(new Date(`${dateStr}T00:00:00`), Math.floor(minutesOfDay / 1440)), "yyyy-MM-dd");
  return { date: rolledDate, time: minutesToHHMM(minutesOfDay) };
}

/**
 * Never ask the planner for slots that have already passed. The viewed week starts on
 * Monday, so from Friday onward an unclamped horizon happily proposed (and let you
 * confirm) sessions earlier in the same week.
 */
export function planningHorizonStart(weekStart: Date): Date {
  const now = new Date();
  return weekStart.getTime() < now.getTime() ? now : weekStart;
}

export function fmtHourLabel(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const m = mins % 60;
  const hh = h % 12 === 0 ? 12 : h % 12;
  const period = h < 12 ? "AM" : "PM";
  return m === 0 ? `${hh} ${period}` : `${hh}:${String(m).padStart(2, "0")} ${period}`;
}

/**
 * Place an instant on the grid, in the same timezone the day columns are built in.
 *
 * Columns come from `startOfWeek(new Date())`, i.e. the viewer's timezone, so
 * placement must use it too. Computing the date in the *organizer's* timezone
 * instead meant a block could resolve to a date absent from the column list and be
 * dropped with no indication -- routine whenever organizer and viewer differ.
 */
export function gridPlacement(iso: string, dayDateStrings: string[]): { day: number; startMin: number } | null {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return null;
  const day = dayDateStrings.indexOf(format(instant, "yyyy-MM-dd"));
  if (day === -1) return null;
  const startMin = Math.max(DAY_START_MIN, Math.min(DAY_END_MIN - 1, instant.getHours() * 60 + instant.getMinutes()));
  return { day, startMin };
}

/** Truncate a block so it never draws past the bottom (midnight) edge of the grid. */
export function clampDurationToDay(startMin: number, durationMin: number): number {
  return Math.max(0, Math.min(durationMin, DAY_END_MIN - startMin));
}

export interface LaneInput {
  day: number;
  startMin: number;
  durationMin: number;
}

/**
 * Split concurrent blocks on the same day into side-by-side lanes.
 *
 * Lane count is computed per *cluster* of mutually-overlapping blocks, not per day:
 * a lone 9 AM block keeps the full column width even if three blocks collide at
 * 5 PM. Within a cluster, blocks are placed first-fit in start order, which for
 * intervals uses exactly max-concurrency lanes. Blocks that only touch (end == start)
 * do not overlap.
 */
export function assignLanes<T extends LaneInput>(blocks: readonly T[]): Array<T & { lane: number; laneCount: number }> {
  const byDay = new Map<number, T[]>();
  for (const block of blocks) {
    const list = byDay.get(block.day);
    if (list) list.push(block);
    else byDay.set(block.day, [block]);
  }

  const out: Array<T & { lane: number; laneCount: number }> = [];
  for (const dayBlocks of byDay.values()) {
    dayBlocks.sort((a, b) => a.startMin - b.startMin);

    let cluster: Array<T & { lane: number }> = [];
    let laneEndMin: number[] = [];
    let clusterEndMin = Number.NEGATIVE_INFINITY;

    const flush = () => {
      for (const block of cluster) out.push({ ...block, laneCount: laneEndMin.length });
      cluster = [];
      laneEndMin = [];
    };

    for (const block of dayBlocks) {
      if (block.startMin >= clusterEndMin) flush();
      const endMin = block.startMin + block.durationMin;
      let lane = laneEndMin.findIndex((end) => end <= block.startMin);
      if (lane === -1) {
        lane = laneEndMin.length;
        laneEndMin.push(endMin);
      } else {
        laneEndMin[lane] = endMin;
      }
      cluster.push({ ...block, lane });
      clusterEndMin = Math.max(clusterEndMin, endMin);
    }
    flush();
  }
  return out;
}
