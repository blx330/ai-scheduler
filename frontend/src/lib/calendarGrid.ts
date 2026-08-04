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
