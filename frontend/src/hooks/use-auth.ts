import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/client";
import { authApi } from "@/api/endpoints";
import type { CurrentUserRead } from "@/api/types";
import { queryKeys } from "./query-keys";

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.currentUser,
    queryFn: async (): Promise<CurrentUserRead | null> => {
      try {
        return await authApi.me();
      } catch (error) {
        // Not signed in isn't a fetch failure -- it's the expected state before login.
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.clear();
      window.location.href = "/";
    },
  });
}
