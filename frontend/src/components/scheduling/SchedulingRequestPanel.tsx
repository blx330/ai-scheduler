import { useId, useState } from "react";

import type { PlanningRunRead, SchedulingRequestReview } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  requestErrorDetail,
  useConfirmSchedulingRequest,
  useParseSchedulingRequest,
} from "@/hooks/use-scheduling-requests";

const MAX_CHARS = 1000;
const PLACEHOLDER =
  "Schedule 3 Hip Hop rehearsals before Oct 20, at least 2 days apart, Maya and Jordan required, no Fridays, Studio B.";

interface Props {
  onPlanned: (run: PlanningRunRead) => void;
}

/**
 * Plain-English request -> reviewed hard constraints -> planning run.
 * Nothing is saved until the organizer presses "Confirm & plan"; the server
 * re-validates the reviewed proposal at that point.
 */
export function SchedulingRequestPanel({ onPlanned }: Props) {
  const inputId = useId();
  const [text, setText] = useState("");
  const [review, setReview] = useState<SchedulingRequestReview | null>(null);
  const parse = useParseSchedulingRequest();
  const confirm = useConfirmSchedulingRequest();

  function handleReview() {
    confirm.reset();
    parse.mutate(text.trim(), { onSuccess: setReview });
  }

  function handleEdit() {
    setReview(null);
    parse.reset();
    confirm.reset();
  }

  function handleConfirm() {
    if (!review) return;
    confirm.mutate(review.proposal, {
      onSuccess: (data) => {
        setReview(null);
        setText("");
        onPlanned(data.planning_run);
      },
    });
  }

  const error = parse.error ?? confirm.error;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Schedule in plain English</CardTitle>
        <CardDescription>
          Describe the rehearsals you need. You&rsquo;ll review the exact rules before anything is saved or planned.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {review === null ? (
          <div className="space-y-2">
            <Label htmlFor={inputId}>Describe what to schedule</Label>
            <Textarea
              id={inputId}
              value={text}
              maxLength={MAX_CHARS}
              placeholder={PLACEHOLDER}
              onChange={(event) => setText(event.target.value)}
              rows={3}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {text.length}/{MAX_CHARS}
              </span>
              <Button onClick={handleReview} disabled={!text.trim() || parse.isPending}>
                {parse.isPending ? "Reading request…" : "Review"}
              </Button>
            </div>
          </div>
        ) : (
          <ReviewView
            review={review}
            confirming={confirm.isPending}
            onConfirm={handleConfirm}
            onEdit={handleEdit}
          />
        )}

        {error && <ErrorView error={error} />}
      </CardContent>
    </Card>
  );
}

function ReviewView({
  review,
  confirming,
  onConfirm,
  onEdit,
}: {
  review: SchedulingRequestReview;
  confirming: boolean;
  onConfirm: () => void;
  onEdit: () => void;
}) {
  const { event, proposal } = review;
  return (
    <section aria-label={`Review: ${event.name}`} className="space-y-4">
      <p className="text-sm italic text-muted-foreground">&ldquo;{review.request_text}&rdquo;</p>

      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Dance</dt>
        <dd className="font-medium">
          {event.name} <span className="text-muted-foreground">({event.duration_minutes} min sessions)</span>
        </dd>
        <dt className="text-muted-foreground">Room</dt>
        <dd>{review.room ? review.room.name : "Default shared room"}</dd>
        <dt className="text-muted-foreground">Window</dt>
        <dd>
          {proposal.earliest_date ?? "today"} to {proposal.latest_date}{" "}
          <span className="text-muted-foreground">({event.organizer_timezone})</span>
        </dd>
        <dt className="text-muted-foreground">Planning</dt>
        <dd>
          {review.sessions_to_plan} sessions to plan
          {event.confirmed_session_count > 0 && ` (${event.confirmed_session_count} already confirmed)`}
        </dd>
      </dl>

      <div>
        <h4 className="mb-1 text-sm font-semibold">Changes to this dance&rsquo;s rules</h4>
        {review.changes.length === 0 ? (
          <p className="text-sm text-muted-foreground">None; the saved rules will be used as they are.</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {review.changes.map((change) => (
                <tr key={change.field} className="border-b last:border-0">
                  <td className="py-1 pr-3 text-muted-foreground">{change.label}</td>
                  <td className="py-1">
                    <span className="line-through text-muted-foreground">{change.before}</span>
                    <span aria-hidden> → </span>
                    <span className="sr-only"> changes to </span>
                    <span className="font-medium">{change.after}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div>
        <h4 className="mb-1 text-sm font-semibold">Dancers</h4>
        <ul className="space-y-1 text-sm">
          {review.participants.map((participant) => (
            <li key={participant.user_id} className="flex items-center gap-2">
              <span>{participant.display_name}</span>
              <Badge variant={participant.role === "required" ? "default" : "outline"}>{participant.role}</Badge>
              {participant.change !== "unchanged" && (
                <Badge variant="warning">{participant.change === "added" ? "added" : "role changed"}</Badge>
              )}
            </li>
          ))}
        </ul>
      </div>

      <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
        {review.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onEdit} disabled={confirming}>
          Edit request
        </Button>
        <Button onClick={onConfirm} disabled={confirming}>
          {confirming ? "Planning…" : "Confirm & plan"}
        </Button>
      </div>
    </section>
  );
}

function ErrorView({ error }: { error: unknown }) {
  const detail = requestErrorDetail(error);
  return (
    <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm">
      <p className="font-medium text-destructive">{detail.message}</p>
      {detail.errors.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-destructive">
          {detail.errors.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
