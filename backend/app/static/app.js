const PARTICIPANT_COLORS = [
  "#f6d6ea",
  "#d9e7ff",
  "#fde2c5",
  "#d9f7e8",
  "#f8f2c7",
  "#e3d7fb",
  "#f8d4e6",
  "#d7f5f5",
  "#f7ddcf",
  "#d8ecdd",
];

const GRID_START_HOUR = 7;
const GRID_END_HOUR = 24;
const HOUR_ROW_HEIGHT = 84;
const TOTAL_GRID_MINUTES = (GRID_END_HOUR - GRID_START_HOUR) * 60;

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
  focusedDanceId: null,
  participantVisibility: {},
  expandedDanceIds: {},
  selectedRecommendation: null,
  selectedParticipantId: null,
  editingDanceId: null,
  weekStart: startOfWeek(new Date()),
  isRefreshing: false,
};

const flash = document.getElementById("flash");
const refreshDashboardButton = document.getElementById("refresh-dashboard");
const openSettingsButton = document.getElementById("open-settings");
const openSettingsSidebarButton = document.getElementById("open-settings-sidebar");
const userForm = document.getElementById("user-form");
const usersList = document.getElementById("users-list");
const eventsList = document.getElementById("events-list");
const participantsList = document.getElementById("participants-list");
const recommendations = document.getElementById("recommendations");
const recommendationsSubtitle = document.getElementById("recommendations-subtitle");
const calendar = document.getElementById("calendar");
const weekLabel = document.getElementById("week-label");
const openAddDanceButton = document.getElementById("open-add-dance");
const clearDanceFilterButton = document.getElementById("clear-dance-filter");

const modalOverlay = document.getElementById("modal-overlay");
const settingsModal = document.getElementById("settings-modal");
const closeSettingsModalButton = document.getElementById("close-settings-modal");

const danceModal = document.getElementById("add-dance-modal");
const danceModalTitle = document.getElementById("dance-modal-title");
const danceModalSubtitle = document.getElementById("dance-modal-subtitle");
const danceModalEyebrow = document.getElementById("dance-modal-eyebrow");
const addDanceForm = document.getElementById("add-dance-form");
const addDanceParticipants = document.getElementById("add-dance-participants");
const addDanceError = document.getElementById("add-dance-error");
const submitDanceButton = document.getElementById("submit-add-dance");
const danceEditActions = document.getElementById("dance-edit-actions");
const duplicateDanceButton = document.getElementById("duplicate-dance");
const toggleDanceStatusButton = document.getElementById("toggle-dance-status");
const archiveDanceButton = document.getElementById("archive-dance");
const deleteDanceButton = document.getElementById("delete-dance");

const participantModal = document.getElementById("participant-modal");
const participantContent = document.getElementById("participant-content");
const participantError = document.getElementById("participant-error");
const removeParticipantButton = document.getElementById("remove-participant");

const confirmModal = document.getElementById("confirm-modal");
const confirmContent = document.getElementById("confirm-content");
const confirmError = document.getElementById("confirm-error");

const timezoneInput = document.getElementById("timezone");

bindStaticListeners();

window.addEventListener("load", async () => {
  timezoneInput.value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  setDefaultDanceDeadline();
  showCallbackMessage();

  try {
    await refreshDashboard();
  } catch (error) {
    showFlash(error.message, true);
  }
});

