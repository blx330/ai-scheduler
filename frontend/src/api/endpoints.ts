import { api } from "./client";
import type {
  AvailabilityCreate,
  AvailabilityRead,
  CalendarOverviewRead,
  DanceEventCreate,
  DanceEventRead,
  DanceEventUpdate,
  GoogleBusySyncRequest,
  GoogleBusySyncResponse,
  GoogleCalendarConnection,
  GoogleCalendarSelectionUpdate,
  GoogleCalendarSummary,
  GoogleOAuthStartResponse,
  HealthRead,
  PlanningRunConfirmRequest,
  PlanningRunConfirmResponse,
  PlanningRunCreate,
  PlanningRunRead,
  PracticeRescheduleRequest,
  PracticeRescheduleResponse,
  PracticeSessionRead,
  PracticeUnscheduleResponse,
  UserCreate,
  UserRead,
  UserUpdate,
} from "./types";

export const healthApi = {
  get: () => api.get<HealthRead>("/health"),
};

export const usersApi = {
  list: () => api.get<UserRead[]>("/users"),
  get: (id: string) => api.get<UserRead>(`/users/${id}`),
  create: (body: UserCreate) => api.post<UserRead>("/users", body),
  update: (id: string, body: UserUpdate) => api.patch<UserRead>(`/users/${id}`, body),
  remove: (id: string) => api.delete<void>(`/users/${id}`),
};

export const availabilityApi = {
  list: (userId: string) => api.get<AvailabilityRead[]>(`/users/${userId}/availability`),
  create: (userId: string, body: AvailabilityCreate) =>
    api.post<AvailabilityRead>(`/users/${userId}/availability`, body),
  remove: (userId: string, intervalId: string) =>
    api.delete<{ message: string }>(`/users/${userId}/availability/${intervalId}`),
};

export const eventsApi = {
  list: () => api.get<DanceEventRead[]>("/events"),
  create: (body: DanceEventCreate) => api.post<DanceEventRead>("/events", body),
  update: (id: string, body: DanceEventUpdate) => api.patch<DanceEventRead>(`/events/${id}`, body),
  sessions: (id: string) => api.get<PracticeSessionRead[]>(`/events/${id}/sessions`),
};

export const planningApi = {
  create: (body: PlanningRunCreate) => api.post<PlanningRunRead>("/planning-runs", body),
  confirm: (id: string, body: PlanningRunConfirmRequest) =>
    api.post<PlanningRunConfirmResponse>(`/planning-runs/${id}/confirm`, body),
};

export const calendarApi = {
  // Busy intervals are private, so the backend only returns them for the users named
  // here; omitting userIds yields practice sessions alone.
  overview: (start: string, end: string, userIds: string[] = []) => {
    const params = new URLSearchParams({ start, end });
    for (const userId of userIds) params.append("user_ids", userId);
    return api.get<CalendarOverviewRead>(`/calendar/overview?${params.toString()}`);
  },
};

export const practicesApi = {
  unschedule: (practiceId: string) =>
    api.delete<PracticeUnscheduleResponse>(`/practices/${practiceId}/schedule`),
  reschedule: (practiceId: string, body: PracticeRescheduleRequest) =>
    api.patch<PracticeRescheduleResponse>(`/practices/${practiceId}/schedule`, body),
};

export const googleCalendarApi = {
  authUrl: (userId: string) =>
    api.get<GoogleOAuthStartResponse>(`/google-calendar/auth?user_id=${encodeURIComponent(userId)}`),
  connection: (userId: string) => api.get<GoogleCalendarConnection>(`/users/${userId}/google/connection`),
  calendars: (userId: string) => api.get<GoogleCalendarSummary[]>(`/users/${userId}/google/calendars`),
  selectCalendars: (userId: string, body: GoogleCalendarSelectionUpdate) =>
    api.post<GoogleCalendarConnection>(`/users/${userId}/google/calendars/select`, body),
  syncBusy: (userId: string, body: GoogleBusySyncRequest) =>
    api.post<GoogleBusySyncResponse>(`/users/${userId}/google/sync-busy`, body),
};
