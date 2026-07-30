import { useQuery } from "@tanstack/react-query";

import { calendarApi } from "@/api/endpoints";
import { queryKeys } from "./query-keys";

export function useCalendarOverview(start: string, end: string) {
  return useQuery({
    queryKey: queryKeys.calendarOverview(start, end),
    queryFn: () => calendarApi.overview(start, end),
  });
}
