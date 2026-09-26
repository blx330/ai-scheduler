import { ChevronLeft, Sparkles, WandSparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { DanceEventRead } from "@/api/types";

interface DancesPanelProps {
  events: DanceEventRead[];
  eventColorMap: Map<string, string>;
  checkedIds: Set<string>;
  onToggleChecked: (eventId: string, checked: boolean) => void;
  onCollapse: () => void;
  onSuggestSessions: () => void;
  onAutoSchedule: () => void;
  isPending: boolean;
  canEdit: boolean;
}

export function DancesPanel({
  events,
  eventColorMap,
  checkedIds,
  onToggleChecked,
  onCollapse,
  onSuggestSessions,
  onAutoSchedule,
  isPending,
  canEdit,
}: DancesPanelProps) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="text-base font-bold">Dances</div>
        <button
          type="button"
          onClick={onCollapse}
          className="text-muted-foreground hover:text-foreground text-sm px-1"
          title="Hide panel"
          aria-label="Hide panel"
        >
          <ChevronLeft className="size-4" />
        </button>
      </div>
      <p className="text-xs text-muted-foreground mb-3">Choose which dances to show and schedule.</p>

      <div className="flex flex-col gap-2.5 mb-4">
        {events.map((eventItem) => {
          const checkboxId = `dance-visible-${eventItem.id}`;
          return (
            <div key={eventItem.id} className="flex items-center gap-2.5">
              <Checkbox
                id={checkboxId}
                checked={checkedIds.has(eventItem.id)}
                onCheckedChange={(checked) => onToggleChecked(eventItem.id, Boolean(checked))}
              />
              <span aria-hidden className="size-2.5 rounded-full shrink-0" style={{ background: eventColorMap.get(eventItem.id) }} />
              <Label htmlFor={checkboxId} className="flex-1 min-w-0 text-sm font-normal truncate cursor-pointer">
                {eventItem.name}
              </Label>
              <Badge
                variant={
                  eventItem.status === "scheduled" ? "success" : eventItem.status === "partially_scheduled" ? "warning" : "outline"
                }
                className="text-[10px] whitespace-nowrap"
              >
                {eventItem.status.replace("_", " ")}
              </Badge>
            </div>
          );
        })}
        {events.length === 0 && <p className="text-xs text-muted-foreground">No dances yet &mdash; add one on the Events page.</p>}
      </div>

      {canEdit ? (
        <>
          <Button
            className="w-full mb-2"
            variant="secondary"
            onClick={onSuggestSessions}
            disabled={isPending}
            title="Show candidate slots for this week for every checked dance that still needs sessions. Nothing is saved until you confirm a slot."
          >
            <Sparkles className="size-4" /> Suggest sessions
          </Button>
          <Button
            className="w-full"
            onClick={onAutoSchedule}
            disabled={isPending}
            title="Run the planner for the first checked dance that still needs sessions and immediately confirm its top-ranked slot this week."
          >
            <WandSparkles className="size-4" /> Auto-schedule next session
          </Button>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">Only organizers can run planning or add dances.</p>
      )}
    </Card>
  );
}
