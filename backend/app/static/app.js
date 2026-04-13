const PARTICIPANT_COLORS = [
  "#d9c8ff",
  "#cfe3ff",
  "#ffd7df",
  "#d2f3df",
  "#fde7c2",
  "#d7edf8",
  "#f8d6ef",
  "#e4f3c7",
];

const GRID_START_HOUR = 7;
const GRID_END_HOUR = 24;
const HOUR_ROW_HEIGHT = 72;
const TOTAL_GRID_MINUTES = (GRID_END_HOUR - GRID_START_HOUR) * 60;
const DEFAULT_ROOM_LABEL = "Not set";

const state = {
  users: [],
  connections: {},
  calendars: {},
  events: [],
  eventSessions: {},
  planningRun: null,
  calendarOverview: {
    busy_intervals: [],
    practice_sessions: [],
  },
  weekStart: startOfWeek(new Date()),
  selectedDanceId: null,
  expandedDanceIds: {},
  participantVisibility: {},
  activePracticeKey: null,
  selectedSuggestionId: null,
  slotDrafts: {},
  sessionLocationOverrides: {},
  confirmedSessionDrafts: {},
  editingDanceId: null,
  focusedSettingsUserId: null,
  focusedSettingsForm: false,
  confirmedEditMode: false,
  isRefreshing: false,
  dragState: null,
  justFinishedDrag: false,
  flashTimeoutId: null,
};

const flash = document.getElementById("flash");
const headerWeekRange = document.getElementById("header-week-range");
const selectedDancePill = document.getElementById("selected-dance-pill");
const connectionBadge = document.getElementById("connection-badge");
const connectionBadgeText = document.getElementById("connection-badge-text");
const refreshDashboardButton = document.getElementById("refresh-dashboard");
const calendarSubtitle = document.getElementById("calendar-subtitle");
const calendarEditNote = document.getElementById("calendar-edit-note");

const dancesList = document.getElementById("dances-list");
const participantsList = document.getElementById("participants-list");
const selectedDanceSummary = document.getElementById("selected-dance-summary");
const schedulePracticeButton = document.getElementById("schedule-practice");
const schedulePracticeHint = document.getElementById("schedule-practice-hint");
const suggestedSlots = document.getElementById("suggested-slots");
const selectedSlotSection = document.getElementById("selected-slot-section");
const selectedSlotEditor = document.getElementById("selected-slot-editor");
const selectedSlotNote = document.getElementById("selected-slot-note");
const confirmSlotButton = document.getElementById("confirm-slot");

const calendar = document.getElementById("calendar");
const calendarScroll = document.getElementById("calendar-scroll");
const confirmedEditToggle = document.getElementById("confirmed-edit-toggle");

const modalOverlay = document.getElementById("modal-overlay");
const settingsModal = document.getElementById("settings-modal");
const danceModal = document.getElementById("add-dance-modal");
const usersList = document.getElementById("users-list");
const userForm = document.getElementById("user-form");
const timezoneInput = document.getElementById("timezone");
const addDanceForm = document.getElementById("add-dance-form");
const addDanceParticipants = document.getElementById("add-dance-participants");
const addDanceError = document.getElementById("add-dance-error");
const danceModalEyebrow = document.getElementById("dance-modal-eyebrow");
const danceModalTitle = document.getElementById("dance-modal-title");
const danceModalSubtitle = document.getElementById("dance-modal-subtitle");
const submitDanceButton = document.getElementById("submit-add-dance");

bindStaticListeners();
initialize();

async function initialize() {
  timezoneInput.value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  setDefaultDanceDeadline();
  showCallbackMessage();

  try {
    await refreshDashboard();
  } catch (error) {
    showFlash(error.message, true);
  }
}

