import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { availabilityApi } from "@/api/endpoints";
import type { AvailabilityCreate } from "@/api/types";
import { errorMessage, queryKeys } from "./query-keys";

export function useAvailability(userId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.availability(userId ?? ""),
    queryFn: () => availabilityApi.list(userId as string),
    enabled: Boolean(userId),
  });
}

export function useCreateAvailability(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AvailabilityCreate) => availabilityApi.create(userId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.availability(userId) });
      toast.success("Availability added");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useDeleteAvailability(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (intervalId: string) => availabilityApi.remove(userId, intervalId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.availability(userId) });
      toast.success("Availability removed");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}
