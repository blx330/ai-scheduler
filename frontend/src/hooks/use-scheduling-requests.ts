import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { schedulingRequestsApi } from "@/api/endpoints";
import type { SchedulingProposal } from "@/api/types";
import { queryKeys } from "./query-keys";

// Errors are rendered inline by the panel (every rejection reason, not just the
// first), so these mutations deliberately don't toast on failure.
export function useParseSchedulingRequest() {
  return useMutation({
    mutationFn: (text: string) => schedulingRequestsApi.parse(text),
  });
}

export function useConfirmSchedulingRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proposal: SchedulingProposal) => schedulingRequestsApi.confirm(proposal),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.events });
      toast.success("Constraints saved and planning run finished");
    },
  });
}

export interface RequestErrorDetail {
  message: string;
  errors: string[];
}

export function requestErrorDetail(error: unknown): RequestErrorDetail {
  if (error instanceof ApiError && error.detail && typeof error.detail === "object" && "errors" in error.detail) {
    return { message: error.detail.message, errors: error.detail.errors };
  }
  return { message: error instanceof Error ? error.message : "Something went wrong", errors: [] };
}
