import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { SessionEditorDialog } from "./SessionEditorDialog";
import type { DanceEventRead, PracticeSessionRead, UserRead } from "@/api/types";

const dance = {
  id: "dance-1",
  name: "Hip Hop Set",
  duration_minutes: 60,
  required_session_count: 2,
} as DanceEventRead;

const session: PracticeSessionRead = {
  id: "session-1",
  dance_event_id: "dance-1",
  session_index: 2,
  start_at: "2026-10-04T22:00:00Z",
  end_at: "2026-10-04T23:00:00Z",
  status: "confirmed",
  room_id: "room-1",
  source_run_id: "run-1",
  total_score: 11,
  google_calendar_event_id: null,
  google_calendar_id: null,
  google_calendar_html_link: "https://calendar.google.com/event?eid=abc",
  is_fallback: false,
  missing_required_user_ids: ["user-9"],
  score_breakdown: {},
  explanation: {
    summary: "Recommended practice with all required participants available.",
    reasons: [{ code: "time_tier_bonus", message: "Evening slot.", score: 6, missing_required_user_ids: [] }],
    missing_required_user_ids: [],
    participant_statuses: [
      { user_id: "user-9", role: "required", available: false, reason: "not_declared", detail: null },
      { user_id: "user-1", role: "required", available: true, reason: null, detail: null },
    ],
  },
};

const usersById = new Map<string, UserRead>([["user-9", { id: "user-9", display_name: "Nina Kowalski" } as UserRead]]);

function renderDialog(overrides: Partial<Parameters<typeof SessionEditorDialog>[0]> = {}) {
  const props = {
    session,
    dance,
    usersById,
    timeZone: "UTC",
    canEdit: true,
    isSaving: false,
    onClose: vi.fn(),
    onSave: vi.fn(),
    onUnschedule: vi.fn(),
    ...overrides,
  };
  render(
    <MemoryRouter>
      <SessionEditorDialog {...props} />
    </MemoryRouter>,
  );
  return props;
}

describe("SessionEditorDialog", () => {
  it("shows the dance, session number, links and who is missing", () => {
    renderDialog();
    expect(screen.getByRole("heading", { name: "Hip Hop Set" })).toBeInTheDocument();
    expect(screen.getByText(/Session 2 of 2/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Google Calendar/ })).toHaveAttribute(
      "href",
      "https://calendar.google.com/event?eid=abc",
    );
    expect(screen.getByRole("link", { name: /Edit dance/ })).toHaveAttribute("href", "/events/dance-1");
    expect(screen.getByText("Nina Kowalski").closest("li")).toHaveTextContent("hasn't declared availability at this time");
  });

  it("saves the edited date and time as instants in the editor's zone, keeping the dance duration", () => {
    const props = renderDialog();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-10-11" } });
    fireEvent.change(screen.getByLabelText(/Start/), { target: { value: "19:30" } });
    expect(screen.getByText(/ends 20:30/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(props.onSave).toHaveBeenCalledWith(session, "2026-10-11T19:30:00.000Z", "2026-10-11T20:30:00.000Z");
  });

  it("arms Unschedule on the first click and only unschedules on the second", () => {
    const props = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /^Unschedule/ }));
    expect(props.onUnschedule).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Really unschedule/ }));
    expect(props.onUnschedule).toHaveBeenCalledWith(session);
  });

  it("is read-only for members", () => {
    renderDialog({ canEdit: false });
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Unschedule/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Date")).toBeDisabled();
  });
});
