import { useEffect, useMemo, useRef, useState } from "react";
import { addDays, addWeeks, endOfWeek, format, startOfWeek, subWeeks } from "date-fns";
import { ChevronLeft, ChevronRight, Pencil } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError } from "@/api/client";
import { DancesPanel } from "@/components/calendar/DancesPanel";
import { MembersPanel } from "@/components/calendar/MembersPanel";
import { WeekGrid } from "@/components/calendar/WeekGrid";
import { FallbackConfirmDialog, type PendingFallback } from "@/components/calendar/FallbackConfirmDialog";
import { RescheduleConflictDialog, type PendingReschedule } from "@/components/calendar/RescheduleConflictDialog";
import { useBlockDrag } from "@/hooks/use-block-drag";
import { useCalendarOverview } from "@/hooks/use-calendar";
import { useEvents } from "@/hooks/use-events";
import { useConfirmPlanningRun, useCreatePlanningRun, useReschedulePractice } from "@/hooks/use-planning";
import { useUsers } from "@/hooks/use-users";
import { errorMessage } from "@/hooks/query-keys";
import { DAY_END_MIN, DAY_START_MIN, PX_PER_MIN, addMinutesToDateTime, GRID_TIME_ZONE, planningHorizonStart } from "@/lib/calendarGrid";
import { buildMemberColorMap } from "@/lib/userColor";
import { localPartsToIso } from "@/lib/datetime";
import type {
  PlanningRecommendationRead,
  PlanningRunRead,
  PlanningSessionRecommendationGroup,
  PracticeSessionRead,
} from "@/api/types";

