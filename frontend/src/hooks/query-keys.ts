export const queryKeys = {
  users: ["users"] as const,
  user: (id: string) => ["users", id] as const,
  availability: (userId: string) => ["availability", userId] as const,
  events: ["events"] as const,
  event: (id: string) => ["events", id] as const,
  eventSessions: (id: string) => ["events", id, "sessions"] as const,
  // userIds is part of the key: it changes the response, so leaving it out would serve
  // one member set's data for another's
  calendarOverview: (start: string, end: string, userIds: string[] = []) =>
    ["calendar-overview", start, end, [...userIds].sort().join(",")] as const,
  googleConnection: (userId: string) => ["google-connection", userId] as const,
  googleCalendars: (userId: string) => ["google-calendars", userId] as const,
  health: ["health"] as const,
};

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}
