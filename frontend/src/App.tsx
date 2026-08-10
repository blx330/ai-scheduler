import { Navigate, Route, Routes } from "react-router-dom";

import { LoginPage } from "@/components/auth/LoginPage";
import { AppShell } from "@/components/layout/AppShell";
import { MembersPage } from "@/pages/MembersPage";
import { MemberDetailPage } from "@/pages/MemberDetailPage";
import { EventsPage } from "@/pages/EventsPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { useCurrentUser } from "@/hooks/use-auth";
import { useOAuthRedirect } from "@/hooks/use-oauth-redirect";

function App() {
  useOAuthRedirect();
  const { data: currentUser, isLoading } = useCurrentUser();

  if (isLoading) {
    return <div className="h-svh flex items-center justify-center text-sm text-muted-foreground">Loading…</div>;
  }

  if (!currentUser) {
    return <LoginPage />;
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/calendar" replace />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/members/:userId" element={<MemberDetailPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/events/:eventId" element={<EventsPage />} />
        <Route path="*" element={<Navigate to="/calendar" replace />} />
      </Routes>
    </AppShell>
  );
}

export default App;