export function CalendarPage() {
  const { data: events, isError: eventsError } = useEvents();
  const { data: users } = useUsers();
  const createRun = useCreatePlanningRun();
  const confirmRun = useConfirmPlanningRun();
  const reschedulePractice = useReschedulePractice();

  const [anchor, setAnchor] = useState(() => new Date());
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [visibleMemberIds, setVisibleMemberIds] = useState<Set<string>>(new Set());
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [activeRun, setActiveRun] = useState<PlanningRunRead | null>(null);
  const [dismissedResultIds, setDismissedResultIds] = useState<Set<string>>(new Set());
  const [pendingFallback, setPendingFallback] = useState<PendingFallback | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [pendingReschedule, setPendingReschedule] = useState<PendingReschedule | null>(null);

  const gridRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { dragPreview, setDragPreview, beginBlockDrag } = useBlockDrag({
    gridRef,
    pxPerMin: PX_PER_MIN,
    dayStartMin: DAY_START_MIN,
    dayEndMin: DAY_END_MIN,
  });

  // Ids we have already offered a default for. Without this, "absent from checkedIds"
  // was indistinguishable from "deliberately unchecked", so every refetch (window
  // focus, any confirm) silently re-checked everything the user had hidden.
  const autoCheckedIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!events) return;
    const liveIds = new Set(events.map((e) => e.id));
    const newIds = events.filter((e) => !autoCheckedIds.current.has(e.id)).map((e) => e.id);
    for (const id of newIds) autoCheckedIds.current.add(id);
    for (const id of [...autoCheckedIds.current]) {
      if (!liveIds.has(id)) autoCheckedIds.current.delete(id);
    }

    setCheckedIds((prev) => {
      const next = new Set<string>();
      for (const id of prev) if (liveIds.has(id)) next.add(id); // drop deleted events
      for (const id of newIds) next.add(id); // default new events to checked
      const unchanged = next.size === prev.size && [...next].every((id) => prev.has(id));
      return unchanged ? prev : next;
    });
  }, [events]);

  // Same "don't silently re-check what was deliberately hidden" problem as
  // autoCheckedIds above, but for members in the new visibility panel.
  const autoVisibleMemberIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!users) return;
    const liveIds = new Set(users.map((u) => u.id));
    const newIds = users.filter((u) => !autoVisibleMemberIds.current.has(u.id)).map((u) => u.id);
    for (const id of newIds) autoVisibleMemberIds.current.add(id);
    for (const id of [...autoVisibleMemberIds.current]) {
      if (!liveIds.has(id)) autoVisibleMemberIds.current.delete(id);
    }

    setVisibleMemberIds((prev) => {
      const next = new Set<string>();
      for (const id of prev) if (liveIds.has(id)) next.add(id); // drop deleted members
      for (const id of newIds) next.add(id); // default new members to visible
      const unchanged = next.size === prev.size && [...next].every((id) => prev.has(id));
      return unchanged ? prev : next;
    });
  }, [users]);

  const weekStart = useMemo(() => startOfWeek(anchor, { weekStartsOn: 1 }), [anchor]);
  const weekEnd = useMemo(() => endOfWeek(anchor, { weekStartsOn: 1 }), [anchor]);
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);
  const dayDateStrings = useMemo(() => days.map((d) => format(d, "yyyy-MM-dd")), [days]);

  // Opening on midnight would bury working hours below a wall of empty night
  // rows, so scroll to ~7 AM by default the way Google Calendar does.
  useEffect(() => {
    scrollContainerRef.current?.scrollTo({ top: 7 * 60 * PX_PER_MIN });
  }, [weekStart]);

  // Busy time only for members toggled visible in the Members panel -- that panel
  // is the sole control over whose calendar is fetched/shown, independent of which
  // dances are checked.
  const visibleMemberIdList = useMemo(() => [...visibleMemberIds].sort(), [visibleMemberIds]);

  const { data: overview, isError: overviewError } = useCalendarOverview(
    weekStart.toISOString(),
    weekEnd.toISOString(),
    visibleMemberIdList,
  );
  // An empty grid is indistinguishable from a backend outage without this.
  const loadError = eventsError || overviewError;

  const eventsById = useMemo(() => new Map((events ?? []).map((e) => [e.id, e])), [events]);
  const usersById = useMemo(() => new Map((users ?? []).map((u) => [u.id, u])), [users]);
  const memberColorMap = useMemo(() => buildMemberColorMap((users ?? []).map((u) => u.id)), [users]);

  function commitConfirm(
    runId: string,
    rec: PlanningRecommendationRead,
    label: string,
    override?: { start_at: string; end_at: string },
  ) {
    if (!rec.id) return;
    // The confirm round-trip also writes to Google Calendar and shows no immediate
    // visual change, so without this an impatient second click double-submits.
    if (confirmRun.isPending) return;
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
    const runId = activeRun.id;
    const recId = rec.id;
    beginBlockDrag(e, "suggested", recId, day, startMin, durationMin, (finalDay, finalStartMin, moved) => {
      setDragPreview(null);
      if (!moved) {
        commitConfirm(runId, rec, group.dance_name);
        return;
      }
      const dateStr = dayDateStrings[finalDay];
      const startParts = addMinutesToDateTime(dateStr, finalStartMin);
      const endParts = addMinutesToDateTime(dateStr, finalStartMin + durationMin);
      // Grid coordinates are in the viewer's timezone (see WeekGrid/gridPlacement), so
      // they must be converted back from it -- using the organizer's timezone here made
      // a dropped block land at a different instant than the one it was dropped on.
      const startIso = localPartsToIso(startParts.date, startParts.time, GRID_TIME_ZONE);
      const endIso = localPartsToIso(endParts.date, endParts.time, GRID_TIME_ZONE);
      commitConfirm(runId, rec, group.dance_name, { start_at: startIso, end_at: endIso });
    });
  }

  function startConfirmedDrag(
    e: React.MouseEvent,
    session: PracticeSessionRead,
    day: number,
    startMin: number,
    durationMin: number,
  ) {
    beginBlockDrag(e, "confirmed", session.id, day, startMin, durationMin, (finalDay, finalStartMin, moved) => {
      if (!moved) {
        setDragPreview(null);
        return;
      }
      const dateStr = dayDateStrings[finalDay];
      const startParts = addMinutesToDateTime(dateStr, finalStartMin);
      const endParts = addMinutesToDateTime(dateStr, finalStartMin + durationMin);
      const startIso = localPartsToIso(startParts.date, startParts.time, GRID_TIME_ZONE);
      const endIso = localPartsToIso(endParts.date, endParts.time, GRID_TIME_ZONE);
      attemptReschedule(session, startIso, endIso);
    });
  }

  function attemptReschedule(session: PracticeSessionRead, startIso: string, endIso: string, override = false) {
    reschedulePractice.mutate(
      { practiceId: session.id, body: { start_at: startIso, end_at: endIso, override_conflicts: override } },
      {
        onSuccess: () => {
          setDragPreview(null);
          setPendingReschedule(null);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409 && error.detail && typeof error.detail === "object") {
            // Keep the drag preview showing the dropped position while the dialog is
            // open, so the block doesn't jump back until the user actually cancels.
            setPendingReschedule({ session, startIso, endIso, conflict: error.detail });
            return;
          }
          setDragPreview(null);
          setPendingReschedule(null);
          toast.error(errorMessage(error));
        },
      },
    );
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
        horizon_start: planningHorizonStart(weekStart).toISOString(),
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
        horizon_start: planningHorizonStart(weekStart).toISOString(),
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

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {loadError && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
          <p className="text-sm text-destructive">
            Could not load calendar data, so this week may be incomplete. Check that the API is
            running, then reload.
          </p>
        </div>
      )}
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
        <Button variant={editMode ? "default" : "outline"} size="sm" onClick={() => setEditMode((prev) => !prev)}>
          <Pencil className="size-4" /> {editMode ? "Done editing" : "Edit calendar"}
        </Button>
      </div>

      <div className="flex gap-5 items-start flex-1 min-h-0">
        {panelCollapsed ? (
          <button
            type="button"
            onClick={() => setPanelCollapsed(false)}
            className="shrink-0 size-8 rounded-lg border flex items-center justify-center text-muted-foreground hover:bg-accent/50"
            title="Show sidebar"
          >
            <ChevronRight className="size-4" />
          </button>
        ) : (
          <div className="flex flex-col gap-5 w-72 shrink-0">
            <DancesPanel
              events={events ?? []}
              checkedIds={checkedIds}
              onToggleChecked={(eventId, checked) =>
                setCheckedIds((prev) => {
                  const next = new Set(prev);
                  if (checked) next.add(eventId);
                  else next.delete(eventId);
                  return next;
                })
              }
              onCollapse={() => setPanelCollapsed(true)}
              onSuggestSessions={handleSuggestSessions}
              onNewEvent={handleNewEvent}
              isPending={createRun.isPending}
            />
            <MembersPanel
              users={users ?? []}
              visibleMemberIds={visibleMemberIds}
              onToggleVisible={(userId, visible) =>
                setVisibleMemberIds((prev) => {
                  const next = new Set(prev);
                  if (visible) next.add(userId);
                  else next.delete(userId);
                  return next;
                })
              }
              memberColorMap={memberColorMap}
            />
          </div>
        )}

        <Card className="flex-1 min-w-0 self-stretch flex flex-col min-h-0 overflow-hidden p-0">
          <WeekGrid
            days={days}
            dayDateStrings={dayDateStrings}
            overview={overview}
            eventsById={eventsById}
            usersById={usersById}
            checkedIds={checkedIds}
            visibleMemberIds={visibleMemberIds}
            memberColorMap={memberColorMap}
            activeRun={activeRun}
            dismissedResultIds={dismissedResultIds}
            dragPreview={dragPreview}
            editMode={editMode}
            gridRef={gridRef}
            scrollContainerRef={scrollContainerRef}
            onStartSuggestedDrag={startDrag}
            onStartConfirmedDrag={startConfirmedDrag}
            onDismissSuggestion={(recId) => setDismissedResultIds((prev) => new Set(prev).add(recId))}
          />
        </Card>
      </div>

      <FallbackConfirmDialog
        pendingFallback={pendingFallback}
        onCancel={() => setPendingFallback(null)}
        onConfirm={confirmPendingFallback}
      />

      <RescheduleConflictDialog
        pendingReschedule={pendingReschedule}
        onCancel={() => {
          setPendingReschedule(null);
          setDragPreview(null);
        }}
        onConfirmAnyway={() =>
          pendingReschedule &&
          attemptReschedule(pendingReschedule.session, pendingReschedule.startIso, pendingReschedule.endIso, true)
        }
      />
    </div>
  );
}
