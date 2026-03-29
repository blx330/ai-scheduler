const state = {
  users: [],
  connections: {},
  calendars: {},
  latestRun: null,
  latestOrganizerId: null,
};

const flash = document.getElementById("flash");
const userForm = document.getElementById("user-form");
const usersList = document.getElementById("users-list");
const organizerSelect = document.getElementById("organizer-select");
const attendeesList = document.getElementById("attendees-list");
const scheduleForm = document.getElementById("schedule-form");
const results = document.getElementById("results");

document.getElementById("timezone").value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
document.getElementById("deadline-at").value = defaultDeadlineValue();

userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await createUser();
  } catch (error) {
    showFlash(error.message, true);
  }
});

scheduleForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await findSlots();
  } catch (error) {
    showFlash(error.message, true);
  }
});

window.addEventListener("load", async () => {
  showCallbackMessage();
  try {
    await refreshUsers();
  } catch (error) {
    state.users = [];
    renderUsers();
    renderScheduleInputs();
    showFlash(error.message, true);
  }
});

async function apiFetch(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

async function createUser() {
  const payload = {
    display_name: document.getElementById("display-name").value.trim(),
    email: document.getElementById("email").value.trim(),
    timezone: document.getElementById("timezone").value.trim(),
  };
  await apiFetch("/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  userForm.reset();
  document.getElementById("timezone").value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  showFlash("User created.");
  await refreshUsers();
}

async function refreshUsers() {
  state.users = await apiFetch("/users");
  await Promise.all(
    state.users.map(async (user) => {
      try {
        state.connections[user.id] = await apiFetch(`/users/${user.id}/google/connection`);
      } catch (_error) {
        state.connections[user.id] = {
          connected: false,
          status: "error",
          account_email: null,
          selected_busy_calendar_ids: [],
          selected_write_calendar_id: null,
          token_expires_at: null,
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
    })
  );
  renderUsers();
  renderScheduleInputs();
}

function renderUsers() {
  if (!state.users.length) {
    usersList.innerHTML = "<p class='subtle'>No users yet. Create at least an organizer and one attendee.</p>";
    return;
  }

  usersList.innerHTML = state.users
    .map((user) => {
      const connection = state.connections[user.id];
      const calendars = state.calendars[user.id] || [];
      const busySelections = new Set(connection?.selected_busy_calendar_ids || []);
      const writeSelection = connection?.selected_write_calendar_id || "";
      const writableCalendars = calendars.filter((item) => ["owner", "writer"].includes(item.access_role));

      return `
        <div class="user-card">
          <div class="row">
            <strong>${escapeHtml(user.display_name)}</strong>
            <span>${escapeHtml(user.email || "no email")}</span>
            <span>${escapeHtml(user.timezone)}</span>
            <span class="status-badge">${connection?.status || "disconnected"}</span>
          </div>
          <div class="row">
            <button type="button" data-action="connect" data-user-id="${user.id}">Connect Google</button>
            <button type="button" class="secondary" data-action="refresh-calendars" data-user-id="${user.id}">Refresh calendars</button>
          </div>
          ${
            calendars.length
              ? `
                <label>
                  Busy source calendars
                  <select multiple size="4" data-role="busy-calendars" data-user-id="${user.id}">
                    ${calendars
                      .map(
                        (calendar) => `
                          <option value="${escapeHtml(calendar.id)}" ${busySelections.has(calendar.id) ? "selected" : ""}>
                            ${escapeHtml(calendar.summary)}${calendar.primary ? " (primary)" : ""}
                          </option>
                        `
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
                        (calendar) => `
                          <option value="${escapeHtml(calendar.id)}" ${writeSelection === calendar.id ? "selected" : ""}>
                            ${escapeHtml(calendar.summary)}
                          </option>
                        `
                      )
                      .join("")}
                  </select>
                </label>
                <button type="button" class="secondary" data-action="save-calendars" data-user-id="${user.id}">Save calendar selection</button>
              `
              : "<small>After Google connect, load calendars and pick the busy source calendars plus an organizer write calendar.</small>"
          }
        </div>
      `;
    })
    .join("");

  usersList.querySelectorAll("[data-action='connect']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await beginGoogleOauth(button.dataset.userId);
      } catch (error) {
        showFlash(error.message, true);
      }
    });
  });
  usersList.querySelectorAll("[data-action='refresh-calendars']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await refreshCalendars(button.dataset.userId);
      } catch (error) {
        showFlash(error.message, true);
      }
    });
  });
  usersList.querySelectorAll("[data-action='save-calendars']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await saveCalendarSelection(button.dataset.userId);
      } catch (error) {
        showFlash(error.message, true);
      }
    });
  });
}

function renderScheduleInputs() {
  organizerSelect.innerHTML = `<option value="">Select organizer</option>${state.users
    .map((user) => `<option value="${user.id}">${escapeHtml(user.display_name)}</option>`)
    .join("")}`;

  attendeesList.innerHTML = state.users
    .map(
      (user) => `
        <label>
          <input type="checkbox" value="${user.id}" />
          ${escapeHtml(user.display_name)}
        </label>
      `
    )
    .join("");
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
  showFlash("Calendars loaded.");
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
  renderUsers();
  showFlash("Calendar selection saved.");
}

