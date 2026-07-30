import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CalendarX } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { EventStatusBadge } from "@/components/events/EventStatusBadge";
import { ParticipantPicker, type ParticipantSelection } from "@/components/events/ParticipantPicker";
import { useEventSessions, useEvents, useUpdateEvent } from "@/hooks/use-events";
import { useUnschedulePractice } from "@/hooks/use-planning";
import { useUsers } from "@/hooks/use-users";
import { localPartsToIso, isoToZonedParts, formatTimeRange } from "@/lib/datetime";
import { guessLocalTimezone } from "@/lib/timezones";
import type { DanceEventParticipant, DanceEventStatus } from "@/api/types";

const STATUS_OPTIONS: DanceEventStatus[] = [
  "unscheduled",
  "partially_scheduled",
  "scheduled",
  "completed",
  "archived",
];

export function EventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();
  const { data: events } = useEvents();
  const event = events?.find((e) => e.id === eventId);
  const { data: users } = useUsers();
  const { data: sessions } = useEventSessions(eventId);
  const updateEvent = useUpdateEvent();
  const unschedule = useUnschedulePractice();

  const tz = guessLocalTimezone();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(90);
  const [minDaysApart, setMinDaysApart] = useState(0);
  const [requiredSessionCount, setRequiredSessionCount] = useState(1);
  const [status, setStatus] = useState<DanceEventStatus>("unscheduled");
  const [deadlineDate, setDeadlineDate] = useState("");
  const [deadlineTime, setDeadlineTime] = useState("23:59");
  const [participants, setParticipants] = useState<Record<string, ParticipantSelection>>({});

  useEffect(() => {
    if (!event) return;
    setName(event.name);
    setDescription(event.description ?? "");
    setDurationMinutes(event.duration_minutes);
    setMinDaysApart(event.min_days_apart);
    setRequiredSessionCount(event.required_session_count);
    setStatus(event.status);
    const parts = isoToZonedParts(event.latest_schedule_at, tz);
    setDeadlineDate(parts.date);
    setDeadlineTime(parts.time);
    const selection: Record<string, ParticipantSelection> = {};
    for (const participant of event.participants) {
      selection[participant.user_id] = participant.role;
    }
    setParticipants(selection);
  }, [event?.id]);

  if (!event) {
    return <p className="text-sm text-muted-foreground">Loading event...</p>;
  }

  function handleSave() {
    if (!event) return;
    const latest_schedule_at = localPartsToIso(deadlineDate, deadlineTime, tz);
    const selectedParticipants: DanceEventParticipant[] = Object.entries(participants)
      .filter(([, role]) => role !== "none")
      .map(([user_id, role]) => ({ user_id, role: role as "required" | "optional" }));

    updateEvent.mutate({
      id: event.id,
      body: {
        name: name.trim(),
        description: description.trim() || undefined,
        duration_minutes: durationMinutes,
        min_days_apart: minDaysApart,
        latest_schedule_at,
        required_session_count: requiredSessionCount,
        status,
        participants: selectedParticipants,
      },
    });
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <Button variant="ghost" size="sm" onClick={() => navigate("/events")}>
        <ArrowLeft /> Back to events
      </Button>

      <div className="flex items-center gap-3">
        <h2 className="text-xl font-semibold">{event.name}</h2>
        <EventStatusBadge status={event.status} />
      </div>
      <p className="text-sm text-muted-foreground">
        {event.confirmed_session_count} confirmed / {event.remaining_session_count} remaining of{" "}
        {event.required_session_count} required sessions
      </p>

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle>Edit event</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-name">Name</Label>
            <Input id="edit-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-description">Description</Label>
            <Textarea id="edit-description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="edit-duration">Duration (minutes)</Label>
              <Input
                id="edit-duration"
                type="number"
                min={1}
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-sessions">Required sessions</Label>
              <Input
                id="edit-sessions"
                type="number"
                min={1}
                value={requiredSessionCount}
                onChange={(e) => setRequiredSessionCount(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-min-days">Min days between sessions</Label>
              <Input
                id="edit-min-days"
                type="number"
                min={0}
                value={minDaysApart}
                onChange={(e) => setMinDaysApart(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-status">Status</Label>
              <Select value={status} onValueChange={(v) => setStatus(v as DanceEventStatus)}>
                <SelectTrigger id="edit-status" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option.replace("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-deadline-date">Deadline date ({tz})</Label>
              <Input
                id="edit-deadline-date"
                type="date"
                value={deadlineDate}
                onChange={(e) => setDeadlineDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-deadline-time">Deadline time</Label>
              <Input
                id="edit-deadline-time"
                type="time"
                value={deadlineTime}
                onChange={(e) => setDeadlineTime(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Participants</Label>
            <ParticipantPicker
              users={users ?? []}
              value={participants}
              onChange={(userId, selection) => setParticipants((prev) => ({ ...prev, [userId]: selection }))}
            />
          </div>
          <Button onClick={handleSave} disabled={updateEvent.isPending}>
            {updateEvent.isPending ? "Saving..." : "Save changes"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Scheduled sessions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(!sessions || sessions.length === 0) && (
            <p className="text-sm text-muted-foreground">No sessions scheduled yet. Run planning to get recommendations.</p>
          )}
          {sessions?.map((session) => (
            <div key={session.id} className="flex items-center justify-between rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">
                  Session {session.session_index + 1} &middot; {formatTimeRange(session.start_at, session.end_at)}
                </p>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge variant="secondary">{session.status}</Badge>
                  {session.is_fallback && <Badge variant="warning">fallback</Badge>}
                  {session.total_score != null && (
                    <Badge variant="outline">score {session.total_score.toFixed(2)}</Badge>
                  )}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => unschedule.mutate(session.id)}
                disabled={unschedule.isPending}
              >
                <CalendarX className="size-4" /> Unschedule
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
