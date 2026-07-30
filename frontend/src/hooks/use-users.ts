import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { usersApi } from "@/api/endpoints";
import type { UserCreate, UserUpdate } from "@/api/types";
import { errorMessage, queryKeys } from "./query-keys";

export function useUsers() {
  return useQuery({ queryKey: queryKeys.users, queryFn: usersApi.list });
}

export function useUser(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.user(id ?? ""),
    queryFn: () => usersApi.get(id as string),
    enabled: Boolean(id),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UserCreate) => usersApi.create(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
      toast.success("Member added");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UserUpdate }) => usersApi.update(id, body),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
      void queryClient.invalidateQueries({ queryKey: queryKeys.user(data.id) });
      toast.success("Preferences updated");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => usersApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
      toast.success("Member removed");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
}
