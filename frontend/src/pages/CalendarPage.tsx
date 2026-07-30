import { useMemo, useState } from "react";
import { addDays, addWeeks, endOfWeek, format, isSameDay, startOfWeek, subWeeks } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCalendarOverview } from "@/hooks/use-calendar";
import { useEvents } from "@/hooks/use-events";
import { useUsers } from "@/hooks/use-users";

export function CalendarPage() {
  const [anchor, setAnchor] = useState(() => new Date());
  const { data: users } = useUsers();
  const { data: events } = useEvents();

  const weekStart = useMemo(() => startOfWeek(anchor, { weekStartsOn: 1 }), [anchor]);
  const weekEnd = useMemo(() => endOfWeek(anchor, { weekStartsOn: 1 }), [anchor]);
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);

  const { data: overview, isLoading } = useCalendarOverview(weekStart.toISOString(), weekEnd.toISOString());

  const usersById = useMemo(() => new Map((users ?? []).map((u) => [u.id, u.display_name])), [users]);
  const eventsById = useMemo(() => new Map((events ?? []).map((e) => [e.id, e.name])), [events]);

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Calendar</h2>
          <p className="text-sm text-muted-foreground">
            {format(weekStart, "MMM d")} &ndash; {format(weekEnd, "MMM d, yyyy")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => setAnchor((prev) => subWeeks(prev, 1))}>
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setAnchor(new Date())}>
            Today
          </Button>
          <Button variant="outline" size="icon" onClick={() => setAnchor((prev) => addWeeks(prev, 1))}>
            <ChevronRight />
          </Button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading calendar...</p>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {days.map((day) => {
          const busyForDay = (overview?.busy_intervals ?? []).filter((interval) =>
            isSameDay(new Date(interval.start_at), day),
          );
          const sessionsForDay = (overview?.practice_sessions ?? []).filter((session) =>
            isSameDay(new Date(session.start_at), day),
          );
          const isToday = isSameDay(day, new Date());

          return (
            <Card key={day.toISOString()} className={isToday ? "border-primary" : undefined}>
              <CardHeader>
                <CardTitle className="text-sm">{format(day, "EEEE, MMM d")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {sessionsForDay.length === 0 && busyForDay.length === 0 && (
                  <p className="text-xs text-muted-foreground">Nothing scheduled.</p>
                )}
                {sessionsForDay
                  .slice()
                  .sort((a, b) => a.start_at.localeCompare(b.start_at))
                  .map((session) => (
                    <div key={session.id} className="rounded-md border border-primary/40 bg-primary/5 p-2 text-xs">
                      <p className="font-medium">
                        {eventsById.get(session.dance_event_id) ?? "Practice session"}
                      </p>
                      <p className="text-muted-foreground">
                        {format(new Date(session.start_at), "h:mm a")} &ndash;{" "}
                        {format(new Date(session.end_at), "h:mm a")}
                      </p>
                      <Badge variant="secondary" className="mt-1">
                        {session.status}
                      </Badge>
                    </div>
                  ))}
                {busyForDay
                  .slice()
                  .sort((a, b) => a.start_at.localeCompare(b.start_at))
                  .map((interval) => (
                    <div key={interval.id} className="rounded-md border p-2 text-xs">
                      <p className="font-medium">{usersById.get(interval.user_id) ?? "Busy"}</p>
                      <p className="text-muted-foreground">
                        {format(new Date(interval.start_at), "h:mm a")} &ndash;{" "}
                        {format(new Date(interval.end_at), "h:mm a")}
                      </p>
                    </div>
                  ))}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
