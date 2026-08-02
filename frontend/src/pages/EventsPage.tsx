import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CalendarX, Plus } from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import { EventStatusBadge } from "@/components/events/EventStatusBadge";
import { ParticipantPicker, type ParticipantSelection } from "@/components/events/ParticipantPicker";
import { useEventSessions, useEvents, useCreateEvent, useUpdateEvent } from "@/hooks/use-events";
import { useUnschedulePractice } from "@/hooks/use-planning";
import { useUsers } from "@/hooks/use-users";
import { eventColor } from "@/lib/eventColor";
import { hasRequiredParticipant } from "@/lib/participants";
import { formatTimeRange, isoToZonedParts, localPartsToIso } from "@/lib/datetime";
import { guessLocalTimezone } from "@/lib/timezones";
import { cn } from "@/lib/utils";
import type { DanceEventParticipant, DanceEventStatus } from "@/api/types";

const STATUS_OPTIONS: DanceEventStatus[] = [
  "unscheduled",
  "partially_scheduled",
  "scheduled",
  "completed",
  "archived",
];

const NEW_EVENT_ID = "__new__";

interface EventFormState {
  name: string;
  description: string;
  organizerId: string | undefined;
  durationMinutes: number;
  earliestStartDate: string;
  minDaysApart: number;
  requiredSessionCount: number;
  status: DanceEventStatus;
  deadlineDate: string;
  deadlineTime: string;
  participants: Record<string, ParticipantSelection>;
}

function emptyForm(defaultOrganizerId?: string): EventFormState {
  return {
    name: "",
    description: "",
    organizerId: defaultOrganizerId,
    durationMinutes: 90,
    earliestStartDate: "",
    minDaysApart: 0,
    requiredSessionCount: 3,
    status: "unscheduled",
    deadlineDate: "",
    deadlineTime: "23:59",
    participants: {},
  };
}

