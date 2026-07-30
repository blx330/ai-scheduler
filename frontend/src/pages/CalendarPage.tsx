import { useEffect, useMemo, useRef, useState } from "react";
import { addDays, addWeeks, endOfWeek, format, startOfWeek, subWeeks } from "date-fns";
import { ChevronLeft, ChevronRight, Plus, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useCalendarOverview } from "@/hooks/use-calendar";
import { useEvents } from "@/hooks/use-events";
import { useConfirmPlanningRun, useCreatePlanningRun } from "@/hooks/use-planning";
import { useUsers } from "@/hooks/use-users";
import { eventColor } from "@/lib/eventColor";
import { localPartsToIso } from "@/lib/datetime";
import type { PlanningRecommendationRead, PlanningRunRead, PlanningSessionRecommendationGroup } from "@/api/types";

const DAY_START_MIN = 7 * 60;
const DAY_END_MIN = 24 * 60;
const PX_PER_MIN = 72 / 60;
const NUM_HOURS = (DAY_END_MIN - DAY_START_MIN) / 60;

function minutesToHHMM(mins: number): string {
  const clamped = ((mins % 1440) + 1440) % 1440;
  const h = Math.floor(clamped / 60);
  const m = clamped % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function addMinutesToDateTime(dateStr: string, minutesOfDay: number): { date: string; time: string } {
  if (minutesOfDay < 1440) return { date: dateStr, time: minutesToHHMM(minutesOfDay) };
  const rolledDate = format(addDays(new Date(`${dateStr}T00:00:00`), Math.floor(minutesOfDay / 1440)), "yyyy-MM-dd");
  return { date: rolledDate, time: minutesToHHMM(minutesOfDay) };
}

function fmtHourLabel(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const hh = h % 12 === 0 ? 12 : h % 12;
  return `${hh} ${h < 12 ? "AM" : "PM"}`;
}

interface DragState {
  runId: string;
  rec: PlanningRecommendationRead;
  groupLabel: string;
  organizerTz: string;
  startClientX: number;
  startClientY: number;
  origDay: number;
  origStartMin: number;
  durationMin: number;
  moved: boolean;
  finalDay: number;
  finalStartMin: number;
}

interface PendingFallback {
  runId: string;
  resultId: string;
  label: string;
  override?: { start_at: string; end_at: string };
}

export function CalendarPage() {
  const { data: events } = useEvents();
  const { data: users } = useUsers();
  const createRun = useCreatePlanningRun();
  const confirmRun = useConfirmPlanningRun();

  const [anchor, setAnchor] = useState(() => new Date());
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [activeRun, setActiveRun] = useState<PlanningRunRead | null>(null);
  const [dismissedResultIds, setDismissedResultIds] = useState<Set<string>>(new Set());
  const [dragPreview, setDragPreview] = useState<{ resultId: string; day: number; startMin: number } | null>(null);
  const [pendingFallback, setPendingFallback] = useState<PendingFallback | null>(null);

  const gridRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!events) return;
    setCheckedIds((prev) => {
      const next = new Set(prev);
      let changed = false;
      for (const e of events) {
        if (!next.has(e.id)) {
          next.add(e.id);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [events]);

  const weekStart = useMemo(() => startOfWeek(anchor, { weekStartsOn: 1 }), [anchor]);
  const weekEnd = useMemo(() => endOfWeek(anchor, { weekStartsOn: 1 }), [anchor]);
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);
  const dayDateStrings = useMemo(() => days.map((d) => format(d, "yyyy-MM-dd")), [days]);

  const { data: overview } = useCalendarOverview(weekStart.toISOString(), weekEnd.toISOString());

  const eventsById = useMemo(() => new Map((events ?? []).map((e) => [e.id, e])), [events]);
  const usersById = useMemo(() => new Map((users ?? []).map((u) => [u.id, u])), [users]);

  function organizerTzFor(danceEventId: string): string {
    const event = eventsById.get(danceEventId);
    const organizer = event ? usersById.get(event.organizer_user_id) : undefined;
    return organizer?.timezone ?? "UTC";
  }

  function zonedDayAndMinutes(iso: string, tz: string): { day: number; startMin: number } | null {
    const zoned = new Date(iso).toLocaleString("en-US", { timeZone: tz });
    const d = new Date(zoned);
    const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const day = dayDateStrings.indexOf(dateStr);
    if (day === -1) return null;
    return { day, startMin: d.getHours() * 60 + d.getMinutes() };
  }

  function blockTooltip(rec: PlanningRecommendationRead): string {
    const statuses = rec.participant_statuses
      .map((s) => `${usersById.get(s.user_id)?.display_name ?? s.user_id} (${s.role}): ${s.available ? "available" : "unavailable"}`)
      .join("\n");
    const score = Object.entries(rec.score_breakdown)
      .map(([k, v]) => `${k}: ${v.toFixed(2)}`)
      .join("\n");
    return `Score ${rec.total_score.toFixed(2)}\n\nParticipants:\n${statuses}\n\nScore breakdown:\n${score}`;
  }

  function commitConfirm(
    runId: string,
    rec: PlanningRecommendationRead,
    label: string,
    override?: { start_at: string; end_at: string },
  ) {
    if (!rec.id) return;
    if (rec.is_fallback) {
      setPendingFallback({ runId, resultId: rec.id, label, override });
      return;
    }
    const resultId = rec.id;
    confirmRun.mutate(
      { runId, body: { confirmations: [override ? { result_id: resultId, ...override } : { result_id: resultId }] } },
      { onSuccess: () => setDismissedResultIds((prev) => new Set(prev).add(resultId)) },
    );
  }

  function confirmPendingFallback() {
    if (!pendingFallback) return;
    const { runId, resultId, override } = pendingFallback;
    confirmRun.mutate(
      { runId, body: { confirmations: [override ? { result_id: resultId, ...override } : { result_id: resultId }] } },
      { onSuccess: () => setDismissedResultIds((prev) => new Set(prev).add(resultId)) },
    );
    setPendingFallback(null);
  }

  function startDrag(
    e: React.MouseEvent,
    group: PlanningSessionRecommendationGroup,
    rec: PlanningRecommendationRead,
    day: number,
    startMin: number,
    durationMin: number,
  ) {
    if (!rec.id || !activeRun) return;
    e.preventDefault();
    const organizerTz = organizerTzFor(group.dance_event_id);
    const drag: DragState = {
      runId: activeRun.id,
      rec,
      groupLabel: group.dance_name,
      organizerTz,
      startClientX: e.clientX,
      startClientY: e.clientY,
      origDay: day,
      origStartMin: startMin,
      durationMin,
      moved: false,
      finalDay: day,
      finalStartMin: startMin,
    };
    setDragPreview({ resultId: rec.id, day, startMin });

    function onMove(ev: MouseEvent) {
      const grid = gridRef.current;
      if (!grid) return;
      const rect = grid.getBoundingClientRect();
      const colWidth = rect.width / 7;
      const deltaDay = Math.round((ev.clientX - drag.startClientX) / colWidth);
      const deltaMin = Math.round((ev.clientY - drag.startClientY) / PX_PER_MIN / 15) * 15;
      if (Math.abs(ev.clientX - drag.startClientX) > 5 || Math.abs(ev.clientY - drag.startClientY) > 5) drag.moved = true;
      const newDay = Math.max(0, Math.min(6, drag.origDay + deltaDay));
      const newStartMin = Math.max(DAY_START_MIN, Math.min(DAY_END_MIN - drag.durationMin, drag.origStartMin + deltaMin));
      drag.finalDay = newDay;
      drag.finalStartMin = newStartMin;
      setDragPreview({ resultId: drag.rec.id!, day: newDay, startMin: newStartMin });
    }

    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      setDragPreview(null);
      if (!drag.moved) {
        commitConfirm(drag.runId, drag.rec, drag.groupLabel);
        return;
      }
      const dateStr = dayDateStrings[drag.finalDay];
      const startParts = addMinutesToDateTime(dateStr, drag.finalStartMin);
      const endParts = addMinutesToDateTime(dateStr, drag.finalStartMin + drag.durationMin);
      const startIso = localPartsToIso(startParts.date, startParts.time, drag.organizerTz);
      const endIso = localPartsToIso(endParts.date, endParts.time, drag.organizerTz);
      commitConfirm(drag.runId, drag.rec, drag.groupLabel, { start_at: startIso, end_at: endIso });
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  async function handleSuggestSessions() {
    const targets = (events ?? []).filter((e) => checkedIds.has(e.id) && e.remaining_session_count > 0);
    if (targets.length === 0) {
      toast.error("No checked dances need sessions scheduled.");
      return;
    }
    try {
      const run = await createRun.mutateAsync({
        event_ids: targets.map((e) => e.id),
        horizon_start: weekStart.toISOString(),
        horizon_end: weekEnd.toISOString(),
        slot_step_minutes: 60,
      });
      setActiveRun(run);
      setDismissedResultIds(new Set());
      const count = run.results.filter((g) => g.recommendations.length > 0).length;
      toast.success(count > 0 ? `Found candidate slots for ${count} session(s)` : "No candidate slots found this week");
    } catch {
      // useCreatePlanningRun already toasts the error
    }
  }

  async function handleNewEvent() {
    const target = (events ?? []).find((e) => checkedIds.has(e.id) && e.remaining_session_count > 0);
    if (!target) {
      toast.error("No checked dance needs a new session.");
      return;
    }
    try {
      const run = await createRun.mutateAsync({
        event_ids: [target.id],
        horizon_start: weekStart.toISOString(),
        horizon_end: weekEnd.toISOString(),
        slot_step_minutes: 60,
      });
      const group = run.results[0];
      const rec = group?.recommendations[0];
      if (!rec || !rec.id) {
        toast.error(`No candidate slot found for ${target.name}`);
        return;
      }
      commitConfirm(run.id, rec, target.name);
    } catch {
      // useCreatePlanningRun already toasts the error
    }
  }

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
      const rec = group.recommendations[0];
      if (!rec || !rec.id || dismissedResultIds.has(rec.id)) continue;
      const tz = organizerTzFor(group.dance_event_id);
      const preview = dragPreview?.resultId === rec.id ? dragPreview : null;
      const placement = preview ?? zonedDayAndMinutes(rec.start_at, tz);
      if (!placement) continue;
      const durationMin = Math.round((new Date(rec.end_at).getTime() - new Date(rec.start_at).getTime()) / 60000);
      blocks.push({
        key: `suggested-${rec.id}`,
        day: placement.day,
        startMin: placement.startMin,
        durationMin,
        color: eventColor(group.dance_event_id),
        label: `${group.dance_name} (suggested)`,
        timeLabel: `${fmtHourLabel(placement.startMin).replace(" ", "")}`,
        isFallback: rec.is_fallback,
        tooltip: blockTooltip(rec),
        group,
        rec,
      });
    }
    return blocks;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRun, dismissedResultIds, dragPreview, events, users]);

  const confirmedBlocks = useMemo(() => {
    const blocks: Array<{ key: string; day: number; startMin: number; durationMin: number; color: string; label: string; timeLabel: string }> = [];
    for (const session of overview?.practice_sessions ?? []) {
      const event = eventsById.get(session.dance_event_id);
      if (!event || !checkedIds.has(event.id)) continue;
      const tz = organizerTzFor(session.dance_event_id);
      const placement = zonedDayAndMinutes(session.start_at, tz);
      if (!placement) continue;
      const durationMin = Math.round((new Date(session.end_at).getTime() - new Date(session.start_at).getTime()) / 60000);
      blocks.push({
        key: `confirmed-${session.id}`,
        day: placement.day,
        startMin: placement.startMin,
        durationMin,
        color: eventColor(session.dance_event_id),
        label: event.name,
        timeLabel: fmtHourLabel(placement.startMin),
      });
    }
    return blocks;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overview, eventsById, checkedIds]);

  const hourLabels = Array.from({ length: NUM_HOURS + 1 }, (_, i) => fmtHourLabel(DAY_START_MIN + i * 60));

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex items-start justify-between mb-5">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Dashboard / Calendar</p>
          <h2 className="text-2xl font-bold tracking-tight">Calendar</h2>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-muted-foreground">
              {format(weekStart, "MMM d")} &ndash; {format(weekEnd, "MMM d, yyyy")}
            </p>
            <Button variant="ghost" size="icon" className="size-6" onClick={() => setAnchor((prev) => subWeeks(prev, 1))}>
              <ChevronLeft className="size-3.5" />
            </Button>
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => setAnchor(new Date())}>
              Today
            </Button>
            <Button variant="ghost" size="icon" className="size-6" onClick={() => setAnchor((prev) => addWeeks(prev, 1))}>
              <ChevronRight className="size-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex gap-5 items-start flex-1 min-h-0">
        {panelCollapsed ? (
          <button
            type="button"
            onClick={() => setPanelCollapsed(false)}
            className="shrink-0 size-8 rounded-lg border flex items-center justify-center text-muted-foreground hover:bg-accent/50"
            title="Show dances panel"
          >
            <ChevronRight className="size-4" />
          </button>
        ) : (
          <Card className="w-72 shrink-0 p-5">
            <div className="flex items-center justify-between mb-1">
              <div className="text-base font-bold">Dances</div>
              <button
                type="button"
                onClick={() => setPanelCollapsed(true)}
                className="text-muted-foreground hover:text-foreground text-sm px-1"
                title="Hide panel"
              >
                <ChevronLeft className="size-4" />
              </button>
            </div>
            <p className="text-xs text-muted-foreground mb-3">Choose which dances to show and schedule.</p>

            <div className="flex flex-col gap-2.5 mb-4">
              {(events ?? []).map((eventItem) => (
                <div key={eventItem.id} className="flex items-center gap-2.5">
                  <Checkbox
                    checked={checkedIds.has(eventItem.id)}
                    onCheckedChange={(checked) =>
                      setCheckedIds((prev) => {
                        const next = new Set(prev);
                        if (checked) next.add(eventItem.id);
                        else next.delete(eventItem.id);
                        return next;
                      })
                    }
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
              {(events ?? []).length === 0 && <p className="text-xs text-muted-foreground">No dances yet &mdash; add one on the Events page.</p>}
            </div>

            <Button className="w-full mb-2" variant="secondary" onClick={handleSuggestSessions} disabled={createRun.isPending}>
              <Sparkles className="size-4" /> Suggest sessions
            </Button>
            <Button className="w-full" onClick={handleNewEvent} disabled={createRun.isPending}>
              <Plus className="size-4" /> New event
            </Button>
          </Card>
        )}

        <Card className="flex-1 min-w-0 overflow-x-auto p-0">
          <div className="min-w-[900px]">
            <div className="grid" style={{ gridTemplateColumns: "64px repeat(7,1fr)" }}>
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
                {confirmedBlocks.map((block) => {
                  const top = (block.startMin - DAY_START_MIN) * PX_PER_MIN;
                  const height = block.durationMin * PX_PER_MIN;
                  const widthPct = 100 / 7;
                  return (
                    <div
                      key={block.key}
                      style={{
                        position: "absolute",
                        top,
                        height,
                        left: `calc(${block.day * widthPct}% + 3px)`,
                        width: `calc(${widthPct}% - 6px)`,
                        background: block.color,
                        color: "#fff",
                        borderRadius: 8,
                        padding: "8px 10px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
                        overflow: "hidden",
                        boxSizing: "border-box",
                      }}
                    >
                      <div className="text-xs font-bold truncate">{block.label}</div>
                      <div className="text-[11px] opacity-80 mt-0.5">{block.timeLabel}</div>
                    </div>
                  );
                })}

                {suggestedBlocks.map((block) => {
                  const top = (block.startMin - DAY_START_MIN) * PX_PER_MIN;
                  const height = block.durationMin * PX_PER_MIN;
                  const widthPct = 100 / 7;
                  return (
                    <div
                      key={block.key}
                      title={block.tooltip}
                      onMouseDown={(e) => startDrag(e, block.group, block.rec, block.day, block.startMin, block.durationMin)}
                      style={{
                        position: "absolute",
                        top,
                        height,
                        left: `calc(${block.day * widthPct}% + 3px)`,
                        width: `calc(${widthPct}% - 6px)`,
                        background: "transparent",
                        border: `2px dashed ${block.isFallback ? "#dc2626" : block.color}`,
                        color: block.isFallback ? "#dc2626" : block.color,
                        borderRadius: 8,
                        padding: "8px 10px",
                        cursor: "grab",
                        userSelect: "none",
                        overflow: "hidden",
                        boxSizing: "border-box",
                      }}
                    >
                      <button
                        type="button"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={() => setDismissedResultIds((prev) => new Set(prev).add(block.rec.id!))}
                        className="absolute top-1 right-1 opacity-60 hover:opacity-100"
                        title="Dismiss suggestion"
                      >
                        <X className="size-3" />
                      </button>
                      <div className="text-xs font-bold truncate pr-3">{block.label}</div>
                      <div className="text-[11px] opacity-80 mt-0.5">{block.timeLabel}</div>
                      {block.isFallback && <div className="text-[10px] font-semibold mt-0.5">missing required</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </Card>
      </div>

      <Dialog open={Boolean(pendingFallback)} onOpenChange={(open) => !open && setPendingFallback(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Missing a required participant</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This slot for <strong>{pendingFallback?.label}</strong> is missing one or more required participants.
            Confirm anyway?
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingFallback(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmPendingFallback}>
              Confirm anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
