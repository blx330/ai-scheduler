import { useState } from "react";
import { CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RecommendationCard } from "@/components/planning/RecommendationCard";
import { RunPlanningForm } from "@/components/planning/RunPlanningForm";
import { useConfirmPlanningRun, useCreatePlanningRun } from "@/hooks/use-planning";
import { useUsers } from "@/hooks/use-users";
import { localPartsToIso } from "@/lib/datetime";
import { guessLocalTimezone } from "@/lib/timezones";
import type { PlanningRunCreate, PlanningRunRead } from "@/api/types";

function groupKey(danceEventId: string, sessionIndex: number): string {
  return `${danceEventId}::${sessionIndex}`;
}

export function PlanningPage() {
  const { data: users } = useUsers();
  const createRun = useCreatePlanningRun();
  const confirmRun = useConfirmPlanningRun();

  const [run, setRun] = useState<PlanningRunRead | null>(null);
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [overrideEnabled, setOverrideEnabled] = useState<Record<string, boolean>>({});
  const [overrideValues, setOverrideValues] = useState<Record<string, { start: string; end: string }>>({});

  const tz = guessLocalTimezone();

  function handleRun(body: PlanningRunCreate) {
    createRun.mutate(body, {
      onSuccess: (data) => {
        setRun(data);
        setSelection({});
        setOverrideEnabled({});
        setOverrideValues({});
      },
    });
  }

  function handleConfirm() {
    if (!run) return;
    const confirmations = Object.entries(selection).map(([key, recommendationId]) => {
      const overrides = overrideEnabled[key] ? overrideValues[key] : undefined;
      if (overrides?.start && overrides?.end) {
        const [startDate, startTime] = overrides.start.split("T");
        const [endDate, endTime] = overrides.end.split("T");
        return {
          result_id: recommendationId,
          start_at: localPartsToIso(startDate, startTime, tz),
          end_at: localPartsToIso(endDate, endTime, tz),
        };
      }
      return { result_id: recommendationId };
    });
    confirmRun.mutate(
      { runId: run.id, body: { confirmations } },
      {
        onSuccess: () => {
          setRun(null);
          setSelection({});
        },
      },
    );
  }

  const selectedCount = Object.keys(selection).length;

  return (
    <div className="space-y-4 max-w-4xl">
      <div>
        <h2 className="text-xl font-semibold">Planning</h2>
        <p className="text-sm text-muted-foreground">
          Run the scheduler over a date horizon, then pick a slot per session and confirm.
        </p>
      </div>

      <RunPlanningForm onRun={handleRun} isPending={createRun.isPending} />

      {run && run.results.length === 0 && (
        <p className="text-sm text-muted-foreground">{run.message ?? "No recommendations were found."}</p>
      )}

      {run && run.results.length > 0 && (
        <div className="space-y-4">
          {run.results.map((group) => {
            const key = groupKey(group.dance_event_id, group.session_index);
            const selectedRecId = selection[key];
            const selectedRec = group.recommendations.find((r) => r.id === selectedRecId);
            return (
              <Card key={key}>
                <CardHeader>
                  <CardTitle>
                    {group.dance_name} &middot; Session {group.session_index + 1}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {group.recommendations.length === 0 && (
                    <p className="text-sm text-muted-foreground">No candidate slots found for this session.</p>
                  )}
                  <div className="grid gap-2 sm:grid-cols-2">
                    {group.recommendations.map((rec) => (
                      <RecommendationCard
                        key={rec.id ?? `${rec.rank}`}
                        recommendation={rec}
                        selected={selectedRecId === rec.id}
                        onSelect={() => {
                          if (!rec.id) return;
                          setSelection((prev) => ({ ...prev, [key]: rec.id! }));
                        }}
                        users={users ?? []}
                      />
                    ))}
                  </div>

                  {selectedRec && (
                    <div className="rounded-md border bg-muted/30 p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id={`override-${key}`}
                          checked={overrideEnabled[key] ?? false}
                          onCheckedChange={(checked) =>
                            setOverrideEnabled((prev) => ({ ...prev, [key]: checked === true }))
                          }
                        />
                        <Label htmlFor={`override-${key}`} className="font-normal">
                          Override exact start/end time
                        </Label>
                      </div>
                      {overrideEnabled[key] && (
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <Label htmlFor={`override-start-${key}`}>Start</Label>
                            <Input
                              id={`override-start-${key}`}
                              type="datetime-local"
                              value={overrideValues[key]?.start ?? ""}
                              onChange={(e) =>
                                setOverrideValues((prev) => ({
                                  ...prev,
                                  [key]: { start: e.target.value, end: prev[key]?.end ?? "" },
                                }))
                              }
                            />
                          </div>
                          <div className="space-y-1">
                            <Label htmlFor={`override-end-${key}`}>End</Label>
                            <Input
                              id={`override-end-${key}`}
                              type="datetime-local"
                              value={overrideValues[key]?.end ?? ""}
                              onChange={(e) =>
                                setOverrideValues((prev) => ({
                                  ...prev,
                                  [key]: { start: prev[key]?.start ?? "", end: e.target.value },
                                }))
                              }
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}

          <div className="flex items-center gap-3">
            <Button onClick={handleConfirm} disabled={selectedCount === 0 || confirmRun.isPending}>
              <CheckCircle2 />
              {confirmRun.isPending ? "Confirming..." : `Confirm ${selectedCount} selected session(s)`}
            </Button>
            {selectedCount > 0 && <Badge variant="secondary">{selectedCount} selected</Badge>}
          </div>
        </div>
      )}
    </div>
  );
}
