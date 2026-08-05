import { ChevronLeft, Plus, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { eventColor } from "@/lib/eventColor";
import type { DanceEventRead } from "@/api/types";

interface DancesPanelProps {
  events: DanceEventRead[];
  checkedIds: Set<string>;
  onToggleChecked: (eventId: string, checked: boolean) => void;
  onCollapse: () => void;
  onSuggestSessions: () => void;
  onNewEvent: () => void;
  isPending: boolean;
}

export function DancesPanel({
  events,
  checkedIds,
  onToggleChecked,
  onCollapse,
  onSuggestSessions,
  onNewEvent,
  isPending,
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
        >
          <ChevronLeft className="size-4" />
        </button>
      </div>
      <p className="text-xs text-muted-foreground mb-3">Choose which dances to show and schedule.</p>

      <div className="flex flex-col gap-2.5 mb-4">
        {events.map((eventItem) => (
          <div key={eventItem.id} className="flex items-center gap-2.5">
            <Checkbox
              checked={checkedIds.has(eventItem.id)}
              onCheckedChange={(checked) => onToggleChecked(eventItem.id, Boolean(checked))}
            />
            <span className="size-2.5 rounded-full shrink-0" style={{ background: eventColor(eventItem.id) }} />
            <span className="flex-1 min-w-0 text-sm truncate">{eventItem.name}</span>
            <Badge
              variant={
                eventItem.status === "scheduled" ? "success" : eventItem.status === "partially_scheduled" ? "warning" : "outline"
              }
              className="text-[10px] whitespace-nowrap"
            >
              {eventItem.status.replace("_", " ")}
            </Badge>
          </div>
        ))}
        {events.length === 0 && <p className="text-xs text-muted-foreground">No dances yet &mdash; add one on the Events page.</p>}
      </div>

      <Button className="w-full mb-2" variant="secondary" onClick={onSuggestSessions} disabled={isPending}>
        <Sparkles className="size-4" /> Suggest sessions
      </Button>
      <Button className="w-full" onClick={onNewEvent} disabled={isPending}>
        <Plus className="size-4" /> New event
      </Button>
    </Card>
  );
}
