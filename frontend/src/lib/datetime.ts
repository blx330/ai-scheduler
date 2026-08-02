import { fromZonedTime, toZonedTime, formatInTimeZone } from "date-fns-tz";

export function localPartsToIso(dateStr: string, timeStr: string, timeZone: string): string {
  const naive = `${dateStr}T${timeStr}:00`;
  return fromZonedTime(naive, timeZone).toISOString();
}

export function isoToZonedParts(iso: string, timeZone: string): { date: string; time: string } {
  const zoned = toZonedTime(iso, timeZone);
  return {
    date: formatInTimeZone(zoned, timeZone, "yyyy-MM-dd"),
    time: formatInTimeZone(zoned, timeZone, "HH:mm"),
  };
}

export function formatTimeRange(startIso: string, endIso: string, timeZone?: string): string {
  if (timeZone) {
    const day = formatInTimeZone(startIso, timeZone, "EEE MMM d");
    const start = formatInTimeZone(startIso, timeZone, "h:mm a");
    const end = formatInTimeZone(endIso, timeZone, "h:mm a zzz");
    return `${day}, ${start} - ${end}`;
  }
  const start = new Date(startIso);
  const end = new Date(endIso);
  const day = start.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const startTime = start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const endTime = end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${day}, ${startTime} - ${endTime}`;
}