export function EventsPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();
  const { data: events, isLoading: eventsLoading, isError: eventsError } = useEvents();
  const { data: users } = useUsers();
  const createEvent = useCreateEvent();
  const updateEvent = useUpdateEvent();
  const unschedule = useUnschedulePractice();

  const [selectedId, setSelectedId] = useState<string | undefined>(eventId);
  const [form, setForm] = useState<EventFormState>(emptyForm());

  const isCreating = selectedId === NEW_EVENT_ID || (!selectedId && (events?.length ?? 0) === 0);
  const selectedEvent = events?.find((e) => e.id === selectedId);
  const { data: sessions } = useEventSessions(isCreating ? undefined : selectedEvent?.id);

  // Id of an event we just created. The list invalidation is async, so without this
  // the effect below sees a stale list that lacks the new id and "corrects" the
  // selection to some other event -- silently pointing the form at the wrong dance.
  const justCreatedId = useRef<string | null>(null);

  useEffect(() => {
    if (!events || events.length === 0) return;
    if (selectedId === NEW_EVENT_ID) return;
    if (selectedId && events.some((e) => e.id === selectedId)) {
      justCreatedId.current = null;
      return;
    }
    if (selectedId && selectedId === justCreatedId.current) return; // refetch hasn't landed
    setSelectedId(events[0].id);
  }, [events, selectedId]);

  useEffect(() => {
    if (isCreating) {
      setForm(emptyForm(users?.[0]?.id));
      return;
    }
    if (!selectedEvent) return;
    const organizerTz = users?.find((u) => u.id === selectedEvent.organizer_user_id)?.timezone ?? guessLocalTimezone();
    const parts = isoToZonedParts(selectedEvent.latest_schedule_at, organizerTz);
    const selection: Record<string, ParticipantSelection> = {};
    for (const participant of selectedEvent.participants) {
      selection[participant.user_id] = participant.role;
    }
    setForm({
      name: selectedEvent.name,
      description: selectedEvent.description ?? "",
      organizerId: selectedEvent.organizer_user_id,
      durationMinutes: selectedEvent.duration_minutes,
      earliestStartDate: selectedEvent.earliest_start_date ?? "",
      minDaysApart: selectedEvent.min_days_apart,
      requiredSessionCount: selectedEvent.required_session_count,
      status: selectedEvent.status,
      deadlineDate: parts.date,
      deadlineTime: parts.time,
      participants: selection,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEvent?.id, isCreating]);

  // Number("") is 0 and a partially-typed value is NaN, neither of which the backend
  // accepts -- so gate on them here instead of surfacing a cryptic 400 after Save.
  const positiveNumbers = [form.durationMinutes, form.requiredSessionCount].every(
    (value) => Number.isFinite(value) && value > 0,
  );
  const minDaysApartValid = Number.isFinite(form.minDaysApart) && form.minDaysApart >= 0;
  const canSave = Boolean(
    form.name.trim() &&
      form.organizerId &&
      form.deadlineDate &&
      form.deadlineTime &&
      positiveNumbers &&
      minDaysApartValid &&
      hasRequiredParticipant(form.participants),
  );

  function buildParticipants(): DanceEventParticipant[] {
    return Object.entries(form.participants)
      .filter(([, role]) => role === "required" || role === "optional")
      .map(([user_id, role]) => ({ user_id, role: role as "required" | "optional" }));
  }

  function handleSave() {
    if (!form.organizerId) return;
    const organizerTz = users?.find((u) => u.id === form.organizerId)?.timezone ?? guessLocalTimezone();
    const latest_schedule_at = localPartsToIso(form.deadlineDate, form.deadlineTime, organizerTz);

    if (isCreating) {
      createEvent.mutate(
        {
          name: form.name.trim(),
          description: form.description.trim() || undefined,
          organizer_user_id: form.organizerId,
          duration_minutes: form.durationMinutes,
          earliest_start_date: form.earliestStartDate || undefined,
          min_days_apart: form.minDaysApart,
          latest_schedule_at,
          required_session_count: form.requiredSessionCount,
          participants: buildParticipants(),
        },
        {
          onSuccess: (created) => {
            justCreatedId.current = created.id;
            setSelectedId(created.id);
          },
        },
      );
      return;
    }

    if (!selectedEvent) return;
    updateEvent.mutate({
      id: selectedEvent.id,
      body: {
        name: form.name.trim(),
        // null, not undefined: JSON.stringify drops undefined keys, so clearing these
        // never reached the backend and the old value silently stuck around
        description: form.description.trim() || null,
        organizer_user_id: form.organizerId,
        duration_minutes: form.durationMinutes,
        earliest_start_date: form.earliestStartDate || null,
        min_days_apart: form.minDaysApart,
        latest_schedule_at,
        required_session_count: form.requiredSessionCount,
        status: form.status,
        participants: buildParticipants(),
      },
    });
  }

  const isSaving = createEvent.isPending || updateEvent.isPending;

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <p className="text-xs text-muted-foreground mb-1">Dashboard / Events</p>
        <h2 className="text-2xl font-bold tracking-tight">Events</h2>
      </div>

      {eventsLoading && <p className="text-sm text-muted-foreground">Loading dances...</p>}
      {eventsError && (
        <p className="text-sm text-destructive">
          Failed to load dances. Check that the API is running, then reload.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {(events ?? []).map((eventItem) => (
          <button
            key={eventItem.id}
            type="button"
            onClick={() => {
              setSelectedId(eventItem.id);
              navigate(`/events/${eventItem.id}`, { replace: true });
            }}
            className={cn(
              "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors border",
              eventItem.id === selectedId
                ? "bg-secondary text-primary border-primary/30"
                : "bg-card text-foreground/70 border-black/10 hover:bg-accent/50",
            )}
          >
            <span className="size-2 rounded-full" style={{ background: eventColor(eventItem.id) }} />
            {eventItem.name}
          </button>
        ))}
        <button
          type="button"
          onClick={() => {
            setSelectedId(NEW_EVENT_ID);
            navigate("/events", { replace: true });
          }}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold border border-dashed",
            isCreating ? "bg-secondary text-primary border-primary/30" : "text-foreground/60 border-black/15 hover:bg-accent/50",
          )}
        >
          <Plus className="size-4" /> New dance
        </button>
      </div>

      {!isCreating && selectedEvent && (
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="text-xl font-bold">{selectedEvent.name}</div>
            <EventStatusBadge status={selectedEvent.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {selectedEvent.confirmed_session_count} confirmed / {selectedEvent.remaining_session_count} remaining of{" "}
            {selectedEvent.required_session_count} required sessions
          </p>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{isCreating ? "Create a dance event" : "Edit event"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="event-name">Name</Label>
            <Input id="event-name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="event-description">Description</Label>
            <Textarea
              id="event-description"
              rows={2}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="event-organizer">Organizer</Label>
            <Select value={form.organizerId} onValueChange={(v) => setForm((f) => ({ ...f, organizerId: v }))}>
              <SelectTrigger id="event-organizer" className="w-full">
                <SelectValue placeholder="Choose an organizer" />
              </SelectTrigger>
              <SelectContent>
                {(users ?? []).map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {user.display_name} ({user.timezone})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="event-duration">Duration (minutes)</Label>
              <Input
                id="event-duration"
                type="number"
                min={1}
                value={form.durationMinutes}
                onChange={(e) => setForm((f) => ({ ...f, durationMinutes: Number(e.target.value) }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-sessions">Required sessions</Label>
              <Input
                id="event-sessions"
                type="number"
                min={1}
                value={form.requiredSessionCount}
                onChange={(e) => setForm((f) => ({ ...f, requiredSessionCount: Number(e.target.value) }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-earliest">Earliest start date (optional)</Label>
              <Input
                id="event-earliest"
                type="date"
                value={form.earliestStartDate}
                onChange={(e) => setForm((f) => ({ ...f, earliestStartDate: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-min-days">Min days between sessions</Label>
              <Input
                id="event-min-days"
                type="number"
                min={0}
                value={form.minDaysApart}
                onChange={(e) => setForm((f) => ({ ...f, minDaysApart: Number(e.target.value) }))}
              />
            </div>
            {!isCreating && (
              <div className="space-y-2">
                <Label htmlFor="event-status">Status</Label>
                <Select value={form.status} onValueChange={(v) => setForm((f) => ({ ...f, status: v as DanceEventStatus }))}>
                  <SelectTrigger id="event-status" className="w-full">
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
            )}
            <div className="space-y-2">
              <Label htmlFor="event-deadline-date">
                Deadline date {form.organizerId && `(${users?.find((u) => u.id === form.organizerId)?.timezone ?? guessLocalTimezone()})`}
              </Label>
              <Input
                id="event-deadline-date"
                type="date"
                value={form.deadlineDate}
                onChange={(e) => setForm((f) => ({ ...f, deadlineDate: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-deadline-time">Deadline time</Label>
              <Input
                id="event-deadline-time"
                type="time"
                value={form.deadlineTime}
                onChange={(e) => setForm((f) => ({ ...f, deadlineTime: e.target.value }))}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Participants</Label>
            <ParticipantPicker
              users={users ?? []}
              value={form.participants}
              onChange={(userId, selection) =>
                setForm((f) => ({ ...f, participants: { ...f.participants, [userId]: selection } }))
              }
            />
            {!hasRequiredParticipant(form.participants) && (
              <p className="text-xs text-destructive">Select at least one required participant.</p>
            )}
          </div>
          <Button onClick={handleSave} disabled={!canSave || isSaving}>
            {isSaving ? "Saving..." : isCreating ? "Create event" : "Save changes"}
          </Button>
        </CardContent>
      </Card>

      {!isCreating && selectedEvent && (
        <Card>
          <CardHeader>
            <CardTitle>Scheduled sessions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(!sessions || sessions.length === 0) && (
              <p className="text-sm text-muted-foreground">No sessions scheduled yet. Run planning from the Calendar page.</p>
            )}
            {sessions?.map((session) => {
              const organizerTz = users?.find((u) => u.id === selectedEvent.organizer_user_id)?.timezone;
              return (
                <div key={session.id} className="flex items-center justify-between rounded-md border p-3">
                  <div>
                    <p className="text-sm font-medium">
                      Session {session.session_index + 1} &middot; {formatTimeRange(session.start_at, session.end_at, organizerTz)}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge variant="secondary">{session.status}</Badge>
                      {session.is_fallback && <Badge variant="warning">fallback</Badge>}
                      {session.total_score != null && <Badge variant="outline">score {session.total_score.toFixed(2)}</Badge>}
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => unschedule.mutate(session.id)} disabled={unschedule.isPending}>
                    <CalendarX className="size-4" /> Unschedule
                  </Button>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
