import { useState, type FormEvent } from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useEvents } from "@/hooks/use-events";
import { dateOnlyToIsoEndOfDay, dateOnlyToIsoStartOfDay } from "@/lib/datetime";
import { guessLocalTimezone } from "@/lib/timezones";
import type { PlanningRunCreate } from "@/api/types";

function defaultDate(offsetDays: number): string {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

export function RunPlanningForm({
  onRun,
  isPending,
}: {
  onRun: (body: PlanningRunCreate) => void;
  isPending: boolean;
}) {
  const { data: events } = useEvents();
  const eligibleEvents = (events ?? []).filter(
    (event) => event.status === "unscheduled" || event.status === "partially_scheduled",
  );
  const [selectedEventIds, setSelectedEventIds] = useState<string[]>([]);
  const [horizonStart, setHorizonStart] = useState(defaultDate(0));
  const [horizonEnd, setHorizonEnd] = useState(defaultDate(21));

  function toggleEvent(id: string, checked: boolean) {
    setSelectedEventIds((prev) => (checked ? [...prev, id] : prev.filter((existing) => existing !== id)));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (selectedEventIds.length === 0) return;
    const tz = guessLocalTimezone();
    onRun({
      event_ids: selectedEventIds,
      horizon_start: dateOnlyToIsoStartOfDay(horizonStart, tz),
      horizon_end: dateOnlyToIsoEndOfDay(horizonEnd, tz),
      slot_step_minutes: 60,
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Run planning</CardTitle>
        <p className="text-xs text-muted-foreground">
          Pick events that still need sessions and a date horizon to search for candidate slots.
        </p>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label>Events</Label>
            {eligibleEvents.length === 0 && (
              <p className="text-sm text-muted-foreground">No unscheduled or partially scheduled events.</p>
            )}
            <div className="space-y-2 rounded-md border p-3">
              {eligibleEvents.map((eventItem) => (
                <div key={eventItem.id} className="flex items-center gap-2">
                  <Checkbox
                    id={`plan-event-${eventItem.id}`}
                    checked={selectedEventIds.includes(eventItem.id)}
                    onCheckedChange={(checked) => toggleEvent(eventItem.id, checked === true)}
                  />
                  <Label htmlFor={`plan-event-${eventItem.id}`} className="font-normal">
                    {eventItem.name}{" "}
                    <span className="text-xs text-muted-foreground">
                      ({eventItem.remaining_session_count} session(s) remaining)
                    </span>
                  </Label>
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="horizon-start">Horizon start</Label>
              <Input
                id="horizon-start"
                type="date"
                value={horizonStart}
                onChange={(e) => setHorizonStart(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="horizon-end">Horizon end</Label>
              <Input id="horizon-end" type="date" value={horizonEnd} onChange={(e) => setHorizonEnd(e.target.value)} />
            </div>
          </div>
          <Button type="submit" disabled={isPending || selectedEventIds.length === 0}>
            <Sparkles /> {isPending ? "Planning..." : "Run planning"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
