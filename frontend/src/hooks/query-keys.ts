export const queryKeys = {
  users: ["users"] as const,
  user: (id: string) => ["users", id] as const,
  availability: (userId: string) => ["availability", userId] as const,
  events: ["events"] as const,
  event: (id: string) => ["events", id] as const,
  eventSessions: (id: string) => ["events", id, "sessions"] as const,
  planningRun: (id: string) => ["planning-runs", id] as const,
  calendarOverview: (start: string, end: string) => ["calendar-overview", start, end] as const,
  googleConnection: (userId: string) => ["google-connection", userId] as const,
  googleCalendars: (userId: string) => ["google-calendars", userId] as const,
};

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}
