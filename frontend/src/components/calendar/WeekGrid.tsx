import { useMemo, type MouseEvent, type RefObject } from "react";
import { format } from "date-fns";
import { X } from "lucide-react";

import { CalendarBlock } from "@/components/calendar/CalendarBlock";
import type { DragPreview } from "@/hooks/use-block-drag";
import { DAY_START_MIN, NUM_HOURS, PX_PER_MIN, fmtHourLabel, gridPlacement } from "@/lib/calendarGrid";
import { eventColor } from "@/lib/eventColor";
import type {
  CalendarOverviewRead,
  DanceEventRead,
  PlanningRecommendationRead,
  PlanningRunRead,
  PlanningSessionRecommendationGroup,
  PracticeSessionRead,
  UserRead,
} from "@/api/types";

function blockTooltip(rec: PlanningRecommendationRead, usersById: Map<string, UserRead>): string {
  const statuses = rec.participant_statuses
    .map((s) => `${usersById.get(s.user_id)?.display_name ?? s.user_id} (${s.role}): ${s.available ? "available" : "unavailable"}`)
    .join("\n");
  const score = Object.entries(rec.score_breakdown)
    .map(([k, v]) => `${k}: ${v.toFixed(2)}`)
    .join("\n");
  return `Score ${rec.total_score.toFixed(2)}\n\nParticipants:\n${statuses}\n\nScore breakdown:\n${score}`;
}

interface WeekGridProps {
  days: Date[];
  dayDateStrings: string[];
  overview: CalendarOverviewRead | undefined;
  eventsById: Map<string, DanceEventRead>;
  usersById: Map<string, UserRead>;
  checkedIds: Set<string>;
  visibleMemberIds: Set<string>;
  memberColorMap: Map<string, string>;
  activeRun: PlanningRunRead | null;
  dismissedResultIds: Set<string>;
  dragPreview: DragPreview | null;
  editMode: boolean;
  gridRef: RefObject<HTMLDivElement | null>;
  scrollContainerRef: RefObject<HTMLDivElement | null>;
  onStartSuggestedDrag: (
    e: MouseEvent,
    group: PlanningSessionRecommendationGroup,
    rec: PlanningRecommendationRead,
    day: number,
    startMin: number,
    durationMin: number,
  ) => void;
  onStartConfirmedDrag: (e: MouseEvent, session: PracticeSessionRead, day: number, startMin: number, durationMin: number) => void;
  onDismissSuggestion: (recId: string) => void;
}

