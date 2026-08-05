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
  onCancel: () => void;
  onConfirmAnyway: () => void;
}

export function RescheduleConflictDialog({ pendingReschedule, onCancel, onConfirmAnyway }: RescheduleConflictDialogProps) {
  return (
    <Dialog open={Boolean(pendingReschedule)} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Scheduling conflict</DialogTitle>
        </DialogHeader>
        {pendingReschedule && (
          <p className="text-sm text-muted-foreground">
            This time conflicts with <strong>{pendingReschedule.conflict.conflicting_label}</strong> (
            {formatTimeRange(pendingReschedule.conflict.conflicting_start_at, pendingReschedule.conflict.conflicting_end_at)}
            ) on the same {pendingReschedule.conflict.conflict_type === "room" ? "room" : "participant"}. Move
            anyway?
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirmAnyway}>
            Move anyway
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
