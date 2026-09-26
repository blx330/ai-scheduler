import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatTimeRange } from "@/lib/datetime";
import type { PracticeSessionRead, RescheduleConflictDetail } from "@/api/types";

export interface PendingReschedule {
  session: PracticeSessionRead;
  startIso: string;
  endIso: string;
  conflict: RescheduleConflictDetail;
}

interface RescheduleConflictDialogProps {
  pendingReschedule: PendingReschedule | null;
  /** True while the override retry is in flight; blocks a second "Move anyway" and closing. */
  isPending: boolean;
  onCancel: () => void;
  onConfirmAnyway: () => void;
}

export function RescheduleConflictDialog({ pendingReschedule, isPending, onCancel, onConfirmAnyway }: RescheduleConflictDialogProps) {
  return (
    <Dialog open={Boolean(pendingReschedule)} onOpenChange={(open) => !open && !isPending && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Scheduling conflict</DialogTitle>
        </DialogHeader>
        {pendingReschedule && (
          <p className="text-sm text-muted-foreground">
            This time overlaps <strong>{pendingReschedule.conflict.conflicting_label}</strong> (
            {formatTimeRange(pendingReschedule.conflict.conflicting_start_at, pendingReschedule.conflict.conflicting_end_at)}
            ), which {pendingReschedule.conflict.conflict_type === "room" ? "uses the same room" : "shares a participant"}. Move
            anyway?
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirmAnyway} disabled={isPending}>
            {isPending ? "Moving…" : "Move anyway"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
