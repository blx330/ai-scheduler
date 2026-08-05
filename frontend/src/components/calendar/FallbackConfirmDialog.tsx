import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export interface PendingFallback {
  runId: string;
  resultId: string;
  label: string;
  override?: { start_at: string; end_at: string };
}

interface FallbackConfirmDialogProps {
  pendingFallback: PendingFallback | null;
  onCancel: () => void;
  onConfirm: () => void;
}

export function FallbackConfirmDialog({ pendingFallback, onCancel, onConfirm }: FallbackConfirmDialogProps) {
  return (
    <Dialog open={Boolean(pendingFallback)} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Missing a required participant</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          This slot for <strong>{pendingFallback?.label}</strong> is missing one or more required participants.
          Confirm anyway?
        </p>
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
