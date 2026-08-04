import { useQuery } from "@tanstack/react-query";

import { healthApi } from "@/api/endpoints";
import { queryKeys } from "./query-keys";

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: healthApi.get, staleTime: 5 * 60 * 1000 });
}
