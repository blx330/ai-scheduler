import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { googleCalendarApi } from "@/api/endpoints";
import type { GoogleBusySyncRequest, GoogleCalendarSelectionUpdate } from "@/api/types";
import { errorMessage, queryKeys } from "./query-keys";

export function useGoogleConnection(userId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.googleConnection(userId ?? ""),
    queryFn: () => googleCalendarApi.connection(userId as string),
    enabled: Boolean(userId),
  });
}

export function useGoogleCalendars(userId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.googleCalendars(userId ?? ""),
    queryFn: () => googleCalendarApi.calendars(userId as string),
    enabled: Boolean(userId) && enabled,
  });
}

export function useStartGoogleAuth() {
  return useMutation({
    mutationFn: (userId: string) => googleCalendarApi.authUrl(userId),
    onSuccess: (data) => {
      window.open(data.authorization_url, "_blank", "noopener,noreferrer");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useSelectGoogleCalendars(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: GoogleCalendarSelectionUpdate) => googleCalendarApi.selectCalendars(userId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.googleConnection(userId) });
      toast.success("Calendar selection saved");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useSyncBusyTime(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: GoogleBusySyncRequest) => googleCalendarApi.syncBusy(userId, body),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["calendar-overview"] });
      toast.success(`Synced ${data.synced_interval_count} busy interval(s)`);
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}