export function WeekGrid({
  days,
  dayDateStrings,
  overview,
  eventsById,
  usersById,
  checkedIds,
  visibleMemberIds,
  memberColorMap,
  activeRun,
  dismissedResultIds,
  dragPreview,
  editMode,
  gridRef,
  scrollContainerRef,
  onStartSuggestedDrag,
  onStartConfirmedDrag,
  onDismissSuggestion,
}: WeekGridProps) {
  const hourLabels = Array.from({ length: NUM_HOURS + 1 }, (_, i) => fmtHourLabel(DAY_START_MIN + i * 60));

  const suggestedBlocks = useMemo(() => {
    if (!activeRun) return [];
    const blocks: Array<{
      key: string;
      day: number;
      startMin: number;
      durationMin: number;
      color: string;
      label: string;
      timeLabel: string;
      isFallback: boolean;
      tooltip: string;
      group: PlanningSessionRecommendationGroup;
      rec: PlanningRecommendationRead;
    }> = [];
    for (const group of activeRun.results) {
      // Fall through to the next-ranked option rather than dropping the whole group
      // when the top one is dismissed.
      const rec = group.recommendations.find((item) => item.id && !dismissedResultIds.has(item.id));
      if (!rec || !rec.id) continue;
      const preview = dragPreview?.kind === "suggested" && dragPreview.id === rec.id ? dragPreview : null;
      const placement = preview ?? gridPlacement(rec.start_at, dayDateStrings);
      if (!placement) continue;
      const durationMin = Math.round((new Date(rec.end_at).getTime() - new Date(rec.start_at).getTime()) / 60000);
      blocks.push({
        key: `suggested-${rec.id}`,
        day: placement.day,
        startMin: placement.startMin,
        durationMin,
        color: eventColor(group.dance_event_id),
        label: `${group.dance_name} (suggested)`,
        timeLabel: fmtHourLabel(placement.startMin),
        isFallback: rec.is_fallback,
        tooltip: blockTooltip(rec, usersById),
        group,
        rec,
      });
    }
    return blocks;
  }, [activeRun, dismissedResultIds, dragPreview, dayDateStrings, usersById]);

  const busyBlocks = useMemo(() => {
    type RawBusyBlock = { key: string; day: number; startMin: number; durationMin: number; label: string; color: string };
    const raw: RawBusyBlock[] = [];
    for (const interval of overview?.busy_intervals ?? []) {
      if (!visibleMemberIds.has(interval.user_id)) continue;
      const placement = gridPlacement(interval.start_at, dayDateStrings);
      if (!placement) continue;
      const durationMin = Math.round(
        (new Date(interval.end_at).getTime() - new Date(interval.start_at).getTime()) / 60000,
      );
      raw.push({
        key: `busy-${interval.id}`,
        day: placement.day,
        startMin: placement.startMin,
        durationMin,
        label: `${usersById.get(interval.user_id)?.display_name ?? "Someone"} (busy)`,
        color: memberColorMap.get(interval.user_id) ?? "#e5e7eb",
      });
    }

    // Overlapping busy blocks on the same day would otherwise render stacked on top
    // of each other now that each one carries a visible name label -- split
    // concurrent blocks into side-by-side lanes so they all stay readable.
    const byDay = new Map<number, RawBusyBlock[]>();
    for (const block of raw) {
      if (!byDay.has(block.day)) byDay.set(block.day, []);
      byDay.get(block.day)!.push(block);
    }

    const blocks: Array<RawBusyBlock & { lane: number; laneCount: number }> = [];
    for (const dayBlocks of byDay.values()) {
      dayBlocks.sort((a, b) => a.startMin - b.startMin);
      const laneEndMin: number[] = [];
      const withLanes: Array<RawBusyBlock & { lane: number }> = [];
      for (const block of dayBlocks) {
        let lane = laneEndMin.findIndex((end) => end <= block.startMin);
        if (lane === -1) {
          lane = laneEndMin.length;
          laneEndMin.push(block.startMin + block.durationMin);
        } else {
          laneEndMin[lane] = block.startMin + block.durationMin;
        }
        withLanes.push({ ...block, lane });
      }
      const laneCount = laneEndMin.length;
      for (const block of withLanes) blocks.push({ ...block, laneCount });
    }

    return blocks;
  }, [overview, usersById, dayDateStrings, visibleMemberIds, memberColorMap]);

  const confirmedBlocks = useMemo(() => {
    const blocks: Array<{
      key: string;
      day: number;
      startMin: number;
      durationMin: number;
      color: string;
      label: string;
      timeLabel: string;
      session: PracticeSessionRead;
    }> = [];
    for (const session of overview?.practice_sessions ?? []) {
      const event = eventsById.get(session.dance_event_id);
      if (!event || !checkedIds.has(event.id)) continue;
      const durationMin = Math.round((new Date(session.end_at).getTime() - new Date(session.start_at).getTime()) / 60000);
      const preview = dragPreview?.kind === "confirmed" && dragPreview.id === session.id ? dragPreview : null;
      const placement = preview ?? gridPlacement(session.start_at, dayDateStrings);
      if (!placement) continue;
      blocks.push({
        key: `confirmed-${session.id}`,
        day: placement.day,
        startMin: placement.startMin,
        durationMin,
        color: eventColor(session.dance_event_id),
        label: event.name,
        timeLabel: fmtHourLabel(placement.startMin),
        session,
      });
    }
    return blocks;
  }, [overview, eventsById, checkedIds, dayDateStrings, dragPreview]);

  return (
    <div ref={scrollContainerRef} className="flex-1 min-h-0 overflow-auto">
      <div className="min-w-[900px]">
        <div className="sticky top-0 z-10 bg-card grid" style={{ gridTemplateColumns: "64px repeat(7,1fr)" }}>
          <div />
          {days.map((day) => (
            <div key={day.toISOString()} className="text-center py-3 border-l border-black/[0.06]">
              <div className="text-xs text-muted-foreground">{format(day, "EEE")}</div>
              <div className="text-base font-bold mt-0.5">{format(day, "d")}</div>
            </div>
          ))}
        </div>

        <div className="relative grid border-t border-black/[0.06]" style={{ gridTemplateColumns: "64px 1fr" }}>
          <div>
            {hourLabels.map((label, i) => (
              <div key={i} style={{ height: 72 }} className="text-right pr-2.5 text-xs text-muted-foreground -translate-y-1.5">
                {label}
              </div>
            ))}
          </div>

          <div
            ref={gridRef}
            className="relative"
            style={{
              height: NUM_HOURS * 72,
              backgroundImage:
                "repeating-linear-gradient(to bottom, rgba(0,0,0,0.06) 0, rgba(0,0,0,0.06) 1px, transparent 1px, transparent 72px), repeating-linear-gradient(to right, rgba(0,0,0,0.06) 0, rgba(0,0,0,0.06) 1px, transparent 1px, transparent calc(100% / 7))",
            }}
          >
            {/* Google-derived busy time, drawn under the practice blocks so the
                grid can show why a slot was not offered. */}
            {busyBlocks.map((block) => (
              <CalendarBlock
                key={block.key}
                day={block.day}
                startMin={block.startMin}
                durationMin={block.durationMin}
                lane={block.lane}
                laneCount={block.laneCount}
                title={block.label}
                style={{
                  borderRadius: 6,
                  border: `1px solid ${block.color}`,
                  borderLeft: `3px solid ${block.color}`,
                  background: `${block.color}33`,
                  pointerEvents: "none",
                }}
              >
                {block.durationMin * PX_PER_MIN >= 20 && (
                  <div className="text-[9px] font-semibold truncate px-1 pt-0.5" style={{ color: "#1f2937" }}>
                    {block.label}
                  </div>
                )}
              </CalendarBlock>
            ))}

            {confirmedBlocks.map((block) => (
              <CalendarBlock
                key={block.key}
                day={block.day}
                startMin={block.startMin}
                durationMin={block.durationMin}
                onMouseDown={
                  editMode
                    ? (e) => onStartConfirmedDrag(e, block.session, block.day, block.startMin, block.durationMin)
                    : undefined
                }
                style={{
                  background: block.color,
                  color: "#fff",
                  borderRadius: 8,
                  padding: "8px 10px",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
                  cursor: editMode ? "grab" : "default",
                  outline: editMode ? "2px dashed rgba(255,255,255,0.7)" : "none",
                  outlineOffset: -4,
                  userSelect: editMode ? "none" : undefined,
                }}
              >
                <div className="text-xs font-bold truncate">{block.label}</div>
                <div className="text-[11px] opacity-80 mt-0.5">{block.timeLabel}</div>
              </CalendarBlock>
            ))}

            {suggestedBlocks.map((block) => (
              <CalendarBlock
                key={block.key}
                day={block.day}
                startMin={block.startMin}
                durationMin={block.durationMin}
                title={block.tooltip}
                onMouseDown={(e) => onStartSuggestedDrag(e, block.group, block.rec, block.day, block.startMin, block.durationMin)}
                style={{
                  background: "transparent",
                  border: `2px dashed ${block.isFallback ? "#dc2626" : block.color}`,
                  color: block.isFallback ? "#dc2626" : block.color,
                  borderRadius: 8,
                  padding: "8px 10px",
                  cursor: "grab",
                  userSelect: "none",
                }}
              >
                <button
                  type="button"
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={() => onDismissSuggestion(block.rec.id!)}
                  className="absolute top-1 right-1 opacity-60 hover:opacity-100"
                  title="Dismiss suggestion"
                >
                  <X className="size-3" />
                </button>
                <div className="text-xs font-bold truncate pr-3">{block.label}</div>
                <div className="text-[11px] opacity-80 mt-0.5">{block.timeLabel}</div>
                {block.isFallback && <div className="text-[10px] font-semibold mt-0.5">missing required</div>}
              </CalendarBlock>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
