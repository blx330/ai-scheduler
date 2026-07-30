import { useState, type FormEvent } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { ParticipantPicker, type ParticipantSelection } from "./ParticipantPicker";
import { useCreateEvent } from "@/hooks/use-events";
import { useUsers } from "@/hooks/use-users";
import { guessLocalTimezone } from "@/lib/timezones";
import { localPartsToIso } from "@/lib/datetime";
import type { DanceEventParticipant } from "@/api/types";

export function CreateEventDialog() {
  const [open, setOpen] = useState(false);
  const { data: users } = useUsers();
  const createEvent = useCreateEvent();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [organizerId, setOrganizerId] = useState<string | undefined>(undefined);
  const [durationMinutes, setDurationMinutes] = useState(90);
  const [earliestStartDate, setEarliestStartDate] = useState("");
  const [minDaysApart, setMinDaysApart] = useState(0);
  const [deadlineDate, setDeadlineDate] = useState("");
  const [deadlineTime, setDeadlineTime] = useState("23:59");
  const [requiredSessionCount, setRequiredSessionCount] = useState(3);
  const [participants, setParticipants] = useState<Record<string, ParticipantSelection>>({});

  function reset() {
    setName("");
    setDescription("");
    setOrganizerId(undefined);
    setDurationMinutes(90);
    setEarliestStartDate("");
    setMinDaysApart(0);
    setDeadlineDate("");
    setDeadlineTime("23:59");
    setRequiredSessionCount(3);
    setParticipants({});
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!organizerId || !deadlineDate) return;
    const organizer = users?.find((u) => u.id === organizerId);
    const tz = organizer?.timezone ?? guessLocalTimezone();
    const latest_schedule_at = localPartsToIso(deadlineDate, deadlineTime, tz);

    const selectedParticipants: DanceEventParticipant[] = Object.entries(participants)
      .filter(([, role]) => role !== "none")
      .map(([user_id, role]) => ({ user_id, role: role as "required" | "optional" }));

    createEvent.mutate(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        organizer_user_id: organizerId,
        duration_minutes: durationMinutes,
        earliest_start_date: earliestStartDate || undefined,
        min_days_apart: minDaysApart,
        latest_schedule_at,
        required_session_count: requiredSessionCount,
        participants: selectedParticipants,
      },
      {
        onSuccess: () => {
          setOpen(false);
          reset();
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus /> New event
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Create a dance event</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="event-name">Name</Label>
            <Input id="event-name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="event-description">Description</Label>
            <Textarea id="event-description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="event-organizer">Organizer</Label>
            <Select value={organizerId} onValueChange={setOrganizerId}>
              <SelectTrigger id="event-organizer" className="w-full">
                <SelectValue placeholder="Choose an organizer" />
              </SelectTrigger>
              <SelectContent>
                {(users ?? []).map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {user.display_name}
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
                required
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-sessions">Required sessions</Label>
              <Input
                id="event-sessions"
                type="number"
                min={1}
                required
                value={requiredSessionCount}
                onChange={(e) => setRequiredSessionCount(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-earliest">Earliest start date (optional)</Label>
              <Input
                id="event-earliest"
                type="date"
                value={earliestStartDate}
                onChange={(e) => setEarliestStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-min-days">Min days between sessions</Label>
              <Input
                id="event-min-days"
                type="number"
                min={0}
                value={minDaysApart}
                onChange={(e) => setMinDaysApart(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-deadline-date">Deadline date</Label>
              <Input
                id="event-deadline-date"
                type="date"
                required
                value={deadlineDate}
                onChange={(e) => setDeadlineDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-deadline-time">Deadline time</Label>
              <Input
                id="event-deadline-time"
                type="time"
                required
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
          <DialogFooter>
            <Button type="submit" disabled={createEvent.isPending || !name.trim() || !organizerId || !deadlineDate}>
              {createEvent.isPending ? "Creating..." : "Create event"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
