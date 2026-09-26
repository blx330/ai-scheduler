import { useMemo, type KeyboardEvent, type MouseEvent, type RefObject } from "react";
import { format } from "date-fns";
import { Check, X } from "lucide-react";

import { CalendarBlock } from "@/components/calendar/CalendarBlock";
import type { DragPreview } from "@/hooks/use-block-drag";
import {
  DAY_START_MIN,
  NUM_HOURS,
  PX_PER_MIN,
  assignLanes,
  clampDurationToDay,
  fmtHourLabel,
  gridPlacement,
} from "@/lib/calendarGrid";
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

function durationBetween(startIso: string, endIso: string): number {
  return Math.round((new Date(endIso).getTime() - new Date(startIso).getTime()) / 60000);
}

function isActivationKey(e: KeyboardEvent): boolean {
  return e.key === "Enter" || e.key === " ";
}

/** What to draw for a block being dragged in from another week (its source block
 * is not part of the visible week's data). */
export interface DragGhost {
  label: string;
  color: string;
  durationMin: number;
  isFallback: boolean;
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
  eventColorMap: Map<string, string>;
  activeRun: PlanningRunRead | null;
  dismissedResultIds: Set<string>;
  dragPreview: DragPreview | null;
  dragGhost: DragGhost | null;
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
  onConfirmSuggestion: (group: PlanningSessionRecommendationGroup, rec: PlanningRecommendationRead) => void;
  onDismissSuggestion: (recId: string) => void;
  onOpenSession: (session: PracticeSessionRead) => void;
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
  eventColorMap,
  activeRun,
  dismissedResultIds,
  dragPreview,
  dragGhost,
  editMode,
  gridRef,
  scrollContainerRef,
  onStartSuggestedDrag,
  onStartConfirmedDrag,
  onConfirmSuggestion,
  onDismissSuggestion,
  onOpenSession,
}: WeekGridProps) {
  const hourLabels = Array.from({ length: NUM_HOURS + 1 }, (_, i) => fmtHourLabel(DAY_START_MIN + i * 60));

  const suggestedBlocks = useMemo(() => {
    if (!activeRun) return [];
    const blocks: Array<{
      key: string;
      recId: string;
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
      blocks.push({
        key: `suggested-${rec.id}`,
        recId: rec.id,
        day: placement.day,
        startMin: placement.startMin,
        durationMin: clampDurationToDay(placement.startMin, durationBetween(rec.start_at, rec.end_at)),
        color: eventColorMap.get(group.dance_event_id) ?? eventColor(group.dance_event_id),
        label: `${group.dance_name} (suggested)`,
        timeLabel: fmtHourLabel(placement.startMin),
        isFallback: rec.is_fallback,
        tooltip: blockTooltip(rec, usersById),
        group,
        rec,
      });
    }
    return blocks;
  }, [activeRun, dismissedResultIds, dragPreview, dayDateStrings, usersById, eventColorMap]);

  const busyBlocks = useMemo(() => {
    const raw: Array<{ key: string; day: number; startMin: number; durationMin: number; label: string; color: string }> = [];
    for (const interval of overview?.busy_intervals ?? []) {
      if (!visibleMemberIds.has(interval.user_id)) continue;
      const placement = gridPlacement(interval.start_at, dayDateStrings);
      if (!placement) continue;
      raw.push({
        key: `busy-${interval.id}`,
        day: placement.day,
        startMin: placement.startMin,
        durationMin: clampDurationToDay(placement.startMin, durationBetween(interval.start_at, interval.end_at)),
        label: `${usersById.get(interval.user_id)?.display_name ?? "Someone"} (busy)`,
        color: memberColorMap.get(interval.user_id) ?? "#e5e7eb",
      });
    }
    // Concurrent busy blocks carry a visible name label each, so they are split into
    // side-by-side lanes per overlap cluster rather than stacked.
    return assignLanes(raw);
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
      const preview = dragPreview?.kind === "confirmed" && dragPreview.id === session.id ? dragPreview : null;
      const placement = preview ?? gridPlacement(session.start_at, dayDateStrings);
      if (!placement) continue;
      blocks.push({
        key: `confirmed-${session.id}`,
        day: placement.day,
        startMin: placement.startMin,
        durationMin: clampDurationToDay(placement.startMin, durationBetween(session.start_at, session.end_at)),
        color: eventColorMap.get(session.dance_event_id) ?? eventColor(session.dance_event_id),
        label: event.name,
        timeLabel: fmtHourLabel(placement.startMin),
        session,
      });
    }
    return blocks;
  }, [overview, eventsById, checkedIds, dayDateStrings, dragPreview, eventColorMap]);

  // A drag that crossed into this week from another one has no source block here,
  // so draw the preview from the ghost description instead.
  const ghostBlock = useMemo(() => {
    if (!dragPreview || !dragGhost) return null;
    const rendered =
      confirmedBlocks.some((block) => block.session.id === dragPreview.id) ||
      suggestedBlocks.some((block) => block.recId === dragPreview.id);
    if (rendered) return null;
    return {
      ...dragGhost,
      day: dragPreview.day,
      startMin: dragPreview.startMin,
      durationMin: clampDurationToDay(dragPreview.startMin, dragGhost.durationMin),
      timeLabel: fmtHourLabel(dragPreview.startMin),
      suggested: dragPreview.kind === "suggested",
    };
  }, [dragPreview, dragGhost, confirmedBlocks, suggestedBlocks]);

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
                aria-hidden
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
                role="button"
                tabIndex={0}
                aria-label={`${block.label}, confirmed, ${format(days[block.day], "EEEE")} ${block.timeLabel}. Press Enter to open.${editMode ? " Drag to reschedule." : ""}`}
                onMouseDown={
                  editMode
                    ? (e) => onStartConfirmedDrag(e, block.session, block.day, block.startMin, block.durationMin)
                    : undefined
                }
                // In edit mode a click is a drag that never moved; the drop handler
                // opens the editor in that case, so only bind onClick outside it.
                onClick={editMode ? undefined : () => onOpenSession(block.session)}
                onKeyDown={(e) => {
                  if (!isActivationKey(e) || e.target !== e.currentTarget) return;
                  e.preventDefault();
                  onOpenSession(block.session);
                }}
                className="shadow-sm"
                style={{
                  background: block.color,
                  color: "#fff",
                  borderRadius: 8,
                  padding: "8px 10px",
                  cursor: editMode ? "grab" : "pointer",
                  border: editMode ? "2px dashed rgba(255,255,255,0.7)" : "2px solid transparent",
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
                role="button"
                tabIndex={0}
                aria-label={`${block.label}, ${format(days[block.day], "EEEE")} ${block.timeLabel}${block.isFallback ? ", missing a required participant" : ""}. Press Enter to confirm this time.`}
                title={block.tooltip}
                onMouseDown={(e) => onStartSuggestedDrag(e, block.group, block.rec, block.day, block.startMin, block.durationMin)}
                onKeyDown={(e) => {
                  if (!isActivationKey(e) || e.target !== e.currentTarget) return;
                  e.preventDefault();
                  onConfirmSuggestion(block.group, block.rec);
                }}
                className="bg-card/70"
                style={{
                  border: `2px dashed ${block.isFallback ? "#dc2626" : block.color}`,
                  color: block.isFallback ? "#dc2626" : block.color,
                  borderRadius: 8,
                  padding: "8px 10px",
                  cursor: "grab",
                  userSelect: "none",
                }}
              >
                <div className="absolute top-1 right-1 flex items-center gap-0.5">
                  <button
                    type="button"
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={() => onConfirmSuggestion(block.group, block.rec)}
                    className="rounded p-0.5 opacity-70 hover:opacity-100 hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    title="Confirm this time"
                    aria-label={`Confirm ${block.group.dance_name} at ${block.timeLabel}`}
                  >
                    <Check className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onMouseDown={(e) => e.stopPropagation()}
                    onClick={() => onDismissSuggestion(block.recId)}
                    className="rounded p-0.5 opacity-60 hover:opacity-100 hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    title="Dismiss suggestion"
                    aria-label={`Dismiss ${block.group.dance_name} suggestion at ${block.timeLabel}`}
                  >
                    <X className="size-3" />
                  </button>
                </div>
                <div className="text-xs font-bold truncate pr-12">{block.label}</div>
                <div className="text-[11px] opacity-80 mt-0.5">{block.timeLabel}</div>
                {block.isFallback && <div className="text-[10px] font-semibold mt-0.5">missing required</div>}
              </CalendarBlock>
            ))}

            {ghostBlock && (
              <CalendarBlock
                day={ghostBlock.day}
                startMin={ghostBlock.startMin}
                durationMin={ghostBlock.durationMin}
                aria-hidden
                className="shadow-md"
                style={
                  ghostBlock.suggested
                    ? {
                        border: `2px dashed ${ghostBlock.isFallback ? "#dc2626" : ghostBlock.color}`,
                        color: ghostBlock.isFallback ? "#dc2626" : ghostBlock.color,
                        background: "rgba(255,255,255,0.85)",
                        borderRadius: 8,
                        padding: "8px 10px",
                        pointerEvents: "none",
                      }
                    : {
                        background: ghostBlock.color,
                        color: "#fff",
                        border: "2px dashed rgba(255,255,255,0.7)",
                        borderRadius: 8,
                        padding: "8px 10px",
                        opacity: 0.9,
                        pointerEvents: "none",
                      }
                }
              >
                <div className="text-xs font-bold truncate">{ghostBlock.label}</div>
                <div className="text-[11px] opacity-80 mt-0.5">{ghostBlock.timeLabel}</div>
              </CalendarBlock>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
