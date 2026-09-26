import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { calendarApi } from "@/api/endpoints";
import { queryKeys } from "./query-keys";

export function useCalendarOverview(start: string, end: string, userIds: string[] = []) {
  return useQuery({
    queryKey: queryKeys.calendarOverview(start, end, userIds),
    queryFn: () => calendarApi.overview(start, end, userIds),
    // Week changes and member toggles change the key; without this the grid blanks
    // on every fetch instead of keeping the last week visible until the new one lands.
    placeholderData: keepPreviousData,
  });
}
