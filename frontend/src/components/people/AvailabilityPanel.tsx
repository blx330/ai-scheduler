import { useState, type FormEvent } from "react";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAvailability, useCreateAvailability, useDeleteAvailability } from "@/hooks/use-availability";
import { localPartsToIso } from "@/lib/datetime";
import type { UserRead } from "@/api/types";

export function AvailabilityPanel({ user }: { user: UserRead }) {
  const { data: intervals, isLoading } = useAvailability(user.id);
  const createAvailability = useCreateAvailability(user.id);
  const deleteAvailability = useDeleteAvailability(user.id);

  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [startTime, setStartTime] = useState("18:00");
  const [endTime, setEndTime] = useState("20:00");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!date || !startTime || !endTime) return;
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
          <Button type="submit" disabled={createAvailability.isPending}>
            {createAvailability.isPending ? "Adding..." : "Add interval"}
          </Button>
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
                  <span>
                    {new Date(interval.start_at).toLocaleString(undefined, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}{" "}
                    &ndash;{" "}
                    {new Date(interval.end_at).toLocaleTimeString(undefined, { timeStyle: "short" })}
                  </span>
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