function bindStaticListeners() {
  openSettingsButton.addEventListener("click", openSettingsModal);
  openSettingsSidebarButton.addEventListener("click", openSettingsModal);
  closeSettingsModalButton.addEventListener("click", closeModals);

  userForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await createUser();
    } catch (error) {
      showFlash(error.message, true);
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

  document.getElementById("week-prev").addEventListener("click", async () => {
    try {
      state.weekStart = addDays(state.weekStart, -7);
      await refreshSchedulerData();
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  document.getElementById("week-today").addEventListener("click", async () => {
    try {
      state.weekStart = startOfWeek(new Date());
      await refreshSchedulerData();
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  document.getElementById("week-next").addEventListener("click", async () => {
    try {
      state.weekStart = addDays(state.weekStart, 7);
      await refreshSchedulerData();
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  openAddDanceButton.addEventListener("click", openCreateDanceModal);
  clearDanceFilterButton.addEventListener("click", () => {
    state.focusedDanceId = null;
    renderSidebar();
    renderCalendar();
    renderRecommendations();
  });

  document.getElementById("close-add-dance").addEventListener("click", closeModals);
  document.getElementById("cancel-add-dance").addEventListener("click", closeModals);
  document.getElementById("close-confirm-modal").addEventListener("click", closeModals);
  document.getElementById("cancel-confirm").addEventListener("click", closeModals);
  document.getElementById("close-participant-modal").addEventListener("click", closeModals);
  document.getElementById("cancel-participant").addEventListener("click", closeModals);
  modalOverlay.addEventListener("click", closeModals);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModals();
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

  duplicateDanceButton.addEventListener("click", async () => {
    if (!state.editingDanceId) {
      return;
    }
    try {
      await duplicateDanceEvent(state.editingDanceId);
    } catch (error) {
      showInlineError(addDanceError, error.message);
    }
  });

  toggleDanceStatusButton.addEventListener("click", async () => {
    if (!state.editingDanceId) {
      return;
    }
    try {
      const event = getEventById(state.editingDanceId);
      if (!event) {
        throw new Error("Dance not found.");
      }
      const nextStatus = getToggleDanceStatusValue(event);
      await updateDanceStatus(event.id, nextStatus);
    } catch (error) {
      showInlineError(addDanceError, error.message);
    }
  });

  archiveDanceButton.addEventListener("click", async () => {
    if (!state.editingDanceId) {
      return;
    }
    try {
      const event = getEventById(state.editingDanceId);
      if (!event) {
        throw new Error("Dance not found.");
      }
      const nextStatus = event.status === "archived" ? deriveAutomaticEventStatus(event) : "archived";
      await updateDanceStatus(event.id, nextStatus);
    } catch (error) {
      showInlineError(addDanceError, error.message);
    }
  });

  deleteDanceButton.addEventListener("click", async () => {
    if (!state.editingDanceId) {
      return;
    }
    try {
      await deleteDanceEvent(state.editingDanceId);
    } catch (error) {
      showInlineError(addDanceError, error.message);
    }
  });

  document.getElementById("submit-confirm").addEventListener("click", async () => {
    try {
      await confirmRecommendation();
    } catch (error) {
      showInlineError(confirmError, error.message);
    }
  });

  removeParticipantButton.addEventListener("click", async () => {
    if (!state.selectedParticipantId) {
      return;
    }
    try {
      await removeParticipantFromApp(state.selectedParticipantId);
    } catch (error) {
      showInlineError(participantError, error.message);
    }
  });

  usersList.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("button[data-user-action]");
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
        await refreshSchedulerData();
        showFlash(`Synced ${result.synced_interval_count} busy intervals for the visible week.`);
      }
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  eventsList.addEventListener("click", async (event) => {
    const emptyAction = event.target.closest("button[data-empty-action]");
    if (emptyAction?.dataset.emptyAction === "add-dance") {
      openCreateDanceModal();
      return;
    }

    const focusButton = event.target.closest("button[data-event-focus]");
    if (focusButton) {
      const { eventId } = focusButton.dataset;
      state.focusedDanceId = state.focusedDanceId === eventId ? null : eventId;
      renderSidebar();
      renderCalendar();
      renderRecommendations();
      return;
    }

    const expandButton = event.target.closest("button[data-event-expand]");
    if (expandButton) {
      const { eventId } = expandButton.dataset;
      state.expandedDanceIds[eventId] = !state.expandedDanceIds[eventId];
      renderSidebar();
      return;
    }

    const actionButton = event.target.closest("button[data-event-action]");
    if (!actionButton) {
      return;
    }
    const { eventAction, eventId } = actionButton.dataset;
    if (!eventAction || !eventId) {
      return;
    }

    try {
      if (eventAction === "edit") {
        openEditDanceModal(eventId);
        return;
      }
      if (eventAction === "duplicate") {
        await duplicateDanceEvent(eventId);
        return;
      }
      if (eventAction === "toggle-status") {
        const danceEvent = getEventById(eventId);
        if (!danceEvent) {
          throw new Error("Dance not found.");
        }
        await updateDanceStatus(eventId, getToggleDanceStatusValue(danceEvent));
        return;
      }
      if (eventAction === "archive") {
        const danceEvent = getEventById(eventId);
        if (!danceEvent) {
          throw new Error("Dance not found.");
        }
        const nextStatus = danceEvent.status === "archived" ? deriveAutomaticEventStatus(danceEvent) : "archived";
        await updateDanceStatus(eventId, nextStatus);
        return;
      }
      if (eventAction === "delete") {
        await deleteDanceEvent(eventId);
      }
    } catch (error) {
      showFlash(error.message, true);
    }
  });

  participantsList.addEventListener("change", (event) => {
    const toggle = event.target.closest("input[data-participant-toggle]");
    if (!toggle) {
      return;
    }
    state.participantVisibility[toggle.value] = toggle.checked;
    renderCalendar();
  });

  participantsList.addEventListener("click", (event) => {
    const emptyAction = event.target.closest("button[data-empty-action]");
    if (emptyAction?.dataset.emptyAction === "settings") {
      openSettingsModal();
      return;
    }

    const manageButton = event.target.closest("button[data-participant-manage]");
    if (!manageButton) {
      return;
    }
    openParticipantModal(manageButton.dataset.participantManage);
  });

  recommendations.addEventListener("click", (event) => {
    const emptyAction = event.target.closest("button[data-empty-action]");
    if (emptyAction?.dataset.emptyAction === "add-dance") {
      openCreateDanceModal();
      return;
    }

    const focusButton = event.target.closest("button[data-focus-dance]");
    if (focusButton) {
      state.focusedDanceId = focusButton.dataset.focusDance;
      renderSidebar();
      renderCalendar();
      renderRecommendations();
      return;
    }

    const actionButton = event.target.closest("button[data-result-id]");
    if (!actionButton) {
      return;
    }
    const recommendation = getRecommendationById(actionButton.dataset.resultId);
    if (!recommendation) {
      return;
    }
    openConfirmModal(recommendation);
  });

  calendar.addEventListener("click", (event) => {
    const recommendationButton = event.target.closest("button[data-calendar-recommendation]");
    if (!recommendationButton) {
      return;
    }
    const recommendation = getRecommendationById(recommendationButton.dataset.calendarRecommendation);
    if (!recommendation) {
      return;
    }
    openConfirmModal(recommendation);
  });
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
  pruneStaleState();
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
        state.calendars[user.id] = [];
        return;
      }

      if (state.connections[user.id].connected) {
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
    state.events.map(async (danceEvent) => [danceEvent.id, await apiFetch(`/events/${danceEvent.id}/sessions`)]),
  );
  state.eventSessions = Object.fromEntries(sessionPairs);

  const syncFailures = await syncBusyForVisibleWeek(startIso, endIso);
  state.calendarOverview = await apiFetch(`/calendar/overview?start=${encodeURIComponent(startIso)}&end=${encodeURIComponent(endIso)}`);

  const planningEventIds = state.events
    .filter((danceEvent) => danceEvent.remaining_session_count > 0 && !["archived", "completed"].includes(danceEvent.status))
    .map((danceEvent) => danceEvent.id);

  state.planningRun = planningEventIds.length
    ? await apiFetch("/planning-runs", {
        method: "POST",
        body: JSON.stringify({
          event_ids: planningEventIds,
          horizon_start: startIso,
          horizon_end: endIso,
          slot_step_minutes: 60,
        }),
      })
    : null;

  if (state.focusedDanceId && !state.events.some((danceEvent) => danceEvent.id === state.focusedDanceId)) {
    state.focusedDanceId = null;
  }

  renderSidebar();
  renderCalendar();
  renderRecommendations();

  if (syncFailures.length) {
    showFlash(`Busy sync skipped for ${syncFailures.join(", ")}.`, true);
  }
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
  showFlash("Participant created.");
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

async function syncBusyForUser(userId) {
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

function renderUsers() {
  if (!state.users.length) {
    usersList.innerHTML = renderEmptyState({
      title: "No participants yet",
      description: "Create people here first so you can assign them to dances and connect their calendars.",
    });
    return;
  }

  usersList.innerHTML = state.users
    .map((user, index) => {
      const connection = state.connections[user.id] || {};
      const calendars = state.calendars[user.id] || [];
      const busySelections = new Set(connection.selected_busy_calendar_ids || []);
      const writeSelection = connection.selected_write_calendar_id || "";
      const writableCalendars = calendars.filter((calendarItem) => ["owner", "writer"].includes(calendarItem.access_role));
      const selectedCount = busySelections.size;

      return `
        <div class="user-card">
          <div class="row">
            ${renderParticipantChip(user.id, index)}
            <div class="participant-meta" style="flex: 1;">
              <strong>${escapeHtml(user.display_name)}</strong>
              <span class="subtle tiny">${escapeHtml(user.timezone)}${user.email ? ` · ${escapeHtml(user.email)}` : ""}</span>
            </div>
            <span class="status-badge ${connection.connected ? "status-scheduled" : "status-unscheduled"}">${escapeHtml(connection.status || "disconnected")}</span>
          </div>
          <div class="row">
            <button type="button" class="secondary small" data-user-action="connect" data-user-id="${user.id}">Connect Google</button>
            <button type="button" class="secondary small" data-user-action="refresh-calendars" data-user-id="${user.id}">Refresh calendars</button>
            <button type="button" class="secondary small" data-user-action="sync-busy" data-user-id="${user.id}">Sync visible week</button>
          </div>
          ${
            calendars.length
              ? `
                <div class="metric-card">
                  <span class="metric-label">Selected busy calendars</span>
                  <span class="metric-value">${selectedCount || 0} chosen</span>
                </div>
                <label>
                  Busy source calendars
                  <select multiple size="4" data-role="busy-calendars" data-user-id="${user.id}">
                    ${calendars
                      .map(
                        (calendarItem) => `
                          <option value="${escapeHtml(calendarItem.id)}" ${busySelections.has(calendarItem.id) ? "selected" : ""}>
                            ${escapeHtml(calendarItem.summary)}${calendarItem.primary ? " (primary)" : ""}
                          </option>
                        `,
                      )
                      .join("")}
                  </select>
                </label>
                <label>
                  Write calendar
                  <select data-role="write-calendar" data-user-id="${user.id}">
                    <option value="">Use primary</option>
                    ${writableCalendars
                      .map(
                        (calendarItem) => `
                          <option value="${escapeHtml(calendarItem.id)}" ${writeSelection === calendarItem.id ? "selected" : ""}>
                            ${escapeHtml(calendarItem.summary)}
                          </option>
                        `,
                      )
                      .join("")}
                  </select>
                </label>
                <button type="button" class="secondary" data-user-action="save-calendars" data-user-id="${user.id}">Save calendar selection</button>
              `
              : `<div class="subtle tiny">Connect Google, then load calendars to choose busy-source and write calendars.</div>`
          }
        </div>
      `;
    })
    .join("");
}

function renderSidebar() {
  clearDanceFilterButton.classList.toggle("hidden", !state.focusedDanceId);

  if (!state.events.length) {
    eventsList.innerHTML = renderEmptyState({
      title: "No dances scheduled yet",
      description: "Create your first dance to start global practice planning.",
      actionLabel: "Add dance",
      action: "add-dance",
    });
  } else {
    eventsList.innerHTML = state.events
      .slice()
      .sort((left, right) => left.latest_schedule_at.localeCompare(right.latest_schedule_at))
      .map((danceEvent) => renderDanceCard(danceEvent))
      .join("");
  }

  const visibleParticipants = getVisibleParticipants();
  participantsList.innerHTML = visibleParticipants.length
    ? visibleParticipants
        .map(
          (user, index) => `
            <div class="participant-row">
              ${renderParticipantChip(user.id, index)}
              <div class="participant-meta">
                <strong>${escapeHtml(user.display_name)}</strong>
                <span class="subtle tiny">${escapeHtml(user.timezone)}</span>
              </div>
              <button type="button" class="secondary small" data-participant-manage="${user.id}">Manage</button>
              <input class="toggle" type="checkbox" data-participant-toggle="true" value="${user.id}" ${
                state.participantVisibility[user.id] !== false ? "checked" : ""
              } />
            </div>
          `,
        )
        .join("")
    : renderEmptyState({
        title: "No participants in view",
        description: "Create people in Calendar Settings, then assign them to dances here.",
        actionLabel: "Open settings",
        action: "settings",
      });
}

function renderDanceCard(danceEvent) {
  const eventSessions = getSessionsForEvent(danceEvent.id);
  const isExpanded = Boolean(state.expandedDanceIds[danceEvent.id]);
  const isFocused = state.focusedDanceId === danceEvent.id;
  const participantUsers = danceEvent.participants
    .map((participant) => ({ user: getUserById(participant.user_id), role: participant.role }))
    .filter((entry) => Boolean(entry.user));
  const requiredCount = danceEvent.participants.filter((participant) => participant.role === "required").length;
  const optionalCount = Math.max(danceEvent.participants.length - requiredCount, 0);
  const effectiveStatus = danceEvent.status || deriveAutomaticEventStatus(danceEvent);

  return `
    <div class="dance-card ${isFocused ? "focused" : ""}">
      <div class="dance-header">
        <button type="button" class="secondary small icon-button" data-event-expand="true" data-event-id="${danceEvent.id}">
          ${isExpanded ? "&minus;" : "+"}
        </button>
        <div class="participant-meta">
          <button type="button" class="dance-title-button" data-event-focus="true" data-event-id="${danceEvent.id}">
            ${escapeHtml(danceEvent.name)}
          </button>
          <span class="subtle tiny">${danceEvent.confirmed_session_count}/${danceEvent.required_session_count} sessions scheduled</span>
        </div>
        <span class="status-badge status-${escapeHtml(effectiveStatus)}">${escapeHtml(formatStatusLabel(effectiveStatus))}</span>
      </div>
      <div class="dance-metrics">
        <div class="metric-card">
          <span class="metric-label">Deadline</span>
          <span class="metric-value">${formatDate(danceEvent.latest_schedule_at)}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Practice length</span>
          <span class="metric-value">${formatDurationHours(danceEvent.duration_minutes)}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Dancers</span>
          <span class="metric-value">${danceEvent.participants.length} total</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Roles</span>
          <span class="metric-value">${requiredCount} required · ${optionalCount} optional</span>
        </div>
      </div>
      ${
        isExpanded
          ? `
            <div class="dance-expanded">
              ${
                danceEvent.description
                  ? `<div class="subtle">${escapeHtml(danceEvent.description)}</div>`
                  : ""
              }
              <div class="stack compact-stack">
                <div class="subtle tiny">Participants</div>
                <div class="participant-pill-list">
                  ${participantUsers
                    .map(
                      ({ user, role }, index) => `
                        <div class="participant-pill">
                          ${renderParticipantChip(user.id, index)}
                          <div class="participant-meta" style="flex: 1;">
                            <strong>${escapeHtml(user.display_name)}</strong>
                            <span class="subtle tiny">${escapeHtml(role)}</span>
                          </div>
                        </div>
                      `,
                    )
                    .join("")}
                </div>
              </div>
              ${
                eventSessions.length
                  ? `
                    <div class="stack compact-stack">
                      <div class="subtle tiny">Confirmed practices</div>
                      <div class="session-pill-list">
                        ${eventSessions
                          .map(
                            (session) => `
                              <div class="session-pill">
                                <span class="tag locked">Confirmed</span>
                                <div class="participant-meta">
                                  <strong>${formatShortDateTime(session.start_at)}</strong>
                                  <span class="subtle tiny">${formatTime(session.start_at)} - ${formatTime(session.end_at)}</span>
                                </div>
                              </div>
                            `,
                          )
                          .join("")}
                      </div>
                    </div>
                  `
                  : ""
              }
              <div class="dance-actions">
                <button type="button" class="secondary small" data-event-action="edit" data-event-id="${danceEvent.id}">Edit</button>
                <button type="button" class="secondary small" data-event-action="duplicate" data-event-id="${danceEvent.id}">Duplicate</button>
                <button type="button" class="secondary small" data-event-action="toggle-status" data-event-id="${danceEvent.id}">
                  ${escapeHtml(getToggleDanceStatusLabel(danceEvent))}
                </button>
                <button type="button" class="secondary small" data-event-action="archive" data-event-id="${danceEvent.id}">
                  ${danceEvent.status === "archived" ? "Restore" : "Archive"}
                </button>
                <button type="button" class="danger-ghost small" data-event-action="delete" data-event-id="${danceEvent.id}">Delete</button>
              </div>
            </div>
          `
          : ""
      }
    </div>
  `;
}

function renderCalendar() {
  weekLabel.textContent = formatWeekLabel(state.weekStart);
  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(state.weekStart, index));
  const visibleBusyIntervals = state.calendarOverview.busy_intervals.filter(
    (interval) => state.participantVisibility[interval.user_id] !== false,
  );
  const focusedRecommendations = state.focusedDanceId
    ? getVisiblePlanningGroups().flatMap((group) => group.recommendations || [])
    : [];
  const hasCalendarItems =
    visibleBusyIntervals.length > 0 || state.calendarOverview.practice_sessions.length > 0 || focusedRecommendations.length > 0;

  if (!hasCalendarItems) {
    calendar.innerHTML = `
      <div class="calendar-empty">
        ${renderEmptyState({
          title: "Nothing is on this week yet",
          description: state.focusedDanceId
            ? "This week has no busy intervals, confirmed practices, or recommendation slots for the selected dance."
            : "Busy intervals and confirmed practices will appear here. Focus a dance to preview recommendation slots on the calendar.",
        })}
      </div>
    `;
    return;
  }

  const headerRow = `
    <div class="calendar-grid calendar-header-row">
      <div class="calendar-header-cell"></div>
      ${weekDays
        .map(
          (day) => `
            <div class="calendar-header-cell">
              <div class="calendar-header-day">
                <strong>${day.toLocaleDateString(undefined, { weekday: "short" })}</strong>
                <div class="subtle tiny">${day.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</div>
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;

  const gridBody = `
    <div class="calendar-grid">
      <div class="time-col">
        ${Array.from({ length: GRID_END_HOUR - GRID_START_HOUR }, (_, index) => {
          const hour = GRID_START_HOUR + index;
          return `<div class="time-cell">${formatHourLabel(hour)}</div>`;
        }).join("")}
      </div>
      ${weekDays
        .map((day) => {
          const dayKey = toDayKey(day);
          const dayBusy = layoutOverlappingItems(
            visibleBusyIntervals.filter((interval) => toDayKey(interval.start_at) === dayKey),
          );
          const dayRecommendations = layoutOverlappingItems(
            focusedRecommendations.filter((recommendation) => toDayKey(recommendation.start_at) === dayKey),
          );
          const daySessions = state.calendarOverview.practice_sessions.filter(
            (session) => toDayKey(session.start_at) === dayKey,
          );

          return `
            <div class="day-col">
              ${Array.from({ length: GRID_END_HOUR - GRID_START_HOUR }, () => `<div class="day-hour-line"></div>`).join("")}
              ${dayBusy.map(({ item, column, columnCount }) => renderBusyBlock(item, column, columnCount)).join("")}
              ${dayRecommendations
                .map(({ item, column, columnCount }) => renderRecommendationBlock(item, column, columnCount))
                .join("")}
              ${daySessions.map((session) => renderConfirmedBlock(session)).join("")}
            </div>
          `;
        })
        .join("")}
    </div>
  `;

  calendar.innerHTML = `${headerRow}${gridBody}`;
}

function renderRecommendations() {
  if (!state.events.length) {
    recommendationsSubtitle.textContent = "Add a dance to begin planning.";
    recommendations.innerHTML = renderEmptyState({
      title: "No dance data yet",
      description: "Create a dance from the sidebar to generate AI-ranked practice options.",
      actionLabel: "Add dance",
      action: "add-dance",
    });
    return;
  }

  if (!state.focusedDanceId) {
    const remainingEvents = state.events.filter(
      (danceEvent) => danceEvent.remaining_session_count > 0 && !["archived", "completed"].includes(danceEvent.status),
    );
    recommendationsSubtitle.textContent = "Choose a dance to inspect the ranked options for that practice plan.";
    recommendations.innerHTML = `
      <div class="summary-card">
        <strong>Select a dance from the left sidebar</strong>
        <div class="subtle">The calendar keeps the full team view, but this panel stays focused on one dance at a time.</div>
      </div>
      ${
        remainingEvents.length
          ? remainingEvents
              .map(
                (danceEvent) => `
                  <div class="summary-card">
                    <div class="row" style="justify-content: space-between;">
                      <div class="participant-meta" style="flex: 1;">
                        <strong>${escapeHtml(danceEvent.name)}</strong>
                        <span class="subtle tiny">${danceEvent.remaining_session_count} practice${danceEvent.remaining_session_count === 1 ? "" : "s"} still need scheduling</span>
                      </div>
                      <button type="button" class="secondary small" data-focus-dance="${danceEvent.id}">Inspect</button>
                    </div>
                  </div>
                `,
              )
              .join("")
          : renderEmptyState({
              title: "All active dances are already scheduled",
              description: "Confirmed practices are locked into the calendar, so there are no open recommendation queues right now.",
            })
      }
    `;
    return;
  }

  const focusedEvent = getEventById(state.focusedDanceId);
  const groups = getVisiblePlanningGroups();
  recommendationsSubtitle.textContent = focusedEvent
    ? `${focusedEvent.confirmed_session_count}/${focusedEvent.required_session_count} sessions confirmed`
    : "Current planning run";

  if (!groups.length) {
    recommendations.innerHTML = renderEmptyState({
      title: "No recommendations in this week",
      description: "Try a different week, sync more calendar data, or adjust the dance deadline and participants.",
    });
    return;
  }

  recommendations.innerHTML = groups
    .map((group) => {
      const [bestOption, ...alternatives] = group.recommendations || [];
      return `
        <section class="recommendation-group">
          <div class="participant-meta">
            <strong>${escapeHtml(group.dance_name)} · Practice ${group.session_index}</strong>
            <span class="subtle tiny">Best option first, followed by alternatives for the selected dance.</span>
          </div>
          ${bestOption ? renderRecommendationCard(bestOption, true) : ""}
          ${alternatives.map((recommendation) => renderRecommendationCard(recommendation, false)).join("")}
        </section>
      `;
    })
    .join("");
}

function openSettingsModal() {
  danceModal.classList.add("hidden");
  participantModal.classList.add("hidden");
  confirmModal.classList.add("hidden");
  settingsModal.classList.remove("hidden");
  modalOverlay.classList.remove("hidden");
}

function openCreateDanceModal() {
  if (!state.users.length) {
    showFlash("Create at least one participant before adding a dance.", true);
    openSettingsModal();
    return;
  }

  settingsModal.classList.add("hidden");
  participantModal.classList.add("hidden");
  confirmModal.classList.add("hidden");
  state.editingDanceId = null;
  addDanceForm.reset();
  setDefaultDanceDeadline();
  renderDanceParticipantSelectors();
  danceModalEyebrow.textContent = "Dance Setup";
  danceModalTitle.textContent = "Add New Dance";
  danceModalSubtitle.textContent = "Create a dance event for the multi-practice planner.";
  submitDanceButton.textContent = "Create dance";
  danceEditActions.classList.add("hidden");
  hideInlineError(addDanceError);
  danceModal.classList.remove("hidden");
  modalOverlay.classList.remove("hidden");
}

function openEditDanceModal(eventId) {
  const danceEvent = getEventById(eventId);
  if (!danceEvent) {
    showFlash("Dance not found.", true);
    return;
  }

  settingsModal.classList.add("hidden");
  participantModal.classList.add("hidden");
  confirmModal.classList.add("hidden");
  state.editingDanceId = danceEvent.id;
  danceModalEyebrow.textContent = "Dance Management";
  danceModalTitle.textContent = `Edit ${danceEvent.name}`;
  danceModalSubtitle.textContent = "Update details, participant roles, and lifecycle actions for this dance.";
  submitDanceButton.textContent = "Save changes";
  danceEditActions.classList.remove("hidden");

  document.getElementById("dance-name").value = danceEvent.name;
  document.getElementById("dance-session-count").value = danceEvent.required_session_count;
  document.getElementById("dance-duration-hours").value = `${danceEvent.duration_minutes / 60}`;
  document.getElementById("dance-deadline").value = toDateInputValue(danceEvent.latest_schedule_at);
  document.getElementById("dance-description").value = danceEvent.description || "";
  renderDanceParticipantSelectors(
    Object.fromEntries(danceEvent.participants.map((participant) => [participant.user_id, participant.role])),
  );
  updateDanceActionButtons(danceEvent);
  hideInlineError(addDanceError);
  danceModal.classList.remove("hidden");
  modalOverlay.classList.remove("hidden");
}

function renderDanceParticipantSelectors(selectedRoles = {}) {
  addDanceParticipants.innerHTML = state.users
    .map(
      (user, index) => `
        <div class="participant-selector-row">
          ${renderParticipantChip(user.id, index)}
          <div class="participant-meta">
            <strong>${escapeHtml(user.display_name)}</strong>
            <span class="subtle tiny">${escapeHtml(user.timezone)}</span>
          </div>
          <select data-dance-participant="${user.id}">
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
  const notes = document.getElementById("dance-description").value.trim();

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

  const editingEvent = state.editingDanceId ? getEventById(state.editingDanceId) : null;
  const payload = {
    name,
    description: notes || null,
    organizer_user_id: editingEvent?.organizer_user_id || state.users[0].id,
    duration_minutes: Math.round(durationHours * 60),
    latest_schedule_at: new Date(`${deadline}T23:59:59`).toISOString(),
    required_session_count: requiredSessionCount,
    participants,
  };

  const response = state.editingDanceId
    ? await apiFetch(`/events/${state.editingDanceId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      })
    : await apiFetch("/events", {
        method: "POST",
        body: JSON.stringify(payload),
      });

  state.focusedDanceId = response.id;
  closeModals();
  await refreshSchedulerData();
  showFlash(isEditing ? "Dance updated." : "Dance created.");
}

async function duplicateDanceEvent(eventId) {
  const danceEvent = getEventById(eventId);
  if (!danceEvent) {
    throw new Error("Dance not found.");
  }

  const duplicated = await apiFetch("/events", {
    method: "POST",
    body: JSON.stringify({
      name: `${danceEvent.name} Copy`,
      description: danceEvent.description,
      organizer_user_id: danceEvent.organizer_user_id,
      duration_minutes: danceEvent.duration_minutes,
      latest_schedule_at: danceEvent.latest_schedule_at,
      required_session_count: danceEvent.required_session_count,
      participants: danceEvent.participants,
    }),
  });

  state.focusedDanceId = duplicated.id;
  closeModals();
  await refreshSchedulerData();
  showFlash("Dance duplicated.");
}

async function updateDanceStatus(eventId, status) {
  await apiFetch(`/events/${eventId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });

  closeModals();
  await refreshSchedulerData();
  showFlash(`Dance marked ${formatStatusLabel(status).toLowerCase()}.`);
}

async function deleteDanceEvent(eventId) {
  const danceEvent = getEventById(eventId);
  if (!danceEvent) {
    throw new Error("Dance not found.");
  }
  if (!window.confirm(`Delete "${danceEvent.name}"? This removes its confirmed sessions and recommendations.`)) {
    return;
  }

  await apiFetch(`/events/${eventId}`, { method: "DELETE" });
  if (state.focusedDanceId === eventId) {
    state.focusedDanceId = null;
  }
  closeModals();
  await refreshSchedulerData();
  showFlash("Dance deleted.");
}

function openParticipantModal(userId) {
  const user = getUserById(userId);
  if (!user) {
    showFlash("Participant not found.", true);
    return;
  }

  settingsModal.classList.add("hidden");
  danceModal.classList.add("hidden");
  confirmModal.classList.add("hidden");
  state.selectedParticipantId = userId;
  hideInlineError(participantError);
  const danceMemberships = getUserDanceMemberships(userId);
  const organizerCount = state.events.filter((danceEvent) => danceEvent.organizer_user_id === userId).length;
  const canRemove = danceMemberships.length === 0 && organizerCount === 0;

  participantContent.innerHTML = `
    <div class="participant-pill">
      ${renderParticipantChip(user.id, state.users.findIndex((candidate) => candidate.id === user.id))}
      <div class="participant-meta">
        <strong>${escapeHtml(user.display_name)}</strong>
        <span class="subtle tiny">${escapeHtml(user.timezone)}${user.email ? ` · ${escapeHtml(user.email)}` : ""}</span>
      </div>
    </div>
    <div class="metric-card">
      <span class="metric-label">Current dance assignments</span>
      <span class="metric-value">${danceMemberships.length}</span>
    </div>
    ${
      organizerCount
        ? `
          <div class="inline-error">
            This person is still the organizer for ${organizerCount} dance${organizerCount === 1 ? "" : "s"}. Reassign or delete those dances before removing them globally.
          </div>
        `
        : ""
    }
    ${
      danceMemberships.length
        ? `
          <div class="stack compact-stack">
            <div class="subtle tiny">Assigned dances</div>
            ${danceMemberships
              .map(
                (danceEvent) => `
                  <div class="session-pill">
                    <div class="participant-meta">
                      <strong>${escapeHtml(danceEvent.name)}</strong>
                      <span class="subtle tiny">${escapeHtml(
                        danceEvent.participants.find((participant) => participant.user_id === userId)?.role || "participant",
                      )}</span>
                    </div>
                    <button type="button" class="secondary small" data-focus-dance="${danceEvent.id}">Edit dance</button>
                  </div>
                `,
              )
              .join("")}
          </div>
        `
        : `<div class="subtle">This participant is not currently assigned to any dance.</div>`
    }
  `;

  removeParticipantButton.disabled = !canRemove;
  participantModal.classList.remove("hidden");
  modalOverlay.classList.remove("hidden");

  participantContent.querySelectorAll("button[data-focus-dance]").forEach((button) => {
    button.addEventListener("click", () => {
      closeModals();
      state.focusedDanceId = button.dataset.focusDance;
      openEditDanceModal(button.dataset.focusDance);
      renderSidebar();
      renderCalendar();
      renderRecommendations();
    });
  });
}

async function removeParticipantFromApp(userId) {
  const user = getUserById(userId);
  if (!user) {
    throw new Error("Participant not found.");
  }
  if (!window.confirm(`Remove ${user.display_name} from the app?`)) {
    return;
  }

  await apiFetch(`/users/${userId}`, { method: "DELETE" });
  closeModals();
  await refreshDashboard();
  showFlash("Participant removed from the app.");
}

function openConfirmModal(recommendation) {
  settingsModal.classList.add("hidden");
  danceModal.classList.add("hidden");
  participantModal.classList.add("hidden");
  state.selectedRecommendation = recommendation;
  hideInlineError(confirmError);

  const danceEvent = getEventById(recommendation.dance_event_id);
  const missingNames = (recommendation.missing_required_user_ids || []).map((userId) => {
    const user = getUserById(userId);
    return user ? user.display_name : "Missing participant";
  });

  confirmContent.innerHTML = `
    <div class="confirm-summary">
      <div class="row" style="justify-content: space-between; align-items: flex-start;">
        <div class="participant-meta">
          <strong>${escapeHtml(recommendation.dance_name)}</strong>
          <span class="subtle tiny">Practice ${recommendation.session_index}</span>
        </div>
        <div class="score ${scoreClass(recommendation.total_score)}">${Number(recommendation.total_score).toFixed(2)}</div>
      </div>
      <div>${formatShortDateTime(recommendation.start_at)} - ${formatTime(recommendation.end_at)}</div>
      <div class="row">
        <span class="tag best">${recommendation.rank === 1 ? "Best option" : `Option ${recommendation.rank}`}</span>
        ${recommendation.is_fallback ? `<span class="tag fallback">Fallback</span>` : ""}
      </div>
      ${
        missingNames.length
          ? `<div class="subtle">Missing required participant${missingNames.length === 1 ? "" : "s"}: ${escapeHtml(missingNames.join(", "))}</div>`
          : ""
      }
      ${
        danceEvent
          ? `<div class="subtle tiny">${danceEvent.confirmed_session_count}/${danceEvent.required_session_count} sessions already confirmed for this dance.</div>`
          : ""
      }
    </div>
    <div class="reason-list">
      ${(recommendation.explanation?.reasons || [])
        .slice(0, 3)
        .map((reason) => `<div>${escapeHtml(reason.message)}</div>`)
        .join("") || `<div>${escapeHtml(recommendation.explanation?.summary || "Selected from the current planning run.")}</div>`}
    </div>
  `;

  confirmModal.classList.remove("hidden");
  modalOverlay.classList.remove("hidden");
}

async function confirmRecommendation() {
  hideInlineError(confirmError);
  if (!state.selectedRecommendation || !state.planningRun) {
    throw new Error("No recommendation selected.");
  }

  await apiFetch(`/planning-runs/${state.planningRun.id}/confirm`, {
    method: "POST",
    body: JSON.stringify({
      result_ids: [state.selectedRecommendation.id],
    }),
  });

  closeModals();
  await refreshSchedulerData();
  showFlash("Practice session confirmed.");
}

function closeModals() {
  settingsModal.classList.add("hidden");
  danceModal.classList.add("hidden");
  participantModal.classList.add("hidden");
  confirmModal.classList.add("hidden");
  modalOverlay.classList.add("hidden");

  state.selectedRecommendation = null;
  state.selectedParticipantId = null;
  state.editingDanceId = null;

  addDanceForm.reset();
  setDefaultDanceDeadline();
  submitDanceButton.textContent = "Create dance";
  danceEditActions.classList.add("hidden");
  hideInlineError(addDanceError);
  hideInlineError(confirmError);
  hideInlineError(participantError);
}

function renderRecommendationCard(recommendation, isBest) {
  const missingNames = (recommendation.missing_required_user_ids || []).map((userId) => {
    const user = getUserById(userId);
    return user ? user.display_name : "Missing participant";
  });
  const reasons = (recommendation.explanation?.reasons || [])
    .slice(0, 3)
    .map((reason) => `<div>${escapeHtml(reason.message)}</div>`)
    .join("");

  return `
    <div class="recommendation-card ${isBest ? "best" : ""}">
      <div class="recommendation-card-header">
        <div class="participant-meta" style="flex: 1;">
          <strong>${escapeHtml(getWeekday(recommendation.start_at))}</strong>
          <span>${formatTime(recommendation.start_at)} - ${formatTime(recommendation.end_at)}</span>
          <span class="subtle tiny">${escapeHtml(recommendation.explanation?.summary || "Ranked from availability and preferences.")}</span>
        </div>
        <div>
          <div class="score ${scoreClass(recommendation.total_score)}">${Number(recommendation.total_score).toFixed(2)}</div>
          <div class="subtle tiny">planner score</div>
        </div>
      </div>
      <div class="row">
        ${isBest ? `<span class="tag best">Best option</span>` : ""}
        ${recommendation.is_fallback ? `<span class="tag fallback">Fallback</span>` : ""}
      </div>
      <div class="reason-list">
        ${reasons || `<div>${escapeHtml(recommendation.explanation?.summary || "")}</div>`}
        ${
          missingNames.length
            ? `<div>Missing required participant${missingNames.length === 1 ? "" : "s"}: ${escapeHtml(missingNames.join(", "))}</div>`
            : ""
        }
      </div>
      <button type="button" data-result-id="${recommendation.id}">Select this time</button>
    </div>
  `;
}

function renderBusyBlock(interval, column, columnCount) {
  const placement = getPlacement(interval.start_at, interval.end_at);
  if (!placement) {
    return "";
  }
  const user = getUserById(interval.user_id);
  const index = state.users.findIndex((candidate) => candidate.id === interval.user_id);
  return `
    <div
      class="calendar-block busy"
      style="${blockPlacementStyle(placement, column, columnCount)} background:${getParticipantColor(index)}88;"
    >
      <div class="block-title">${escapeHtml(user ? user.display_name : "Busy")}</div>
      <div class="block-subtitle">Busy · ${formatTime(interval.start_at)} - ${formatTime(interval.end_at)}</div>
    </div>
  `;
}

function renderRecommendationBlock(recommendation, column, columnCount) {
  const placement = getPlacement(recommendation.start_at, recommendation.end_at);
  if (!placement) {
    return "";
  }

  return `
    <button
      type="button"
      class="calendar-block recommendation"
      data-calendar-recommendation="${recommendation.id}"
      style="${blockPlacementStyle(placement, column, columnCount, 6)}"
    >
      <div class="block-title">${escapeHtml(recommendation.dance_name)}</div>
      <div class="block-subtitle">${formatTime(recommendation.start_at)} - ${formatTime(recommendation.end_at)}</div>
      <div class="block-subtitle">${recommendation.rank === 1 ? "Best option" : `Option ${recommendation.rank}`}</div>
    </button>
  `;
}

function renderConfirmedBlock(session) {
  const placement = getPlacement(session.start_at, session.end_at);
  if (!placement) {
    return "";
  }
  const danceEvent = getEventById(session.dance_event_id);
  const isFocused = !state.focusedDanceId || session.dance_event_id === state.focusedDanceId;
  return `
    <div
      class="calendar-block confirmed"
      style="top:${placement.top}px;height:${placement.height}px;left:4px;right:4px;opacity:${isFocused ? 1 : 0.78};"
    >
      <div class="block-title">${escapeHtml(danceEvent ? danceEvent.name : "Practice session")}</div>
      <div class="block-subtitle">${formatTime(session.start_at)} - ${formatTime(session.end_at)}</div>
      <div class="block-subtitle">Confirmed practice</div>
    </div>
  `;
}

function getVisiblePlanningGroups() {
  if (!state.planningRun?.results || !state.focusedDanceId) {
    return [];
  }
  return state.planningRun.results.filter((group) => group.dance_event_id === state.focusedDanceId);
}

function getRecommendationById(resultId) {
  return buildRecommendationIndex()[resultId] || null;
}

function buildRecommendationIndex() {
  const results = state.planningRun?.results || [];
  return Object.fromEntries(
    results
      .flatMap((group) => group.recommendations || [])
      .map((recommendation) => [recommendation.id, recommendation]),
  );
}

function getVisibleParticipants() {
  if (!state.events.length) {
    return state.users;
  }
  const visibleEventIds = state.focusedDanceId
    ? [state.focusedDanceId]
    : state.events.map((danceEvent) => danceEvent.id);
  const participantIds = new Set();
  visibleEventIds.forEach((eventId) => {
    const danceEvent = getEventById(eventId);
    (danceEvent?.participants || []).forEach((participant) => participantIds.add(participant.user_id));
  });

  if (!participantIds.size) {
    return state.users;
  }
  return state.users.filter((user) => participantIds.has(user.id));
}

function getEventById(eventId) {
  return state.events.find((danceEvent) => danceEvent.id === eventId) || null;
}

function getSessionsForEvent(eventId) {
  return (state.eventSessions[eventId] || []).slice().sort((left, right) => left.start_at.localeCompare(right.start_at));
}

function getUserDanceMemberships(userId) {
  return state.events.filter((danceEvent) => danceEvent.participants.some((participant) => participant.user_id === userId));
}

function mergeParticipantVisibility() {
  state.users.forEach((user) => {
    if (!(user.id in state.participantVisibility)) {
      state.participantVisibility[user.id] = true;
    }
  });
}

function pruneStaleState() {
  const validUserIds = new Set(state.users.map((user) => user.id));
  Object.keys(state.participantVisibility).forEach((userId) => {
    if (!validUserIds.has(userId)) {
      delete state.participantVisibility[userId];
    }
  });
  Object.keys(state.connections).forEach((userId) => {
    if (!validUserIds.has(userId)) {
      delete state.connections[userId];
      delete state.calendars[userId];
    }
  });
}

function updateDanceActionButtons(danceEvent) {
  toggleDanceStatusButton.textContent = getToggleDanceStatusLabel(danceEvent);
  archiveDanceButton.textContent = danceEvent.status === "archived" ? "Restore" : "Archive";
}

function getToggleDanceStatusLabel(danceEvent) {
  return ["completed", "archived"].includes(danceEvent.status) ? "Reopen dance" : "Mark complete";
}

function getToggleDanceStatusValue(danceEvent) {
  return ["completed", "archived"].includes(danceEvent.status) ? deriveAutomaticEventStatus(danceEvent) : "completed";
}

function deriveAutomaticEventStatus(danceEvent) {
  if (danceEvent.confirmed_session_count <= 0) {
    return "unscheduled";
  }
  if (danceEvent.confirmed_session_count >= danceEvent.required_session_count) {
    return "scheduled";
  }
  return "partially_scheduled";
}

function layoutOverlappingItems(items) {
  const sortedItems = [...items].sort((left, right) => {
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

  sortedItems.forEach((item) => {
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

function blockPlacementStyle(placement, column, columnCount, inset = 4) {
  const width = 100 / columnCount;
  return [
    `top:${placement.top}px`,
    `height:${placement.height}px`,
    `left:calc(${width * column}% + ${inset}px)`,
    `width:calc(${width}% - ${inset * 2}px)`,
  ].join(";");
}

function renderEmptyState({ title, description, actionLabel = "", action = "" }) {
  return `
    <div class="empty-state">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(description)}</p>
      ${
        actionLabel && action
          ? `<button type="button" class="secondary small empty-state-action" data-empty-action="${escapeHtml(action)}">${escapeHtml(actionLabel)}</button>`
          : ""
      }
    </div>
  `;
}

function renderParticipantChip(userId, fallbackIndex = 0) {
  const user = getUserById(userId);
  const index = state.users.findIndex((candidate) => candidate.id === userId);
  const background = getParticipantColor(index >= 0 ? index : fallbackIndex);
  return `<span class="participant-chip" style="background:${background};">${escapeHtml(getInitials(user?.display_name || "User"))}</span>`;
}

function getUserById(userId) {
  return state.users.find((user) => user.id === userId) || null;
}

function getParticipantColor(index) {
  return PARTICIPANT_COLORS[Math.max(index, 0) % PARTICIPANT_COLORS.length];
}

function updateRefreshButton() {
  refreshDashboardButton.disabled = state.isRefreshing;
  refreshDashboardButton.textContent = state.isRefreshing ? "Refreshing..." : "Refresh data";
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
  flash.classList.remove("hidden", "error");
  flash.classList.toggle("error", isError);
  flash.innerHTML = `<div>${escapeHtml(message)}</div>`;
}

function showInlineError(element, message) {
  element.textContent = message;
  element.classList.remove("hidden");
}

function hideInlineError(element) {
  element.textContent = "";
  element.classList.add("hidden");
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

function scoreClass(score) {
  const value = Number(score);
  if (value >= 2.5) {
    return "good";
  }
  if (value >= 1.5) {
    return "ok";
  }
  return "low";
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function formatShortDateTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
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

function formatWeekLabel(weekStart) {
  const weekEnd = addDays(weekStart, 6);
  return `${weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${weekEnd.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
}

function formatHourLabel(hour) {
  if (hour === 12) {
    return "12 PM";
  }
  if (hour > 12) {
    return `${hour - 12} PM`;
  }
  return `${hour} AM`;
}

function formatStatusLabel(status) {
  return status.replaceAll("_", " ");
}

function getWeekday(value) {
  return new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(new Date(value));
}

function startOfWeek(date) {
  const copy = new Date(date);
  const day = copy.getDay();
  const offset = (day + 6) % 7;
  copy.setHours(0, 0, 0, 0);
  copy.setDate(copy.getDate() - offset);
  return copy;
}

function addDays(date, amount) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + amount);
  return copy;
}

function toDayKey(dateLike) {
  const date = new Date(dateLike);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function toDateInputValue(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function getInitials(displayName) {
  return displayName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() || "")
    .join("");
}

function setDefaultDanceDeadline() {
  const deadline = addDays(new Date(), 7);
  document.getElementById("dance-deadline").value = `${deadline.getFullYear()}-${String(deadline.getMonth() + 1).padStart(2, "0")}-${String(deadline.getDate()).padStart(2, "0")}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
