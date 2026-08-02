import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { eventsApi } from "@/api/endpoints";
import type { DanceEventCreate, DanceEventUpdate } from "@/api/types";
import { errorMessage, queryKeys } from "./query-keys";

export function useEvents() {
  return useQuery({ queryKey: queryKeys.events, queryFn: eventsApi.list });
}

export function useEventSessions(eventId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.eventSessions(eventId ?? ""),
    queryFn: () => eventsApi.sessions(eventId as string),
    enabled: Boolean(eventId),
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DanceEventCreate) => eventsApi.create(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.events });
      toast.success("Event created");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useUpdateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: DanceEventUpdate }) => eventsApi.update(id, body),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.events });
      void queryClient.invalidateQueries({ queryKey: queryKeys.event(data.id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.eventSessions(data.id) });
      toast.success("Event updated");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}