async function findSlots() {
  const organizerId = organizerSelect.value;
  const organizer = state.users.find((user) => user.id === organizerId);
  if (!organizer) {
    throwAndShow("Select an organizer.");
    return;
  }

  const selectedAttendeeIds = Array.from(attendeesList.querySelectorAll("input:checked")).map((checkbox) => checkbox.value);
  const participantIds = Array.from(new Set([organizerId, ...selectedAttendeeIds]));
  if (!participantIds.length) {
    throwAndShow("Select at least one attendee.");
    return;
  }

  const deadlineValue = document.getElementById("deadline-at").value;
  const deadlineDate = new Date(deadlineValue);
  if (Number.isNaN(deadlineDate.valueOf())) {
    throwAndShow("Choose a valid deadline.");
    return;
  }

  const preferredWeekdays = Array.from(document.querySelectorAll(".weekday-fieldset input:checked")).map((input) => input.value);
  const preferredStart = document.getElementById("preferred-start").value || null;
  const preferredEnd = document.getElementById("preferred-end").value || null;

  const requestPayload = {
    title: document.getElementById("meeting-title").value.trim(),
    organizer_user_id: organizerId,
    duration_minutes: Number(document.getElementById("duration-minutes").value),
    horizon_start: new Date().toISOString(),
    horizon_end: deadlineDate.toISOString(),
    slot_step_minutes: 30,
    daily_window_start_local: "08:00:00",
    daily_window_end_local: "18:00:00",
    preferred_weekdays: preferredWeekdays,
    preferred_time_range_start_local: preferredStart ? `${preferredStart}:00` : null,
    preferred_time_range_end_local: preferredEnd ? `${preferredEnd}:00` : null,
    participants: participantIds.map((userId) => ({ user_id: userId, role: "required" })),
  };

  const scheduleRequest = await apiFetch("/schedule-requests", {
    method: "POST",
    body: JSON.stringify(requestPayload),
  });

  const syncPayload = {
    horizon_start: requestPayload.horizon_start,
    horizon_end: requestPayload.horizon_end,
  };

  for (const userId of participantIds) {
    const connection = state.connections[userId];
    if (!connection?.connected) {
      showFlash("Some attendees are not connected to Google. They will fall back to any manual availability only.", true);
      continue;
    }
    await apiFetch(`/users/${userId}/google/sync-busy`, {
      method: "POST",
      body: JSON.stringify(syncPayload),
    });
  }

  state.latestRun = await apiFetch(`/schedule-requests/${scheduleRequest.id}/run`, {
    method: "POST",
  });
  state.latestOrganizerId = organizerId;
  renderResults();
  showFlash("Top slots generated.");
}

function renderResults() {
  if (!state.latestRun) {
    results.innerHTML = "<p class='subtle'>No run yet.</p>";
    return;
  }
  const organizer = state.users.find((user) => user.id === state.latestOrganizerId);
  const timeZone = organizer?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  if (!state.latestRun.results.length) {
    results.innerHTML = "<p class='subtle'>No feasible slots found. Check attendee connections, calendars, or deadline.</p>";
    return;
  }

  results.innerHTML = state.latestRun.results
    .map(
      (slot) => `
        <div class="result-card">
          <strong>Rank #${slot.rank}</strong>
          <div>${formatDateTime(slot.start_at, timeZone)} to ${formatDateTime(slot.end_at, timeZone)}</div>
          <div>Score: ${slot.total_score}</div>
          <div>${escapeHtml(slot.explanation)}</div>
          <button type="button" data-rank="${slot.rank}">Confirm and create event</button>
        </div>
      `
    )
    .join("");

  results.querySelectorAll("button[data-rank]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await confirmSlot(Number(button.dataset.rank));
      } catch (error) {
        showFlash(error.message, true);
      }
    });
  });
}

async function confirmSlot(rank) {
  if (!state.latestRun) {
    return;
  }
  const organizerConnection = state.connections[state.latestOrganizerId];
  const createdEvent = await apiFetch(`/schedule-runs/${state.latestRun.id}/confirm`, {
    method: "POST",
    body: JSON.stringify({
      rank,
      calendar_id: organizerConnection?.selected_write_calendar_id || null,
    }),
  });
  const link = createdEvent.html_link
    ? `<p><a href="${createdEvent.html_link}" target="_blank" rel="noreferrer">Open Google Calendar event</a></p>`
    : "";
  showFlash(`Event created in calendar ${createdEvent.calendar_id}.`, false, link);
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

function showFlash(message, isError = false, extraHtml = "") {
  flash.classList.remove("hidden", "error");
  if (isError) {
    flash.classList.add("error");
  }
  flash.innerHTML = `<div>${escapeHtml(message)}</div>${extraHtml}`;
}

function throwAndShow(message) {
  showFlash(message, true);
}

function formatDateTime(value, timeZone) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(value));
}

function defaultDeadlineValue() {
  const value = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
