import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreateEventDialog } from "@/components/events/CreateEventDialog";
import { EventStatusBadge } from "@/components/events/EventStatusBadge";
import { useEvents } from "@/hooks/use-events";

export function EventsPage() {
  const { data: events, isLoading, isError } = useEvents();
  const navigate = useNavigate();

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Events</h2>
          <p className="text-sm text-muted-foreground">Dances that need practice sessions scheduled.</p>
        </div>
        <CreateEventDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All events</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-sm text-muted-foreground">Loading events...</p>}
          {isError && <p className="text-sm text-destructive">Failed to load events.</p>}
          {events && events.length === 0 && (
            <p className="text-sm text-muted-foreground">No events yet. Create one to get started.</p>
          )}
          {events && events.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Sessions</TableHead>
                  <TableHead>Deadline</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((eventItem) => (
                  <TableRow
                    key={eventItem.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/events/${eventItem.id}`)}
                  >
                    <TableCell className="font-medium">{eventItem.name}</TableCell>
                    <TableCell>
                      <EventStatusBadge status={eventItem.status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {eventItem.confirmed_session_count}/{eventItem.required_session_count} confirmed
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(eventItem.latest_schedule_at).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </TableCell>
                    <TableCell>
                      <ChevronRight className="size-4 text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
