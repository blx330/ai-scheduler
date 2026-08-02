import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { planningApi, practicesApi } from "@/api/endpoints";
import type { PlanningRunConfirmRequest, PlanningRunCreate } from "@/api/types";
import { errorMessage, queryKeys } from "./query-keys";

export function useCreatePlanningRun() {
  return useMutation({
    mutationFn: (body: PlanningRunCreate) => planningApi.create(body),
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useConfirmPlanningRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, body }: { runId: string; body: PlanningRunConfirmRequest }) =>
      planningApi.confirm(runId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.events });
      void queryClient.invalidateQueries({ queryKey: ["calendar-overview"] });
      toast.success("Sessions confirmed");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useUnschedulePractice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (practiceId: string) => practicesApi.unschedule(practiceId),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.events });
      void queryClient.invalidateQueries({ queryKey: queryKeys.eventSessions(data.dance_event_id) });
      void queryClient.invalidateQueries({ queryKey: ["calendar-overview"] });
      if (data.warning) {
        toast.warning(data.warning);
      } else {
        toast.success("Session unscheduled");
      }
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}
