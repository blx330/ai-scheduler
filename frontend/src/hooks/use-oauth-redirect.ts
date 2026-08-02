import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { queryKeys } from "./query-keys";

/**
 * Handle the params the Google OAuth callback redirects back with.
 *
 * The backend redirects to the app root with `?google_connected=1&user_id=...` on
 * success or `?google_error=...` on failure. Nothing read them, so a successful
 * connection left the UI showing "disconnected" until its cache went stale, and a
 * failed one gave the user no indication at all.
 */
export function useOAuthRedirect() {
  const queryClient = useQueryClient();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("google_connected");
    const error = params.get("google_error");
    if (!connected && !error) return;
    handled.current = true;

    if (error) {
      toast.error(`Google Calendar connection failed: ${error}`);
    } else {
      const userId = params.get("user_id");
      if (userId) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.googleConnection(userId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.googleCalendars(userId) });
      }
      toast.success("Google Calendar connected");
    }

    // drop the params so a reload doesn't replay the toast
    const url = new URL(window.location.href);
    for (const key of ["google_connected", "google_error", "user_id"]) url.searchParams.delete(key);
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  }, [queryClient]);
}