function bindStaticListeners() {
  document.getElementById("open-settings").addEventListener("click", () => openSettingsModal());
  document.getElementById("open-manage-people").addEventListener("click", () => openSettingsModal());
  document.getElementById("open-add-participant").addEventListener("click", () => openSettingsModal({ focusForm: true }));
  document.getElementById("open-add-dance").addEventListener("click", openCreateDanceModal);
  document.getElementById("close-settings-modal").addEventListener("click", closeModals);
  document.getElementById("close-add-dance").addEventListener("click", closeModals);
  document.getElementById("cancel-add-dance").addEventListener("click", closeModals);
  modalOverlay.addEventListener("click", closeModals);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModals();
    }
  });

  refreshDashboardButton.addEventListener("click", async () => {
    try {
      await refreshDashboard();
      showFlash("Dashboard refreshed.");
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  document.getElementById("week-prev").addEventListener("click", () => moveWeek(-7));
  document.getElementById("week-today").addEventListener("click", async () => {
    state.weekStart = startOfWeek(new Date());
    await safeRefreshSchedulerData();
  });
  document.getElementById("week-next").addEventListener("click", () => moveWeek(7));

  confirmedEditToggle.addEventListener("change", () => {
    state.confirmedEditMode = confirmedEditToggle.checked;
    calendarEditNote.classList.toggle("hidden", !state.confirmedEditMode);
    renderCalendar();
  });

  userForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await createUser();
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  addDanceForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await submitDanceForm();
    } catch (error) {
      showInlineError(addDanceError, error.message);
    }
  });

  dancesList.addEventListener("click", async (event) => {
    const toggleButton = event.target.closest("[data-dance-toggle]");
    if (toggleButton) {
      const danceId = toggleButton.dataset.danceToggle;
      state.expandedDanceIds[danceId] = !state.expandedDanceIds[danceId];
      renderSidebar();
      return;
    }

    const editButton = event.target.closest("[data-dance-edit]");
    if (editButton) {
      openEditDanceModal(editButton.dataset.danceEdit);
      return;
    }

    const practiceButton = event.target.closest("[data-practice-select]");
    if (practiceButton) {
      const danceId = practiceButton.dataset.danceId;
      const sessionIndex = Number(practiceButton.dataset.practiceSelect);
      selectDance(danceId, { sessionIndex, keepSuggestion: false });
      return;
    }

    const danceButton = event.target.closest("[data-dance-select]");
    if (danceButton) {
      selectDance(danceButton.dataset.danceSelect, { keepSuggestion: false });
    }
  });

  participantsList.addEventListener("click", (event) => {
    const visibilityButton = event.target.closest("[data-toggle-visibility]");
    if (visibilityButton) {
      const userId = visibilityButton.dataset.toggleVisibility;
      state.participantVisibility[userId] = state.participantVisibility[userId] === false;
      renderCalendar();
      renderParticipants();
      return;
    }

    const manageButton = event.target.closest("[data-manage-user]");
    if (manageButton) {
      openSettingsModal({ focusUserId: manageButton.dataset.manageUser });
    }
  });

  usersList.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-user-action]");
    if (!actionButton) {
      return;
    }

    const { userAction, userId } = actionButton.dataset;
    if (!userAction || !userId) {
      return;
    }

    try {
      if (userAction === "connect") {
        await beginGoogleOauth(userId);
        return;
      }
      if (userAction === "refresh-calendars") {
        await refreshCalendars(userId);
        showFlash("Calendars loaded.");
        return;
      }
      if (userAction === "save-calendars") {
        await saveCalendarSelection(userId);
        showFlash("Calendar selection saved.");
        return;
      }
      if (userAction === "sync-busy") {
        const result = await syncBusyForUser(userId);
        await safeRefreshSchedulerData();
        showFlash(`Synced ${result.synced_interval_count} busy intervals for the visible week.`);
      }
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  // Make rebinding safe if initialization happens more than once.
  schedulePracticeButton.removeEventListener("click", handleSchedulePracticeClick);
  schedulePracticeButton.addEventListener("click", handleSchedulePracticeClick);

  suggestedSlots.addEventListener("click", (event) => {
    const button = event.target.closest("[data-select-suggestion]");
    if (!button) {
      return;
    }
    selectSuggestion(button.dataset.selectSuggestion);
  });

  selectedSlotEditor.addEventListener("input", handleSlotEditorChange);
  selectedSlotEditor.addEventListener("change", handleSlotEditorChange);

  confirmSlotButton.addEventListener("click", async () => {
    try {
      await confirmSelectedSlot();
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  calendar.addEventListener("click", (event) => {
    if (state.justFinishedDrag) {
      state.justFinishedDrag = false;
      return;
    }

    const suggestionBlock = event.target.closest("[data-ghost-id]");
    if (suggestionBlock) {
      selectSuggestion(suggestionBlock.dataset.ghostId);
    }
  });

  calendar.addEventListener("pointerdown", handleCalendarPointerDown);
  document.addEventListener("pointermove", handleGlobalPointerMove);
  document.addEventListener("pointerup", handleGlobalPointerUp);
}

async function moveWeek(offsetDays) {
  state.weekStart = addDays(state.weekStart, offsetDays);
  await safeRefreshSchedulerData();
}

async function safeRefreshSchedulerData() {
  try {
    await refreshSchedulerData();
  } catch (error) {
    showFlash(error.message, true);
  }
}

async function refreshDashboard() {
  state.isRefreshing = true;
  updateRefreshButton();
  try {
    await refreshUsers();
    await refreshSchedulerData();
  } finally {
    state.isRefreshing = false;
    updateRefreshButton();
  }
}

async function refreshUsers() {
  state.users = await apiFetch("/users");
  mergeParticipantVisibility();

  await Promise.all(
    state.users.map(async (user) => {
      try {
        state.connections[user.id] = await apiFetch(`/users/${user.id}/google/connection`);
      } catch (_error) {
        state.connections[user.id] = {
          connected: false,
          status: "disconnected",
          account_email: null,
          selected_busy_calendar_ids: [],
          selected_write_calendar_id: null,
        };
      }

      if (state.connections[user.id]?.connected) {
        try {
          state.calendars[user.id] = await apiFetch(`/users/${user.id}/google/calendars`);
        } catch (_error) {
          state.calendars[user.id] = [];
        }
      } else {
        state.calendars[user.id] = [];
      }
    }),
  );

  renderUsers();
}

async function refreshSchedulerData() {
  const { startIso, endIso } = getWeekRange();

  state.events = await apiFetch("/events");
  const sessionPairs = await Promise.all(
    state.events.map(async (dance) => [dance.id, await apiFetch(`/events/${dance.id}/sessions`)]),
  );
  state.eventSessions = Object.fromEntries(sessionPairs);

  const syncFailures = await syncBusyForVisibleWeek(startIso, endIso);
  state.calendarOverview = await apiFetch(`/calendar/overview?start=${encodeURIComponent(startIso)}&end=${encodeURIComponent(endIso)}`);
  await requestPlanningRun(startIso, endIso);
  sanitizeStateAfterRefresh();
  renderApp();

  if (syncFailures.length) {
    showFlash(`Busy sync skipped for ${syncFailures.join(", ")}.`, true);
  }
}

async function handleSchedulePracticeClick() {
  try {
    await scheduleActivePractice();
  } catch (error) {
    showFlash(error.message, true);
  }
}

async function requestPlanningRun(startIso, endIso) {
  const eventIds = state.events
    .filter((dance) => dance.remaining_session_count > 0 && !["archived", "completed"].includes(dance.status))
    .map((dance) => dance.id);

  if (!eventIds.length) {
    state.planningRun = null;
    return;
  }

  const range = getPlanningHorizon(endIso);
  const payload = {
    event_ids: eventIds,
    horizon_start: range.startIso,
    horizon_end: range.endIso,
    slot_step_minutes: 60,
  };

  const eventDebugSummary = state.events
    .filter((dance) => eventIds.includes(dance.id))
    .map((dance) => ({
      event_id: dance.id,
      dance_name: dance.name,
      participant_ids: (dance.participants || []).map((participant) => participant.user_id),
      required_participant_ids: (dance.participants || [])
        .filter((participant) => participant.role === "required")
        .map((participant) => participant.user_id),
      optional_participant_ids: (dance.participants || [])
        .filter((participant) => participant.role === "optional")
        .map((participant) => participant.user_id),
      duration_minutes: dance.duration_minutes,
      required_session_count: dance.required_session_count,
      remaining_session_count: dance.remaining_session_count,
      latest_schedule_at: dance.latest_schedule_at,
      status: dance.status,
    }));

  console.log("POST /api/v1/planning-runs body", payload);
  console.log("Planning run event context (derived from selected event_ids)", eventDebugSummary);

  state.planningRun = await apiFetch("/planning-runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function sanitizeStateAfterRefresh() {
  const validDanceIds = new Set(state.events.map((dance) => dance.id));
  Object.keys(state.expandedDanceIds).forEach((danceId) => {
    if (!validDanceIds.has(danceId)) {
      delete state.expandedDanceIds[danceId];
    }
  });

  if (state.selectedDanceId && !validDanceIds.has(state.selectedDanceId)) {
    state.selectedDanceId = null;
    state.activePracticeKey = null;
    state.selectedSuggestionId = null;
  }

  if (state.selectedDanceId) {
    state.expandedDanceIds[state.selectedDanceId] = true;
    const activePractice = getActivePractice();
    if (!activePractice || !practiceExists(state.selectedDanceId, activePractice.sessionIndex)) {
      const next = getNextPracticeForDance(state.selectedDanceId);
      state.activePracticeKey = next ? practiceKey(state.selectedDanceId, next.sessionIndex) : null;
      state.selectedSuggestionId = null;
    }
  }

  if (state.selectedSuggestionId && !getRecommendationById(state.selectedSuggestionId)) {
    state.selectedSuggestionId = null;
  }

  mergeParticipantVisibility();
}

function renderApp() {
  renderHeader();
  renderSidebar();
  renderRightSidebar();
  renderCalendar();
  renderUsers();
}

function renderHeader() {
  headerWeekRange.textContent = formatWeekLabel(state.weekStart);

  const selectedDance = getSelectedDance();
  if (selectedDance) {
    selectedDancePill.textContent = selectedDance.name;
    selectedDancePill.classList.remove("hidden");
  } else {
    selectedDancePill.classList.add("hidden");
  }

  const anyConnected = state.users.some((user) => state.connections[user.id]?.connected);
  connectionBadge.classList.toggle("connected", anyConnected);
  connectionBadgeText.textContent = anyConnected ? "Google Calendar connected" : "Google Calendar not connected";
}

function renderSidebar() {
  renderDances();
  renderParticipants();
}

function renderDances() {
  if (!state.events.length) {
    dancesList.innerHTML = renderEmptyState(
      "No dances yet",
      "Add a dance to start the scheduling workflow.",
    );
    return;
  }

  dancesList.innerHTML = state.events
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((dance) => renderDanceCard(dance))
    .join("");
}

function renderDanceCard(dance) {
  const isSelected = dance.id === state.selectedDanceId;
  const isExpanded = state.expandedDanceIds[dance.id] || isSelected;
  const practices = getPracticeRows(dance.id);
  const status = dance.status || deriveDanceStatus(dance);

  return `
    <article class="dance-card ${isSelected ? "selected" : ""}">
      <div class="dance-card-top">
        <button
          type="button"
          class="collapse-button"
          data-dance-toggle="${escapeHtml(dance.id)}"
          aria-label="${isExpanded ? "Collapse dance" : "Expand dance"}"
        >
          ${isExpanded ? "&minus;" : "+"}
        </button>

        <div>
          <button type="button" class="dance-title-button" data-dance-select="${escapeHtml(dance.id)}">
            ${escapeHtml(dance.name)}
          </button>
          <div class="dance-progress">${dance.confirmed_session_count}/${dance.required_session_count} scheduled</div>
        </div>
      </div>

      <div class="dance-meta-row">
        <span class="status-badge status-${escapeHtml(status)}">${escapeHtml(formatStatusLabel(status))}</span>
        <span class="secondary-text compact-copy">${formatDurationHours(dance.duration_minutes)} · due ${formatDate(dance.latest_schedule_at)}</span>
      </div>

      ${
        isExpanded
          ? `
            <div class="dance-practice-list">
              ${practices.map((practice) => renderPracticeRow(dance.id, practice)).join("")}
            </div>
            <button type="button" class="secondary-button" data-dance-edit="${escapeHtml(dance.id)}">Edit dance</button>
          `
          : ""
      }
    </article>
  `;
}

function renderPracticeRow(danceId, practice) {
  const isActive = state.activePracticeKey === practiceKey(danceId, practice.sessionIndex);
  const isScheduled = practice.status === "scheduled";

  return `
    <button
      type="button"
      class="practice-row ${isActive ? "active" : ""}"
      data-practice-select="${practice.sessionIndex}"
      data-dance-id="${escapeHtml(danceId)}"
    >
      <div class="practice-row-meta">
        <strong>Practice ${practice.sessionIndex}</strong>
        <span class="practice-row-status">
          ${
            isScheduled
              ? `${formatShortDate(practice.session.start_at)} · ${formatTime(practice.session.start_at)}-${formatTime(practice.session.end_at)}`
              : "Unscheduled"
          }
        </span>
      </div>
      <span class="status-badge ${isScheduled ? "status-scheduled" : "status-unscheduled"}">
        ${isScheduled ? "scheduled" : "unscheduled"}
      </span>
    </button>
  `;
}

function renderParticipants() {
  if (!state.users.length) {
    participantsList.innerHTML = renderEmptyState("No participants", "Add participant to manage calendars and overlays.");
    return;
  }

  participantsList.innerHTML = state.users
    .slice()
    .sort((left, right) => left.display_name.localeCompare(right.display_name))
    .map((user) => {
      const connected = Boolean(state.connections[user.id]?.connected);
      const isVisible = state.participantVisibility[user.id] !== false;
      return `
        <div class="participant-row">
          <span class="participant-dot" style="background:${getParticipantColorByUserId(user.id)};"></span>
          <div class="participant-meta">
            <strong>${escapeHtml(user.display_name)}</strong>
            <span class="participant-subline">${connected ? "Calendar connected" : "Calendar not connected"}</span>
          </div>
          <button type="button" class="secondary-button" data-manage-user="${escapeHtml(user.id)}">Manage</button>
          <button
            type="button"
            class="visibility-toggle ${isVisible ? "active" : ""}"
            data-toggle-visibility="${escapeHtml(user.id)}"
            aria-label="${isVisible ? "Hide participant overlays" : "Show participant overlays"}"
          ></button>
        </div>
      `;
    })
    .join("");
}

function renderRightSidebar() {
  const selectedDance = getSelectedDance();
  const activePractice = getActivePractice();
  const remainingPractice = selectedDance ? getNextPracticeForDance(selectedDance.id) : null;

  if (!selectedDance) {
    selectedDanceSummary.innerHTML = `
      <strong>Select a dance from the left.</strong>
      <div class="secondary-text compact-copy">Choose one dance to review its next practice and see ghost suggestions on the calendar.</div>
    `;
    schedulePracticeButton.disabled = true;
    schedulePracticeHint.textContent = "Select a dance from the left.";
    suggestedSlots.innerHTML = renderEmptyState("Suggested Slots", "Select a dance to start the AI scheduling workflow.");
    selectedSlotSection.classList.add("hidden");
    return;
  }

  const requiredCount = selectedDance.participants.filter((participant) => participant.role === "required").length;
  const locationLabel = getLocationLabel(selectedDance.id, activePractice?.sessionIndex || remainingPractice?.sessionIndex || 1);

  selectedDanceSummary.innerHTML = `
    <div>
      <strong>${escapeHtml(selectedDance.name)}</strong>
      <div class="secondary-text compact-copy">Practice ${activePractice?.sessionIndex || remainingPractice?.sessionIndex || 1}</div>
    </div>
    <div class="summary-grid">
      <div class="summary-metric">
        <span class="summary-metric-label">Duration</span>
        <strong>${formatDurationHours(selectedDance.duration_minutes)}</strong>
      </div>
      <div class="summary-metric">
        <span class="summary-metric-label">Required participants</span>
        <strong>${requiredCount}</strong>
      </div>
      <div class="summary-metric">
        <span class="summary-metric-label">Location</span>
        <strong>${escapeHtml(locationLabel)}</strong>
      </div>
      <div class="summary-metric">
        <span class="summary-metric-label">Progress</span>
        <strong>${selectedDance.confirmed_session_count}/${selectedDance.required_session_count} scheduled</strong>
      </div>
    </div>
  `;

  const allScheduled = selectedDance.remaining_session_count <= 0;
  schedulePracticeButton.disabled = allScheduled === true;
  schedulePracticeHint.textContent = allScheduled
    ? "All practices confirmed. No remaining sessions."
    : `Active practice: ${activePractice ? `Practice ${activePractice.sessionIndex}` : `Practice ${remainingPractice?.sessionIndex || 1}`}`;

  if (allScheduled) {
    suggestedSlots.innerHTML = renderEmptyState("Suggested Slots", "All practices confirmed. No remaining sessions.");
    selectedSlotSection.classList.add("hidden");
    return;
  }

  const suggestions = getActiveSuggestions();
  if (!suggestions.length) {
    suggestedSlots.innerHTML = renderEmptyState(
      "Suggested Slots",
      "No suggested slots found. Try adjusting participant visibility or schedule manually.",
    );
    selectedSlotSection.classList.add("hidden");
    return;
  }

  suggestedSlots.innerHTML = suggestions.map((suggestion) => renderSuggestionCard(suggestion)).join("");
  renderSelectedSlotEditor();
}

function renderSuggestionCard(suggestion) {
  const display = getSuggestionDisplay(suggestion);
  const availableNames = getAvailableParticipantNames(suggestion);
  const conflicts = getConflictText(suggestion);
  const reasonText = getReasonText(suggestion);
  const isSelected = state.selectedSuggestionId === suggestion.id;

  return `
    <article class="slot-card ${isSelected ? "selected" : ""}">
      <button type="button" data-select-suggestion="${escapeHtml(suggestion.id)}">
        <div class="slot-card-head">
          <div>
            <strong>${escapeHtml(formatSlotTitle(display.start_at, display.end_at))}</strong>
            <div class="secondary-text compact-copy">Practice ${suggestion.session_index}</div>
          </div>
          <span class="score-pill">Score ${displayScore(suggestion)}</span>
        </div>

        <div class="slot-detail">
          <span>Available participants</span>
          <div>${escapeHtml(availableNames.join(", ") || "No availability details returned")}</div>
        </div>

        <div class="slot-detail">
          <span>Conflicts</span>
          <div>${escapeHtml(conflicts)}</div>
        </div>

        <div class="slot-detail">
          <span>Reason</span>
          <div>${escapeHtml(reasonText)}</div>
        </div>
      </button>
    </article>
  `;
}

function renderSelectedSlotEditor() {
  const selectedSuggestion = getSelectedSuggestion();
  if (!selectedSuggestion) {
    selectedSlotSection.classList.add("hidden");
    return;
  }

  const display = getSuggestionDisplay(selectedSuggestion);
  selectedSlotSection.classList.remove("hidden");
  selectedSlotEditor.innerHTML = `
    <div class="editor-grid">
      <label>
        Start time
        <input data-slot-field="start_at" type="datetime-local" value="${toLocalDateTimeInputValue(display.start_at)}" />
      </label>
      <label>
        End time
        <input data-slot-field="end_at" type="datetime-local" value="${toLocalDateTimeInputValue(display.end_at)}" />
      </label>
      <label>
        Location/room
        <input data-slot-field="location" type="text" value="${escapeAttribute(display.location === DEFAULT_ROOM_LABEL ? "" : display.location || "")}" placeholder="Studio A" />
      </label>
    </div>
  `;

  const timeModified = isSuggestionTimeModified(selectedSuggestion.id);
  const locationModified = Boolean(getSlotDraft(selectedSuggestion.id)?.location?.trim());
  const notes = [];
  if (timeModified) {
    notes.push("Time edits update the preview only. The current backend confirm endpoint can only confirm the original suggested slot.");
  }
  if (locationModified) {
    notes.push("Location is stored as a frontend placeholder because the current backend response does not include a room name field.");
  }
  if (notes.length) {
    selectedSlotNote.textContent = notes.join(" ");
    selectedSlotNote.classList.remove("hidden");
  } else {
    selectedSlotNote.classList.add("hidden");
    selectedSlotNote.textContent = "";
  }
}

function renderCalendar() {
  const selectedDance = getSelectedDance();
  const activePractice = getActivePractice();
  calendarSubtitle.textContent = selectedDance
    ? `${selectedDance.name} · ${activePractice ? `Practice ${activePractice.sessionIndex}` : "Select a practice"}`
    : "Busy overlays, suggested slots, and confirmed practices.";

  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(state.weekStart, index));
  const busySegments = expandBusySegments(getVisibleBusyIntervals(), weekDays);
  const ghostSuggestions = getActiveSuggestions().map((suggestion) => getSuggestionDisplay(suggestion));
  const ghostSegments = expandSuggestionSegments(ghostSuggestions, weekDays);
  const confirmedSegments = expandConfirmedSegments(getRenderedPracticeSessions(), weekDays);
  const hasItems = busySegments.length || ghostSegments.length || confirmedSegments.length;

  if (!hasItems) {
    calendar.innerHTML = `
      <div class="calendar-empty">
        ${renderEmptyState("Nothing on the calendar", "Select a dance or sync calendars to populate this week view.")}
      </div>
    `;
    return;
  }

  const busyByDay = groupByDay(busySegments);
  const ghostByDay = groupByDay(ghostSegments);
  const confirmedByDay = groupByDay(confirmedSegments);

  const headerHtml = `
    <div class="calendar-header">
      <div class="calendar-header-cell">Time</div>
      ${weekDays
        .map(
          (day) => `
            <div class="calendar-header-cell">
              <div class="calendar-day-label">
                <strong>${escapeHtml(day.toLocaleDateString(undefined, { weekday: "short" }))}</strong>
                <span class="secondary-text">${escapeHtml(day.toLocaleDateString(undefined, { month: "short", day: "numeric" }))}</span>
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;

  const gridHtml = `
    <div class="calendar-grid">
      <div class="time-column">
        ${Array.from({ length: GRID_END_HOUR - GRID_START_HOUR }, (_, index) => `<div class="time-cell">${formatHourLabel(GRID_START_HOUR + index)}</div>`).join("")}
      </div>

      ${weekDays
        .map((day, index) => {
          const dayKey = toDayKey(day);
          const busyItems = layoutOverlappingItems(busyByDay[dayKey] || []);
          const ghostItems = layoutOverlappingItems(ghostByDay[dayKey] || []);
          const confirmedItems = layoutOverlappingItems(confirmedByDay[dayKey] || []);
          return `
            <div class="day-column" data-day-index="${index}">
              ${Array.from({ length: GRID_END_HOUR - GRID_START_HOUR }, (_, hourIndex) => `<div class="hour-line" style="top:${hourIndex * HOUR_ROW_HEIGHT}px;"></div>`).join("")}
              ${busyItems.map(({ item, column, columnCount }) => renderBusyBlock(item, column, columnCount)).join("")}
              ${ghostItems.map(({ item, column, columnCount }) => renderGhostBlock(item, column, columnCount)).join("")}
              ${confirmedItems.map(({ item, column, columnCount }) => renderConfirmedBlock(item, column, columnCount)).join("")}
            </div>
          `;
        })
        .join("")}
    </div>
  `;

  calendar.innerHTML = `${headerHtml}${gridHtml}`;
}

function renderBusyBlock(segment, column, columnCount) {
  const placement = getPlacement(segment.start_at, segment.end_at);
  if (!placement) {
    return "";
  }

  return `
    <div
      class="calendar-block busy"
      style="${blockPlacementStyle(placement, column, columnCount)} background:${getParticipantColorByUserId(segment.user_id)}aa;"
    >
      <div class="block-title">${escapeHtml(segment.user_name)}</div>
      <div class="block-subtitle">Busy · ${formatTime(segment.start_at)}-${formatTime(segment.end_at)}</div>
    </div>
  `;
}

function renderGhostBlock(segment, column, columnCount) {
  const placement = getPlacement(segment.start_at, segment.end_at);
  if (!placement) {
    return "";
  }

  const selected = state.selectedSuggestionId === segment.id ? "selected" : "";
  const dragging = state.dragState?.type === "suggestion" && state.dragState.id === segment.id ? "dragging" : "";
  return `
    <div
      class="calendar-block ghost ${selected} ${dragging}"
      data-ghost-id="${escapeHtml(segment.id)}"
      style="${blockPlacementStyle(placement, column, columnCount)}"
    >
      <div class="block-title">${escapeHtml(segment.dance_name)} · Practice ${segment.session_index}</div>
      <div class="block-subtitle">${formatTime(segment.start_at)}-${formatTime(segment.end_at)}</div>
      <div class="block-subtitle">Suggested slot</div>
    </div>
  `;
}

function renderConfirmedBlock(segment, column, columnCount) {
  const placement = getPlacement(segment.start_at, segment.end_at);
  if (!placement) {
    return "";
  }

  const editable = state.confirmedEditMode ? "editable" : "";
  const dragging = state.dragState?.type === "confirmed" && state.dragState.id === segment.id ? "dragging" : "";
  const location = segment.location && segment.location !== DEFAULT_ROOM_LABEL ? ` · ${segment.location}` : "";

  return `
    <div
      class="calendar-block confirmed ${editable} ${dragging}"
      data-confirmed-id="${escapeHtml(segment.id)}"
      style="${blockPlacementStyle(placement, column, columnCount)}"
    >
      <div class="block-title">${escapeHtml(segment.dance_name)} · Practice ${segment.session_index}</div>
      <div class="block-subtitle">${formatTime(segment.start_at)}-${formatTime(segment.end_at)}${escapeHtml(location)}</div>
      <div class="block-subtitle">${state.confirmedEditMode ? "Confirmed · drag to preview" : "Confirmed practice"}</div>
    </div>
  `;
}

function renderUsers() {
  if (!state.users.length) {
    usersList.innerHTML = renderEmptyState("No participants", "Add participant to connect calendars and schedule dances.");
    return;
  }

  usersList.innerHTML = state.users
    .slice()
    .sort((left, right) => left.display_name.localeCompare(right.display_name))
    .map((user) => renderSettingsUserCard(user))
    .join("");

  if (state.focusedSettingsUserId) {
    requestAnimationFrame(() => {
      const card = usersList.querySelector(`[data-settings-user="${state.focusedSettingsUserId}"]`);
      card?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }
}

function renderSettingsUserCard(user) {
  const connection = state.connections[user.id] || {
    connected: false,
    status: "disconnected",
    account_email: null,
    selected_busy_calendar_ids: [],
    selected_write_calendar_id: null,
  };
  const calendars = state.calendars[user.id] || [];
  const busySelections = new Set(connection.selected_busy_calendar_ids || []);
  const writeSelection = connection.selected_write_calendar_id || "";
  const writableCalendars = calendars.filter((calendarItem) => ["owner", "writer"].includes(calendarItem.access_role));
  const focusedClass = state.focusedSettingsUserId === user.id ? 'style="outline: 2px solid rgba(79, 70, 229, 0.18);"' : "";

  return `
    <section class="settings-user-card" data-settings-user="${escapeHtml(user.id)}" ${focusedClass}>
      <div class="settings-user-top">
        <div class="participant-meta">
          <strong>${escapeHtml(user.display_name)}</strong>
          <span class="connection-summary">${escapeHtml(user.timezone)}${user.email ? ` · ${escapeHtml(user.email)}` : ""}</span>
        </div>
        <span class="status-badge ${connection.connected ? "status-completed" : "status-unscheduled"}">${escapeHtml(connection.status || "disconnected")}</span>
      </div>

      <div class="settings-user-actions">
        <button type="button" class="secondary-button" data-user-action="connect" data-user-id="${escapeHtml(user.id)}">Connect Google</button>
        <button type="button" class="secondary-button" data-user-action="refresh-calendars" data-user-id="${escapeHtml(user.id)}">Refresh calendars</button>
        <button type="button" class="secondary-button" data-user-action="sync-busy" data-user-id="${escapeHtml(user.id)}">Sync visible week</button>
      </div>

      ${
        calendars.length
          ? `
            <div class="select-grid">
              <label>
                Busy source calendars
                <select multiple size="4" data-role="busy-calendars" data-user-id="${escapeHtml(user.id)}">
                  ${calendars
                    .map(
                      (calendarItem) => `
                        <option value="${escapeAttribute(calendarItem.id)}" ${busySelections.has(calendarItem.id) ? "selected" : ""}>
                          ${escapeHtml(calendarItem.summary)}${calendarItem.primary ? " (primary)" : ""}
                        </option>
                      `,
                    )
                    .join("")}
                </select>
              </label>
              <label>
                Write calendar
                <select data-role="write-calendar" data-user-id="${escapeHtml(user.id)}">
                  <option value="">Use primary</option>
                  ${writableCalendars
                    .map(
                      (calendarItem) => `
                        <option value="${escapeAttribute(calendarItem.id)}" ${writeSelection === calendarItem.id ? "selected" : ""}>
                          ${escapeHtml(calendarItem.summary)}
                        </option>
                      `,
                    )
                    .join("")}
                </select>
              </label>
              <button type="button" class="primary-button" data-user-action="save-calendars" data-user-id="${escapeHtml(user.id)}">Save calendar selection</button>
            </div>
          `
          : `<div class="connection-summary">Load calendars after connecting Google Calendar to choose busy-source and write calendars.</div>`
      }
    </section>
  `;
}

function selectDance(danceId, { sessionIndex = null, keepSuggestion = false } = {}) {
  const dance = getDanceById(danceId);
  if (!dance) {
    return;
  }

  state.selectedDanceId = danceId;
  state.expandedDanceIds[danceId] = true;

  const nextPractice = sessionIndex ? { sessionIndex } : getNextPracticeForDance(danceId) || { sessionIndex: 1 };
  state.activePracticeKey = practiceKey(danceId, nextPractice.sessionIndex);
  if (!keepSuggestion) {
    state.selectedSuggestionId = null;
  }

  renderApp();
}

function selectSuggestion(suggestionId) {
  const suggestion = getRecommendationById(suggestionId);
  if (!suggestion) {
    return;
  }

  state.selectedSuggestionId = suggestionId;
  state.selectedDanceId = suggestion.dance_event_id;
  state.expandedDanceIds[suggestion.dance_event_id] = true;
  state.activePracticeKey = practiceKey(suggestion.dance_event_id, suggestion.session_index);
  ensureSlotDraft(suggestion);
  renderApp();
  focusSuggestionInCalendar(suggestionId);
}

async function scheduleActivePractice() {
  const selectedDance = getSelectedDance();
  if (!selectedDance) {
    throw new Error("Select a dance first.");
  }
  if (selectedDance.remaining_session_count <= 0) {
    renderRightSidebar();
    return;
  }

  const nextPractice = getNextPracticeForDance(selectedDance.id);
  if (!nextPractice) {
    renderRightSidebar();
    return;
  }

  state.activePracticeKey = practiceKey(selectedDance.id, nextPractice.sessionIndex);
  state.selectedSuggestionId = null;

  const { startIso, endIso } = getWeekRange();
  await requestPlanningRun(startIso, endIso);
  renderApp();
}

async function confirmSelectedSlot() {
  const selectedSuggestion = getSelectedSuggestion();
  if (!selectedSuggestion || !state.planningRun) {
    throw new Error("Select a suggestion first.");
  }

  if (isSuggestionTimeModified(selectedSuggestion.id)) {
    throw new Error("Reset the slot to the original suggested time before confirming. Manual time edits are preview-only right now.");
  }

  await apiFetch(`/planning-runs/${state.planningRun.id}/confirm`, {
    method: "POST",
    body: JSON.stringify({
      result_ids: [selectedSuggestion.id],
    }),
  });

  const draft = getSlotDraft(selectedSuggestion.id);
  if (draft?.location?.trim()) {
    state.sessionLocationOverrides[practiceKey(selectedSuggestion.dance_event_id, selectedSuggestion.session_index)] = draft.location.trim();
  }

  state.selectedSuggestionId = null;
  await refreshSchedulerData();

  if (state.selectedDanceId) {
    const nextPractice = getNextPracticeForDance(state.selectedDanceId);
    state.activePracticeKey = nextPractice ? practiceKey(state.selectedDanceId, nextPractice.sessionIndex) : null;
  }

  renderApp();
  showFlash("Slot confirmed.");
}

function handleSlotEditorChange(event) {
  const field = event.target.dataset.slotField;
  const selectedSuggestion = getSelectedSuggestion();
  if (!field || !selectedSuggestion) {
    return;
  }

  const draft = ensureSlotDraft(selectedSuggestion);
  if (field === "location") {
    draft.location = event.target.value;
  } else if (field === "start_at") {
    const value = fromLocalDateTimeInputValue(event.target.value);
    if (value) {
      draft.start_at = value;
      if (new Date(draft.end_at) <= new Date(draft.start_at)) {
        draft.end_at = addMinutesIso(draft.start_at, getDurationMinutes(selectedSuggestion.start_at, selectedSuggestion.end_at));
      }
    }
  } else if (field === "end_at") {
    const value = fromLocalDateTimeInputValue(event.target.value);
    if (value) {
      draft.end_at = value;
    }
  }

  renderRightSidebar();
  renderCalendar();
}

async function createUser() {
  const payload = {
    display_name: document.getElementById("display-name").value.trim(),
    email: document.getElementById("email").value.trim() || null,
    timezone: timezoneInput.value.trim(),
  };

  await apiFetch("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  userForm.reset();
  timezoneInput.value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  await refreshDashboard();
  openSettingsModal({ focusForm: true });
  showFlash("Participant created.");
}

function openSettingsModal({ focusUserId = null, focusForm = false } = {}) {
  state.focusedSettingsUserId = focusUserId;
  state.focusedSettingsForm = focusForm;
  settingsModal.classList.remove("hidden");
  danceModal.classList.add("hidden");
  modalOverlay.classList.remove("hidden");
  renderUsers();

  if (focusForm) {
    requestAnimationFrame(() => document.getElementById("display-name").focus());
  }
}

function openCreateDanceModal() {
  if (!state.users.length) {
    showFlash("Add participant before creating a dance.", true);
    openSettingsModal({ focusForm: true });
    return;
  }

  state.editingDanceId = null;
  addDanceForm.reset();
  setDefaultDanceDeadline();
  renderDanceParticipantSelectors();
  hideInlineError(addDanceError);
  danceModalEyebrow.textContent = "Dance Setup";
  danceModalTitle.textContent = "Add dance";
  danceModalSubtitle.textContent = "Create a dance and choose who needs to attend.";
  submitDanceButton.textContent = "Save dance";
  settingsModal.classList.add("hidden");
  danceModal.classList.remove("hidden");
  modalOverlay.classList.remove("hidden");
}

function openEditDanceModal(danceId) {
  const dance = getDanceById(danceId);
  if (!dance) {
    showFlash("Dance not found.", true);
    return;
  }

  state.editingDanceId = dance.id;
  danceModalEyebrow.textContent = "Dance Setup";
  danceModalTitle.textContent = "Edit dance";
  danceModalSubtitle.textContent = "Update dance details and participant roles.";
  submitDanceButton.textContent = "Save dance";
  hideInlineError(addDanceError);
  renderDanceParticipantSelectors(
    Object.fromEntries(dance.participants.map((participant) => [participant.user_id, participant.role])),
  );

  document.getElementById("dance-name").value = dance.name;
  document.getElementById("dance-session-count").value = dance.required_session_count;
  document.getElementById("dance-duration-hours").value = `${dance.duration_minutes / 60}`;
  document.getElementById("dance-deadline").value = toDateInputValue(dance.latest_schedule_at);
  document.getElementById("dance-description").value = dance.description || "";

  settingsModal.classList.add("hidden");
  danceModal.classList.remove("hidden");
  modalOverlay.classList.remove("hidden");
}

function closeModals() {
  settingsModal.classList.add("hidden");
  danceModal.classList.add("hidden");
  modalOverlay.classList.add("hidden");
  state.focusedSettingsUserId = null;
  state.focusedSettingsForm = false;
  state.editingDanceId = null;
  hideInlineError(addDanceError);
}

function renderDanceParticipantSelectors(selectedRoles = {}) {
  addDanceParticipants.innerHTML = state.users
    .slice()
    .sort((left, right) => left.display_name.localeCompare(right.display_name))
    .map(
      (user) => `
        <div class="participant-selector-row">
          <span class="participant-dot" style="background:${getParticipantColorByUserId(user.id)};"></span>
          <div class="participant-meta">
            <strong>${escapeHtml(user.display_name)}</strong>
            <span class="participant-subline">${escapeHtml(user.timezone)}</span>
          </div>
          <select data-dance-participant="${escapeHtml(user.id)}">
            <option value="ignore" ${(selectedRoles[user.id] || "ignore") === "ignore" ? "selected" : ""}>Ignore</option>
            <option value="required" ${selectedRoles[user.id] === "required" ? "selected" : ""}>Required</option>
            <option value="optional" ${selectedRoles[user.id] === "optional" ? "selected" : ""}>Optional</option>
          </select>
        </div>
      `,
    )
    .join("");
}

async function submitDanceForm() {
  hideInlineError(addDanceError);
  const isEditing = Boolean(state.editingDanceId);
  const name = document.getElementById("dance-name").value.trim();
  const requiredSessionCount = Number(document.getElementById("dance-session-count").value);
  const durationHours = Number(document.getElementById("dance-duration-hours").value);
  const deadline = document.getElementById("dance-deadline").value;
  const description = document.getElementById("dance-description").value.trim();

  const participants = state.users
    .map((user) => ({
      user_id: user.id,
      role: addDanceParticipants.querySelector(`[data-dance-participant="${user.id}"]`)?.value || "ignore",
    }))
    .filter((participant) => participant.role !== "ignore");

  if (!name) {
    throw new Error("Dance name is required.");
  }
  if (!deadline) {
    throw new Error("Deadline is required.");
  }
  if (!participants.length) {
    throw new Error("Select at least one participant.");
  }
  if (!participants.some((participant) => participant.role === "required")) {
    throw new Error("At least one participant must be marked required.");
  }

  const existingDance = state.editingDanceId ? getDanceById(state.editingDanceId) : null;
  const payload = {
    name,
    description: description || null,
    organizer_user_id: existingDance?.organizer_user_id || state.users[0]?.id,
    duration_minutes: Math.round(durationHours * 60),
    latest_schedule_at: new Date(`${deadline}T23:59:59`).toISOString(),
    required_session_count: requiredSessionCount,
    participants,
  };

  const response = isEditing
    ? await apiFetch(`/events/${state.editingDanceId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      })
    : await apiFetch("/events", {
        method: "POST",
        body: JSON.stringify(payload),
      });

  closeModals();
  state.selectedDanceId = response.id;
  await refreshSchedulerData();
  selectDance(response.id);
  showFlash(isEditing ? "Dance updated." : "Dance created.");
}

async function beginGoogleOauth(userId) {
  const response = await apiFetch("/google/oauth/start", {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
  window.location.href = response.authorization_url;
}

async function refreshCalendars(userId) {
  state.calendars[userId] = await apiFetch(`/users/${userId}/google/calendars`);
  renderUsers();
}

async function saveCalendarSelection(userId) {
  const busySelect = usersList.querySelector(`[data-role="busy-calendars"][data-user-id="${userId}"]`);
  const writeSelect = usersList.querySelector(`[data-role="write-calendar"][data-user-id="${userId}"]`);
  const busyCalendarIds = Array.from(busySelect?.selectedOptions || []).map((option) => option.value);
  const writeCalendarId = writeSelect?.value || null;

  state.connections[userId] = await apiFetch(`/users/${userId}/google/calendars/select`, {
    method: "POST",
    body: JSON.stringify({
      busy_calendar_ids: busyCalendarIds,
      write_calendar_id: writeCalendarId,
    }),
  });

  await refreshSchedulerData();
  renderUsers();
}

function syncBusyForUser(userId) {
  const { startIso, endIso } = getWeekRange();
  return apiFetch(`/users/${userId}/google/sync-busy`, {
    method: "POST",
    body: JSON.stringify({
      horizon_start: startIso,
      horizon_end: endIso,
    }),
  });
}

async function syncBusyForVisibleWeek(startIso, endIso) {
  const connectedUsers = state.users.filter((user) => state.connections[user.id]?.connected);
  if (!connectedUsers.length) {
    return [];
  }

  const failures = [];
  await Promise.all(
    connectedUsers.map(async (user) => {
      try {
        await apiFetch(`/users/${user.id}/google/sync-busy`, {
          method: "POST",
          body: JSON.stringify({
            horizon_start: startIso,
            horizon_end: endIso,
          }),
        });
      } catch (_error) {
        failures.push(user.display_name);
      }
    }),
  );
  return failures;
}

function handleCalendarPointerDown(event) {
  const ghost = event.target.closest("[data-ghost-id]");
  if (ghost) {
    const suggestion = getRecommendationById(ghost.dataset.ghostId);
    if (!suggestion) {
      return;
    }
    ensureSlotDraft(suggestion);
    state.selectedSuggestionId = suggestion.id;
    beginDrag({
      type: "suggestion",
      id: suggestion.id,
      durationMinutes: getDurationMinutes(getSuggestionDisplay(suggestion).start_at, getSuggestionDisplay(suggestion).end_at),
      pointerOffsetMinutes: getPointerOffsetMinutes(event, ghost),
    });
    renderRightSidebar();
    renderCalendar();
    event.preventDefault();
    return;
  }

  const confirmed = event.target.closest("[data-confirmed-id]");
  if (confirmed && state.confirmedEditMode) {
    const session = getRenderedPracticeSessions().find((item) => item.id === confirmed.dataset.confirmedId);
    if (!session) {
      return;
    }
    beginDrag({
      type: "confirmed",
      id: session.id,
      durationMinutes: getDurationMinutes(session.start_at, session.end_at),
      pointerOffsetMinutes: getPointerOffsetMinutes(event, confirmed),
    });
    event.preventDefault();
  }
}

function beginDrag(payload) {
  state.dragState = {
    ...payload,
    moved: false,
  };
}

function handleGlobalPointerMove(event) {
  if (!state.dragState) {
    return;
  }

  const dayColumns = Array.from(calendar.querySelectorAll(".day-column"));
  if (!dayColumns.length) {
    return;
  }

  state.dragState.moved = true;
  const dayIndex = getDayIndexFromPointer(dayColumns, event.clientX);
  const yMinutes = getMinutesFromPointer(dayColumns[0], event.clientY);
  const snapMinutes = state.dragState.type === "suggestion" ? Math.max(30, state.planningRun?.slot_step_minutes || 60) : 30;
  const clampedStartMinutes = clampToGrid(snapMinutes * Math.round((yMinutes - state.dragState.pointerOffsetMinutes) / snapMinutes), state.dragState.durationMinutes);
  const nextStart = buildWeekDateTime(dayIndex, clampedStartMinutes);
  const nextEnd = addMinutesIso(nextStart, state.dragState.durationMinutes);

  if (state.dragState.type === "suggestion") {
    const suggestion = getRecommendationById(state.dragState.id);
    if (!suggestion) {
      return;
    }
    const draft = ensureSlotDraft(suggestion);
    draft.start_at = nextStart;
    draft.end_at = nextEnd;
    state.selectedSuggestionId = suggestion.id;
    renderCalendar();
    renderRightSidebar();
  } else if (state.dragState.type === "confirmed") {
    state.confirmedSessionDrafts[state.dragState.id] = {
      start_at: nextStart,
      end_at: nextEnd,
    };
    renderCalendar();
  }
}

function handleGlobalPointerUp() {
  if (!state.dragState) {
    return;
  }
  state.justFinishedDrag = Boolean(state.dragState.moved);
  state.dragState = null;
}

function getDayIndexFromPointer(dayColumns, clientX) {
  const foundIndex = dayColumns.findIndex((column) => {
    const rect = column.getBoundingClientRect();
    return clientX >= rect.left && clientX <= rect.right;
  });

  if (foundIndex >= 0) {
    return foundIndex;
  }

  const firstRect = dayColumns[0].getBoundingClientRect();
  const lastRect = dayColumns[dayColumns.length - 1].getBoundingClientRect();
  if (clientX < firstRect.left) {
    return 0;
  }
  if (clientX > lastRect.right) {
    return dayColumns.length - 1;
  }
  return 0;
}

function getMinutesFromPointer(firstDayColumn, clientY) {
  const rect = firstDayColumn.getBoundingClientRect();
  const offset = clientY - rect.top + calendarScroll.scrollTop;
  return (offset / HOUR_ROW_HEIGHT) * 60;
}

function getPointerOffsetMinutes(pointerEvent, element) {
  const rect = element.getBoundingClientRect();
  return ((pointerEvent.clientY - rect.top) / HOUR_ROW_HEIGHT) * 60;
}

function clampToGrid(startMinutes, durationMinutes) {
  return Math.min(Math.max(startMinutes, 0), TOTAL_GRID_MINUTES - durationMinutes);
}

function focusSuggestionInCalendar(suggestionId) {
  requestAnimationFrame(() => {
    const block = calendar.querySelector(`[data-ghost-id="${suggestionId}"]`);
    if (!block) {
      return;
    }
    const targetTop = Math.max(block.offsetTop - calendarScroll.clientHeight / 2 + block.clientHeight / 2 - 32, 0);
    calendarScroll.scrollTo({ top: targetTop, behavior: "smooth" });
  });
}

function getSelectedDance() {
  return getDanceById(state.selectedDanceId);
}

function getDanceById(danceId) {
  return state.events.find((dance) => dance.id === danceId) || null;
}

function getActivePractice() {
  if (!state.selectedDanceId || !state.activePracticeKey) {
    return null;
  }
  const [danceId, sessionIndex] = state.activePracticeKey.split("::");
  if (danceId !== state.selectedDanceId) {
    return null;
  }
  return {
    danceId,
    sessionIndex: Number(sessionIndex),
  };
}

function getActiveSuggestions() {
  const activePractice = getActivePractice();
  if (!activePractice || !state.planningRun?.results) {
    return [];
  }
  return state.planningRun.results
    .find(
      (group) =>
        group.dance_event_id === activePractice.danceId &&
        group.session_index === activePractice.sessionIndex,
    )
    ?.recommendations.slice(0, 3) || [];
}

function getRecommendationById(recommendationId) {
  return (state.planningRun?.results || [])
    .flatMap((group) => group.recommendations || [])
    .find((recommendation) => recommendation.id === recommendationId) || null;
}

function getSelectedSuggestion() {
  return getRecommendationById(state.selectedSuggestionId);
}

function getPracticeRows(danceId) {
  const sessions = getSessionsForDance(danceId);
  const dance = getDanceById(danceId);
  if (!dance) {
    return [];
  }

  return Array.from({ length: dance.required_session_count }, (_, index) => {
    const sessionIndex = index + 1;
    const session = sessions.find((item) => item.session_index === sessionIndex);
    return {
      sessionIndex,
      status: session ? "scheduled" : "unscheduled",
      session,
    };
  });
}

function getSessionsForDance(danceId) {
  return (state.eventSessions[danceId] || [])
    .slice()
    .sort((left, right) => left.session_index - right.session_index);
}

function getNextPracticeForDance(danceId) {
  return getPracticeRows(danceId).find((practice) => practice.status === "unscheduled") || null;
}

function practiceExists(danceId, sessionIndex) {
  return getPracticeRows(danceId).some((practice) => practice.sessionIndex === sessionIndex);
}

function getVisibleBusyIntervals() {
  return state.calendarOverview.busy_intervals.filter((interval) => state.participantVisibility[interval.user_id] !== false);
}

function getRenderedPracticeSessions() {
  return state.calendarOverview.practice_sessions.map((session) => {
    const preview = state.confirmedSessionDrafts[session.id] || {};
    const dance = getDanceById(session.dance_event_id);
    return {
      ...session,
      dance_name: dance?.name || "Dance",
      start_at: preview.start_at || session.start_at,
      end_at: preview.end_at || session.end_at,
      location: getLocationLabel(session.dance_event_id, session.session_index),
    };
  });
}

function getSuggestionDisplay(recommendation) {
  const draft = getSlotDraft(recommendation.id);
  return {
    ...recommendation,
    start_at: draft?.start_at || recommendation.start_at,
    end_at: draft?.end_at || recommendation.end_at,
    location: draft?.location || getLocationLabel(recommendation.dance_event_id, recommendation.session_index),
  };
}

function ensureSlotDraft(recommendation) {
  if (!state.slotDrafts[recommendation.id]) {
    state.slotDrafts[recommendation.id] = {
      start_at: recommendation.start_at,
      end_at: recommendation.end_at,
      location: "",
    };
  }
  return state.slotDrafts[recommendation.id];
}

function getSlotDraft(recommendationId) {
  return state.slotDrafts[recommendationId] || null;
}

function isSuggestionTimeModified(recommendationId) {
  const recommendation = getRecommendationById(recommendationId);
  const draft = getSlotDraft(recommendationId);
  if (!recommendation || !draft) {
    return false;
  }
  return draft.start_at !== recommendation.start_at || draft.end_at !== recommendation.end_at;
}

function getLocationLabel(danceId, sessionIndex) {
  return state.sessionLocationOverrides[practiceKey(danceId, sessionIndex)] || DEFAULT_ROOM_LABEL;
}

function getAvailableParticipantNames(recommendation) {
  const available = recommendation.participant_statuses
    .filter((item) => item.available)
    .map((item) => getUserById(item.user_id)?.display_name)
    .filter(Boolean);

  if (available.length) {
    return available;
  }

  const dance = getDanceById(recommendation.dance_event_id);
  return (dance?.participants || [])
    .filter((participant) => participant.role === "required")
    .map((participant) => getUserById(participant.user_id)?.display_name)
    .filter(Boolean);
}

function getConflictText(recommendation) {
  const missingRequired = (recommendation.missing_required_user_ids || [])
    .map((userId) => getUserById(userId)?.display_name)
    .filter(Boolean);
  if (missingRequired.length) {
    return `Missing required: ${missingRequired.join(", ")}`;
  }

  const unavailable = recommendation.participant_statuses
    .filter((item) => !item.available)
    .map((item) => getUserById(item.user_id)?.display_name)
    .filter(Boolean);

  return unavailable.length ? unavailable.join(", ") : "None";
}

function getReasonText(recommendation) {
  return (
    recommendation.explanation?.summary ||
    recommendation.explanation?.reasons?.[0]?.message ||
    "Fits all participants, avoids late-night hours."
  );
}

function displayScore(recommendation) {
  const base = Number.isFinite(Number(recommendation.total_score)) ? Number(recommendation.total_score) : recommendation.rank;
  return Math.max(70, Math.min(99, Math.round(82 + base * 5 - (recommendation.rank - 1) * 3)));
}

function getUserById(userId) {
  return state.users.find((user) => user.id === userId) || null;
}

function getParticipantColorByUserId(userId) {
  const index = state.users.findIndex((user) => user.id === userId);
  return PARTICIPANT_COLORS[Math.max(index, 0) % PARTICIPANT_COLORS.length];
}

function expandBusySegments(intervals, weekDays) {
  return intervals.flatMap((interval) => splitAcrossWeek(interval, weekDays, (segment) => {
    const user = getUserById(interval.user_id);
    return {
      ...segment,
      id: interval.id,
      user_id: interval.user_id,
      user_name: user?.display_name || "Busy",
    };
  }));
}

function expandSuggestionSegments(suggestions, weekDays) {
  return suggestions.flatMap((suggestion) => splitAcrossWeek(suggestion, weekDays, (segment) => ({
    ...segment,
    id: suggestion.id,
    dance_name: suggestion.dance_name,
    session_index: suggestion.session_index,
  })));
}

function expandConfirmedSegments(sessions, weekDays) {
  return sessions.flatMap((session) => splitAcrossWeek(session, weekDays, (segment) => ({
    ...segment,
    id: session.id,
    dance_name: session.dance_name,
    session_index: session.session_index,
    location: session.location,
  })));
}

function splitAcrossWeek(item, weekDays, mapper) {
  const start = new Date(item.start_at);
  const end = new Date(item.end_at);
  return weekDays.flatMap((day) => {
    const dayStart = new Date(day);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = addDays(dayStart, 1);
    const segmentStart = new Date(Math.max(start.getTime(), dayStart.getTime()));
    const segmentEnd = new Date(Math.min(end.getTime(), dayEnd.getTime()));
    if (segmentEnd <= segmentStart) {
      return [];
    }
    return [
      mapper({
        start_at: segmentStart.toISOString(),
        end_at: segmentEnd.toISOString(),
        dayKey: toDayKey(dayStart),
      }),
    ];
  });
}

function groupByDay(items) {
  return items.reduce((accumulator, item) => {
    const key = item.dayKey || toDayKey(item.start_at);
    if (!accumulator[key]) {
      accumulator[key] = [];
    }
    accumulator[key].push(item);
    return accumulator;
  }, {});
}

function layoutOverlappingItems(items) {
  const sorted = [...items].sort((left, right) => {
    if (left.start_at !== right.start_at) {
      return left.start_at.localeCompare(right.start_at);
    }
    return left.end_at.localeCompare(right.end_at);
  });

  const positioned = [];
  let cluster = [];
  let activeColumns = [];
  let clusterMaxEnd = -Infinity;

  const flushCluster = () => {
    if (!cluster.length) {
      return;
    }
    const columnCount = Math.max(...cluster.map((entry) => entry.column), 0) + 1;
    cluster.forEach((entry) => {
      positioned.push({
        item: entry.item,
        column: entry.column,
        columnCount,
      });
    });
    cluster = [];
    activeColumns = [];
    clusterMaxEnd = -Infinity;
  };

  sorted.forEach((item) => {
    const itemStart = new Date(item.start_at).getTime();
    const itemEnd = new Date(item.end_at).getTime();

    if (cluster.length && itemStart >= clusterMaxEnd) {
      flushCluster();
    }

    let column = activeColumns.findIndex((columnEnd) => columnEnd <= itemStart);
    if (column === -1) {
      column = activeColumns.length;
      activeColumns.push(itemEnd);
    } else {
      activeColumns[column] = itemEnd;
    }

    cluster.push({ item, column });
    clusterMaxEnd = Math.max(clusterMaxEnd, itemEnd);
  });

  flushCluster();
  return positioned;
}

function getPlacement(startAt, endAt) {
  const start = new Date(startAt);
  const end = new Date(endAt);
  const startMinutes = start.getHours() * 60 + start.getMinutes() - GRID_START_HOUR * 60;
  const endMinutes = end.getHours() * 60 + end.getMinutes() - GRID_START_HOUR * 60;
  const clampedStart = Math.max(startMinutes, 0);
  const clampedEnd = Math.min(endMinutes, TOTAL_GRID_MINUTES);

  if (clampedEnd <= clampedStart) {
    return null;
  }

  return {
    top: (clampedStart / 60) * HOUR_ROW_HEIGHT,
    height: ((clampedEnd - clampedStart) / 60) * HOUR_ROW_HEIGHT,
  };
}

function blockPlacementStyle(placement, column, columnCount) {
  const inset = 4;
  const width = 100 / columnCount;
  return [
    `top:${placement.top}px`,
    `height:${placement.height}px`,
    `left:calc(${column * width}% + ${inset}px)`,
    `width:calc(${width}% - ${inset * 2}px)`,
  ].join(";");
}

function mergeParticipantVisibility() {
  state.users.forEach((user) => {
    if (!(user.id in state.participantVisibility)) {
      state.participantVisibility[user.id] = true;
    }
  });
}

function updateRefreshButton() {
  refreshDashboardButton.disabled = state.isRefreshing;
  refreshDashboardButton.textContent = state.isRefreshing ? "Refreshing..." : "Refresh";
}

function getWeekRange() {
  const start = new Date(state.weekStart);
  start.setHours(0, 0, 0, 0);
  const end = addDays(start, 7);
  end.setHours(0, 0, 0, 0);
  return {
    startIso: start.toISOString(),
    endIso: end.toISOString(),
  };
}

function getPlanningHorizon(visibleEndIso = null) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const minimumEnd = addDays(today, 14);
  minimumEnd.setHours(0, 0, 0, 0);

  const visibleEnd = visibleEndIso ? new Date(visibleEndIso) : null;
  const finalEnd =
    visibleEnd && !Number.isNaN(visibleEnd.getTime()) && visibleEnd > minimumEnd
      ? visibleEnd
      : minimumEnd;

  return {
    startIso: today.toISOString(),
    endIso: finalEnd.toISOString(),
  };
}

function buildWeekDateTime(dayIndex, gridMinutes) {
  const date = addDays(state.weekStart, dayIndex);
  date.setHours(0, 0, 0, 0);
  return addMinutesIso(date.toISOString(), GRID_START_HOUR * 60 + gridMinutes);
}

function practiceKey(danceId, sessionIndex) {
  return `${danceId}::${sessionIndex}`;
}

function getDurationMinutes(startAt, endAt) {
  return Math.max(30, Math.round((new Date(endAt).getTime() - new Date(startAt).getTime()) / 60000));
}

function addMinutesIso(value, minutes) {
  const date = new Date(value);
  date.setMinutes(date.getMinutes() + minutes);
  return date.toISOString();
}

function deriveDanceStatus(dance) {
  if (dance.confirmed_session_count <= 0) {
    return "unscheduled";
  }
  if (dance.confirmed_session_count >= dance.required_session_count) {
    return "scheduled";
  }
  return "partially_scheduled";
}

function formatStatusLabel(status) {
  return status.replaceAll("_", " ");
}

function showCallbackMessage() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("google_connected")) {
    showFlash("Google Calendar connected.");
    window.history.replaceState({}, document.title, "/");
  }
  if (params.get("google_error")) {
    showFlash(params.get("google_error"), true);
    window.history.replaceState({}, document.title, "/");
  }
}

function showFlash(message, isError = false) {
  flash.textContent = message;
  flash.classList.remove("hidden", "error");
  flash.classList.toggle("error", isError);
  if (state.flashTimeoutId) {
    window.clearTimeout(state.flashTimeoutId);
  }
  state.flashTimeoutId = window.setTimeout(() => {
    flash.classList.add("hidden");
  }, 4200);
}

function showInlineError(element, message) {
  element.textContent = message;
  element.classList.remove("hidden");
}

function hideInlineError(element) {
  element.textContent = "";
  element.classList.add("hidden");
}

function renderEmptyState(title, description) {
  return `
    <div class="empty-state">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(description)}</p>
    </div>
  `;
}

function apiFetch(path, options = {}) {
  return fetch(`/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  }).then(async (response) => {
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed: ${response.status}`);
    }
    if (response.status === 204) {
      return null;
    }
    return response.json();
  });
}

function setDefaultDanceDeadline() {
  const defaultDate = addDays(new Date(), 14);
  document.getElementById("dance-deadline").value = toDateInputValue(defaultDate);
}

function formatWeekLabel(weekStart) {
  const weekEnd = addDays(weekStart, 6);
  return `${weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${weekEnd.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

function formatSlotTitle(startAt, endAt) {
  const dayText = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date(startAt));
  return `${dayText} · ${formatTime(startAt)}-${formatTime(endAt)}`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatShortDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDurationHours(durationMinutes) {
  const hours = durationMinutes / 60;
  return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}h`;
}

function formatHourLabel(hour) {
  const date = new Date();
  date.setHours(hour, 0, 0, 0);
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
  }).format(date);
}

function toDateInputValue(value) {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toLocalDateTimeInputValue(value) {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const hours = `${date.getHours()}`.padStart(2, "0");
  const minutes = `${date.getMinutes()}`.padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function fromLocalDateTimeInputValue(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function toDayKey(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${`${date.getMonth() + 1}`.padStart(2, "0")}-${`${date.getDate()}`.padStart(2, "0")}`;
}

function startOfWeek(value) {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  return date;
}

function addDays(value, count) {
  const date = new Date(value);
  date.setDate(date.getDate() + count);
  return date;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
