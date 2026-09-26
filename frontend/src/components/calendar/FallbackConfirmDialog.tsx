import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { missingParticipants } from "@/lib/participantStatus";
import type { PlanningParticipantStatus, UserRead } from "@/api/types";

export interface PendingFallback {
  runId: string;
  resultId: string;
  label: string;
  /** Statuses of the slot being confirmed, so the dialog can say who is missing and why. */
  statuses: PlanningParticipantStatus[];
  override?: { start_at: string; end_at: string };
}

interface FallbackConfirmDialogProps {
  pendingFallback: PendingFallback | null;
  usersById: Map<string, UserRead>;
  onCancel: () => void;
  onConfirm: () => void;
}

export function FallbackConfirmDialog({ pendingFallback, usersById, onCancel, onConfirm }: FallbackConfirmDialogProps) {
  const missing = pendingFallback ? missingParticipants(pendingFallback.statuses, usersById).filter((m) => m.role === "required") : [];
  return (
    <Dialog open={Boolean(pendingFallback)} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Missing a required participant</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          This slot for <strong>{pendingFallback?.label}</strong> is missing{" "}
          {missing.length === 1 ? "a required participant" : "required participants"}:
        </p>
        <ul className="text-sm space-y-1">
          {missing.map((person) => (
            <li key={person.userId}>
              <strong>{person.name}</strong> <span className="text-muted-foreground">{person.why}</span>
            </li>
          ))}
          {missing.length === 0 && <li className="text-muted-foreground">One or more required participants cannot attend.</li>}
        </ul>
        <p className="text-sm text-muted-foreground">Confirm anyway?</p>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Confirm anyway
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
