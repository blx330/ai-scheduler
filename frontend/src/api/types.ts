export type PreferredPracticeTime = "early_morning" | "mid_morning" | "late_morning";

export interface CachedPracticePreference {
  preferred_days: string[];
  avoid_days: string[];
  earliest_time: string | null;
  latest_time: string | null;
  notes: string | null;
  summary: string | null;
}

export interface UserRead {
  id: string;
  display_name: string;
  timezone: string;
  email: string | null;
  preferred_practice_time: PreferredPracticeTime | null;
  preferred_practice_time_raw: string | null;
  preferred_practice_time_parsed: CachedPracticePreference | null;
  preferred_practice_time_summary: string | null;
  created_at: string;
}

export interface UserCreate {
  display_name: string;
  timezone: string;
  email?: string;
  preferred_practice_time?: PreferredPracticeTime;
  preferred_practice_time_raw?: string;
}

export interface UserUpdate {
  preferred_practice_time?: PreferredPracticeTime | null;
  preferred_practice_time_raw?: string | null;
}

export interface AvailabilityRead {
  id: string;
  user_id: string;
  start_at: string;
  end_at: string;
}

export interface AvailabilityCreate {
  start_at: string;
  end_at: string;
}

export type ParticipantRole = "required" | "optional";

export interface DanceEventParticipant {
  user_id: string;
  role: ParticipantRole;
}

export type DanceEventStatus =
  | "unscheduled"
  | "partially_scheduled"
  | "scheduled"
  | "completed"
  | "archived";

export interface DanceEventRead {
  id: string;
  name: string;
  description: string | null;
  organizer_user_id: string;
  duration_minutes: number;
  earliest_start_date: string | null;
  min_days_apart: number;
  latest_schedule_at: string;
  required_session_count: number;
  confirmed_session_count: number;
  remaining_session_count: number;
  status: DanceEventStatus;
  participants: DanceEventParticipant[];
}

export interface DanceEventCreate {
  name: string;
  description?: string;
  organizer_user_id: string;
  duration_minutes: number;
  earliest_start_date?: string;
  min_days_apart: number;
  latest_schedule_at: string;
  required_session_count: number;
  participants: DanceEventParticipant[];
}

export interface DanceEventUpdate {
  name?: string;
  // nullable: the backend distinguishes "field absent" (leave alone) from an explicit
  // null (clear it), so these must be able to carry null to be clearable at all
  description?: string | null;
  organizer_user_id?: string;
  duration_minutes?: number;
  earliest_start_date?: string | null;
  min_days_apart?: number;
  latest_schedule_at?: string;
  required_session_count?: number;
  status?: DanceEventStatus;
  participants?: DanceEventParticipant[];
}

export interface PlanningExplanationReason {
  code: string;
  message: string;
  score: number | null;
  missing_required_user_ids: string[];
}

export interface PlanningExplanation {
  summary: string;
  reasons: PlanningExplanationReason[];
  missing_required_user_ids: string[];
}

export interface PlanningParticipantStatus {
  user_id: string;
  role: ParticipantRole;
  available: boolean;
}

export interface PlanningRecommendationRead {
  id: string | null;
  dance_event_id: string;
  dance_name: string;
  session_index: number;
  rank: number;
  room_id: string;
  start_at: string;
  end_at: string;
  total_score: number;
  score_breakdown: Record<string, number>;
  explanation: PlanningExplanation;
  is_fallback: boolean;
  missing_required_user_ids: string[];
  optional_available_count: number;
  participant_statuses: PlanningParticipantStatus[];
}

export interface PlanningSessionRecommendationGroup {
  dance_event_id: string;
  dance_name: string;
  session_index: number;
  recommendations: PlanningRecommendationRead[];
}

export type PlanningRunStatus = "completed" | "no_results";

export interface PlanningRunRead {
  id: string;
  room_id: string;
  status: PlanningRunStatus;
  message: string | null;
  horizon_start: string;
  horizon_end: string;
  slot_step_minutes: number;
  event_ids: string[];
  results: PlanningSessionRecommendationGroup[];
}

export interface PlanningRunCreate {
  event_ids: string[];
  horizon_start: string;
  horizon_end: string;
  slot_step_minutes: number;
  room_id?: string;
}

export type PlanningResultConfirmation =
  | { result_id: string; start_at?: undefined; end_at?: undefined }
  | { result_id: string; start_at: string; end_at: string };

export interface PlanningRunConfirmRequest {
  confirmations: PlanningResultConfirmation[];
}

export type PracticeSessionStatus = string;

export interface PracticeSessionRead {
  id: string;
  dance_event_id: string;
  session_index: number;
  start_at: string;
  end_at: string;
  status: PracticeSessionStatus;
  room_id: string;
  source_run_id: string | null;
  total_score: number | null;
  google_calendar_event_id: string | null;
  google_calendar_id: string | null;
  google_calendar_html_link: string | null;
  is_fallback: boolean;
  missing_required_user_ids: string[];
  score_breakdown: Record<string, number>;
  explanation: PlanningExplanation;
}

export interface PlanningRunConfirmResponse {
  planning_run_id: string;
  confirmed_sessions: PracticeSessionRead[];
  /** Non-fatal problems, e.g. the session was confirmed but not pushed to Google Calendar. */
  warnings: string[];
}

export interface CalendarBusyInterval {
  id: string;
  user_id: string;
  start_at: string;
  end_at: string;
}

export interface CalendarOverviewRead {
  start_at: string;
  end_at: string;
  busy_intervals: CalendarBusyInterval[];
  practice_sessions: PracticeSessionRead[];
}

export interface PracticeUnscheduleResponse {
  practice_id: string;
  dance_event_id: string;
  unscheduled: boolean;
  google_event_deleted: boolean;
  warning: string | null;
}

export interface GoogleOAuthStartResponse {
  authorization_url: string;
}

export interface GoogleCalendarSummary {
  id: string;
  summary: string;
  primary: boolean;
  access_role: string;
  time_zone: string | null;
}

export interface GoogleCalendarConnection {
  user_id: string;
  connected: boolean;
  status: string;
  account_email: string | null;
  selected_busy_calendar_ids: string[];
  selected_write_calendar_id: string | null;
  token_expires_at: string | null;
}

export interface GoogleCalendarSelectionUpdate {
  busy_calendar_ids: string[];
  write_calendar_id?: string;
}

export interface GoogleBusySyncRequest {
  horizon_start: string;
  horizon_end: string;
}

export interface GoogleBusySyncResponse {
  user_id: string;
  synced_interval_count: number;
  calendar_ids: string[];
}

export interface ApiErrorBody {
  detail: string;
}
