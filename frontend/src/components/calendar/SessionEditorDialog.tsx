import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarX, ExternalLink, Pencil } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { addMinutesToDateTime } from "@/lib/calendarGrid";
import { formatTimeRange, isoToZonedParts, localPartsToIso } from "@/lib/datetime";
import type { DanceEventRead, PracticeSessionRead, UserRead } from "@/api/types";

interface SessionEditorDialogProps {
  session: PracticeSessionRead | null;
  dance: DanceEventRead | undefined;
  usersById: Map<string, UserRead>;
  /** Zone the date/time fields are edited in; the grid's zone, so they agree. */
  timeZone: string;
  canEdit: boolean;
  isSaving: boolean;
  onClose: () => void;
  onSave: (session: PracticeSessionRead, startIso: string, endIso: string) => void;
  onUnschedule: (session: PracticeSessionRead) => void;
}

const TIME_STEP_SECONDS = 15 * 60;

/**
 * Google-Calendar-style editor for one confirmed session: change its date/time
 * (the dance's duration is fixed), see why the engine picked it, unschedule it.
 * Saving goes through the same reschedule path as drag-and-drop, so conflicts get
 * the same confirmation dialog.
 */
export function SessionEditorDialog({
  session,
  dance,
  usersById,
  timeZone,
  canEdit,
  isSaving,
  onClose,
  onSave,
  onUnschedule,
}: SessionEditorDialogProps) {
  const initial = useMemo(() => (session ? isoToZonedParts(session.start_at, timeZone) : null), [session, timeZone]);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  // Unschedule is destructive (it also deletes the Google Calendar event), so the
  // first click only arms the button.
  const [confirmingUnschedule, setConfirmingUnschedule] = useState(false);

  // Reset the form whenever a different session is opened (or the same one reloads).
  useEffect(() => {
    setDate(initial?.date ?? "");
    setTime(initial?.time ?? "");
    setConfirmingUnschedule(false);
  }, [initial]);

  if (!session) {
    return <Dialog open={false} onOpenChange={() => onClose()} />;
  }

  const durationMin =
    dance?.duration_minutes ?? Math.round((new Date(session.end_at).getTime() - new Date(session.start_at).getTime()) / 60000);
  const [hh, mm] = time.split(":").map(Number);
  const startMinute = Number.isFinite(hh) && Number.isFinite(mm) ? hh * 60 + mm : null;
  const endParts = date && startMinute !== null ? addMinutesToDateTime(date, startMinute + durationMin) : null;
  const dirty = Boolean(initial) && (date !== initial?.date || time !== initial?.time);
  const canSave = canEdit && dirty && Boolean(date) && startMinute !== null && !isSaving;
  const missingNames = session.missing_required_user_ids.map((id) => usersById.get(id)?.display_name ?? "Unknown member");

  function handleSave() {
    if (!session || !canSave || !endParts) return;
    onSave(session, localPartsToIso(date, time, timeZone), localPartsToIso(endParts.date, endParts.time, timeZone));
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !isSaving && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{dance?.name ?? "Practice session"}</DialogTitle>
          <DialogDescription>
            Session {session.session_index}
            {dance ? ` of ${dance.required_session_count}` : ""} &middot; {formatTimeRange(session.start_at, session.end_at, timeZone)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap gap-1">
          <Badge variant="secondary">{session.status}</Badge>
          {session.is_fallback && <Badge variant="warning">fallback</Badge>}
          {session.total_score != null && <Badge variant="outline">score {session.total_score.toFixed(2)}</Badge>}
          {session.source_run_id === null && <Badge variant="outline">set manually</Badge>}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="session-date">Date</Label>
            <Input
              id="session-date"
              type="date"
              value={date}
              disabled={!canEdit || isSaving}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="session-start">Start ({timeZone})</Label>
            <Input
              id="session-start"
              type="time"
              step={TIME_STEP_SECONDS}
              value={time}
              disabled={!canEdit || isSaving}
              onChange={(e) => setTime(e.target.value)}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {durationMin} minutes{endParts ? `, ends ${endParts.time}${endParts.date !== date ? " the next day" : ""}` : ""}. The
          duration is set on the dance.
        </p>

        {session.explanation.summary && (
          <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-1">
            <p className="font-medium">{session.explanation.summary}</p>
            {session.explanation.reasons.map((reason) => (
              <p key={reason.code} className="text-muted-foreground">
                {reason.message}
                {reason.score != null ? ` (${reason.score > 0 ? "+" : ""}${reason.score.toFixed(2)})` : ""}
              </p>
            ))}
            {missingNames.length > 0 && (
              <p className="text-destructive">Missing required: {missingNames.join(", ")}</p>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-3 text-xs">
          {dance && (
            <Link to={`/events/${dance.id}`} className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline">
              <Pencil className="size-3" /> Edit dance
            </Link>
          )}
          {session.google_calendar_html_link && (
            <a
              href={session.google_calendar_html_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline"
            >
              <ExternalLink className="size-3" /> Open in Google Calendar
            </a>
          )}
        </div>

        <DialogFooter className="sm:justify-between">
          {canEdit ? (
            <Button
              variant={confirmingUnschedule ? "destructive" : "outline"}
              onClick={() => (confirmingUnschedule ? onUnschedule(session) : setConfirmingUnschedule(true))}
              disabled={isSaving}
            >
              <CalendarX className="size-4" /> {confirmingUnschedule ? "Really unschedule?" : "Unschedule"}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose} disabled={isSaving}>
              {canEdit ? "Cancel" : "Close"}
            </Button>
            {canEdit && (
              <Button onClick={handleSave} disabled={!canSave}>
                {isSaving ? "Saving…" : "Save"}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
