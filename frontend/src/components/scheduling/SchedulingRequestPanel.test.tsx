import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { schedulingRequestsApi } from "@/api/endpoints";
import type { PlanningRunRead, SchedulingRequestReview } from "@/api/types";
import { SchedulingRequestPanel } from "./SchedulingRequestPanel";

vi.mock("@/api/endpoints", () => ({
  schedulingRequestsApi: { parse: vi.fn(), confirm: vi.fn() },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));

const parse = vi.mocked(schedulingRequestsApi.parse);
const confirm = vi.mocked(schedulingRequestsApi.confirm);

const REVIEW: SchedulingRequestReview = {
  request_text: "Schedule 3 Hip Hop rehearsals before Oct 20",
  proposal: {
    event_id: "e1",
    session_count: 3,
    earliest_date: null,
    latest_date: "2026-10-19",
    min_days_apart: 2,
    participants: [
      { user_id: "u1", role: "required" },
      { user_id: "u2", role: "required" },
    ],
    allowed_weekdays: [],
    blocked_weekdays: ["FRI"],
    earliest_start_time: null,
    latest_end_time: null,
    room_id: "r1",
  },
  event: {
    id: "e1",
    name: "Hip Hop",
    organizer_timezone: "America/New_York",
    duration_minutes: 60,
    confirmed_session_count: 0,
  },
  room: { id: "r1", name: "Studio B" },
  participants: [
    { user_id: "u2", display_name: "Jordan Lee", role: "required", change: "added" },
    { user_id: "u1", display_name: "Maya Chen", role: "required", change: "unchanged" },
  ],
  changes: [
    { field: "session_count", label: "Total sessions", before: "1", after: "3" },
    { field: "blocked_weekdays", label: "Blocked days", before: "none", after: "FRI" },
  ],
  sessions_to_plan: 3,
  notes: ["Slots where every required dancer can attend are always tried first."],
};

const RUN = { id: "run1", results: [] } as unknown as PlanningRunRead;

function renderPanel(onPlanned = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SchedulingRequestPanel onPlanned={onPlanned} />
    </QueryClientProvider>,
  );
  return { onPlanned, user: userEvent.setup() };
}

async function submit(user: ReturnType<typeof userEvent.setup>, text = REVIEW.request_text) {
  await user.type(screen.getByLabelText(/describe what to schedule/i), text);
  await user.click(screen.getByRole("button", { name: /review/i }));
}

describe("SchedulingRequestPanel", () => {
  beforeEach(() => {
    parse.mockReset();
    confirm.mockReset();
  });

  it("disables review until something is typed", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: /review/i })).toBeDisabled();
  });

  it("shows the parsed constraints for review without planning anything", async () => {
    parse.mockResolvedValue(REVIEW);
    const { user } = renderPanel();

    await submit(user);

    expect(parse).toHaveBeenCalledWith(REVIEW.request_text);
    const review = await screen.findByRole("region", { name: /review: hip hop/i });
    expect(within(review).getByText("Total sessions")).toBeInTheDocument();
    expect(within(review).getByText("1")).toBeInTheDocument();
    expect(within(review).getByText("3")).toBeInTheDocument();
    expect(within(review).getByText("Studio B")).toBeInTheDocument();
    expect(within(review).getByText("Jordan Lee")).toBeInTheDocument();
    expect(within(review).getByText("added")).toBeInTheDocument();
    expect(within(review).getByText(/3 sessions to plan/i)).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
  });

  it("runs the planner only after confirmation, sending the reviewed proposal", async () => {
    parse.mockResolvedValue(REVIEW);
    confirm.mockResolvedValue({ event_id: "e1", planning_run: RUN });
    const { user, onPlanned } = renderPanel();

    await submit(user);
    await user.click(await screen.findByRole("button", { name: /confirm & plan/i }));

    expect(confirm).toHaveBeenCalledWith(REVIEW.proposal);
    expect(onPlanned).toHaveBeenCalledWith(RUN);
  });

  it("lists every rejection reason instead of a partial result", async () => {
    parse.mockRejectedValue(
      new ApiError(422, "Nothing was changed. The request doesn't match this team's data.", {
        message: "Nothing was changed. The request doesn't match this team's data.",
        errors: ['Unknown member "Maia".', 'Unknown room "Studio Z".'],
      }),
    );
    const { user } = renderPanel();

    await submit(user, "Hip Hop with Maia in Studio Z");

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/nothing was changed/i)).toBeInTheDocument();
    expect(within(alert).getByText('Unknown member "Maia".')).toBeInTheDocument();
    expect(within(alert).getByText('Unknown room "Studio Z".')).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /confirm & plan/i })).not.toBeInTheDocument();
  });

  it("shows the configuration error when parsing is unavailable", async () => {
    parse.mockRejectedValue(
      new ApiError(503, "needs GEMINI_API_KEY", { message: "needs GEMINI_API_KEY", errors: [] }),
    );
    const { user } = renderPanel();

    await submit(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("needs GEMINI_API_KEY");
  });

  it("goes back to editing with the text preserved", async () => {
    parse.mockResolvedValue(REVIEW);
    const { user } = renderPanel();

    await submit(user);
    await user.click(await screen.findByRole("button", { name: /edit request/i }));

    expect(screen.getByLabelText(/describe what to schedule/i)).toHaveValue(REVIEW.request_text);
    expect(confirm).not.toHaveBeenCalled();
  });
});
