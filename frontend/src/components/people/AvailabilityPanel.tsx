import { useState, type FormEvent } from "react";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAvailability, useCreateAvailability, useDeleteAvailability } from "@/hooks/use-availability";
import { formatInTimeZone } from "date-fns-tz";

import { formatTimeRange, localPartsToIso } from "@/lib/datetime";
import type { UserRead } from "@/api/types";

export function AvailabilityPanel({ user }: { user: UserRead }) {
  const { data: intervals, isLoading } = useAvailability(user.id);
  const createAvailability = useCreateAvailability(user.id);
  const deleteAvailability = useDeleteAvailability(user.id);

  // The entered date is interpreted in the member's timezone, so the default must be
  // today *there*. toISOString() is UTC, which pre-filled tomorrow's date for anyone
  // west of UTC after their local evening.
  const today = formatInTimeZone(new Date(), user.timezone, "yyyy-MM-dd");
  const [date, setDate] = useState(today);
  const [startTime, setStartTime] = useState("18:00");
  const [endTime, setEndTime] = useState("20:00");

  const rangeValid = Boolean(startTime && endTime && endTime > startTime);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!date || !rangeValid) return;
    const start_at = localPartsToIso(date, startTime, user.timezone);
    const end_at = localPartsToIso(date, endTime, user.timezone);
    createAvailability.mutate({ start_at, end_at });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Manual availability</CardTitle>
        <p className="text-xs text-muted-foreground">
          Explicit free-time windows, entered in {user.display_name}'s timezone ({user.timezone}).
        </p>
        <p className="text-xs text-muted-foreground">
          With no manual availability, {user.display_name.split(" ")[0]} is treated as fully unavailable for
          scheduling &mdash; unless their Google Calendar is connected <em>and</em> busy time has been synced,
          in which case the synced window counts as free apart from the busy blocks in it.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="flex flex-wrap items-end gap-3" onSubmit={handleSubmit}>
          <div className="space-y-1">
            <Label htmlFor="avail-date">Date</Label>
            <Input id="avail-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </div>
          <div className="space-y-1">
            <Label htmlFor="avail-start">Start</Label>
            <Input
              id="avail-start"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="avail-end">End</Label>
            <Input id="avail-end" type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} required />
          </div>
          <Button type="submit" disabled={createAvailability.isPending || !rangeValid}>
            {createAvailability.isPending ? "Adding..." : "Add interval"}
          </Button>
          {!rangeValid && startTime && endTime && (
            <p className="w-full text-xs text-destructive">End time must be after start time.</p>
          )}
        </form>

        {isLoading && <p className="text-sm text-muted-foreground">Loading availability...</p>}
        {intervals && intervals.length === 0 && (
          <p className="text-sm text-muted-foreground">No manual availability yet.</p>
        )}
        {intervals && intervals.length > 0 && (
          <ul className="divide-y rounded-md border">
            {intervals
              .slice()
              .sort((a, b) => a.start_at.localeCompare(b.start_at))
              .map((interval) => (
                <li key={interval.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  {/* rendered in the member's timezone, matching the label above and
                      the timezone these values were entered in */}
                  <span>{formatTimeRange(interval.start_at, interval.end_at, user.timezone)}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteAvailability.mutate(interval.id)}
                    disabled={deleteAvailability.isPending}
                    aria-label="Delete interval"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </li>
              ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
