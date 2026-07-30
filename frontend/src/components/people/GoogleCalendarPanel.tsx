import { useEffect, useState } from "react";
import { CalendarPlus, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useGoogleCalendars,
  useGoogleConnection,
  useSelectGoogleCalendars,
  useStartGoogleAuth,
  useSyncBusyTime,
} from "@/hooks/use-google-calendar";
import type { UserRead } from "@/api/types";

export function GoogleCalendarPanel({ user }: { user: UserRead }) {
  const { data: connection, isLoading } = useGoogleConnection(user.id);
  const startAuth = useStartGoogleAuth();
  const syncBusy = useSyncBusyTime(user.id);
  const selectCalendars = useSelectGoogleCalendars(user.id);
  const { data: calendars } = useGoogleCalendars(user.id, Boolean(connection?.connected));

  const [busyIds, setBusyIds] = useState<string[]>([]);
  const [writeId, setWriteId] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (connection) {
      setBusyIds(connection.selected_busy_calendar_ids);
      setWriteId(connection.selected_write_calendar_id ?? undefined);
    }
  }, [connection]);

  function toggleBusy(id: string, checked: boolean) {
    setBusyIds((prev) => (checked ? [...prev, id] : prev.filter((existing) => existing !== id)));
  }

  function handleSaveSelection() {
    selectCalendars.mutate({ busy_calendar_ids: busyIds, write_calendar_id: writeId });
  }

  function handleSync() {
    const now = new Date();
    const horizonEnd = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
    syncBusy.mutate({ horizon_start: now.toISOString(), horizon_end: horizonEnd.toISOString() });
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Google Calendar</CardTitle>
        {connection && (
          <Badge variant={connection.connected ? "success" : "outline"}>
            {connection.connected ? connection.account_email ?? "Connected" : connection.status}
          </Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <p className="text-sm text-muted-foreground">Checking connection...</p>}

        {!isLoading && !connection?.connected && (
          <Button onClick={() => startAuth.mutate(user.id)} disabled={startAuth.isPending}>
            <CalendarPlus /> Connect Google Calendar
          </Button>
        )}

        {connection?.connected && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => startAuth.mutate(user.id)}>
                Reconnect
              </Button>
              <Button size="sm" onClick={handleSync} disabled={syncBusy.isPending}>
                <RefreshCw className="size-4" />
                {syncBusy.isPending ? "Syncing..." : "Sync busy time (next 30 days)"}
              </Button>
            </div>

            {calendars && calendars.length > 0 && (
              <div className="space-y-3">
                <div>
                  <p className="mb-2 text-sm font-medium">Busy-source calendars</p>
                  <div className="space-y-2">
                    {calendars.map((calendar) => (
                      <div key={calendar.id} className="flex items-center gap-2">
                        <Checkbox
                          id={`cal-${calendar.id}`}
                          checked={busyIds.includes(calendar.id)}
                          onCheckedChange={(checked) => toggleBusy(calendar.id, checked === true)}
                        />
                        <Label htmlFor={`cal-${calendar.id}`} className="font-normal">
                          {calendar.summary}
                          {calendar.primary && <span className="text-muted-foreground"> (primary)</span>}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="write-calendar">Write calendar (for confirmed sessions)</Label>
                  <p className="text-xs text-muted-foreground">
                    Only takes effect when {user.display_name} organizes the event whose session gets confirmed
                    &mdash; sessions are always written to the organizer's calendar, never a participant's.
                  </p>
                  <Select value={writeId} onValueChange={setWriteId}>
                    <SelectTrigger id="write-calendar" className="w-full max-w-sm">
                      <SelectValue placeholder="Choose a calendar" />
                    </SelectTrigger>
                    <SelectContent>
                      {calendars.map((calendar) => (
                        <SelectItem key={calendar.id} value={calendar.id}>
                          {calendar.summary}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Button size="sm" onClick={handleSaveSelection} disabled={selectCalendars.isPending}>
                  {selectCalendars.isPending ? "Saving..." : "Save calendar selection"}
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
