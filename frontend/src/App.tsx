import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { MembersPage } from "@/pages/MembersPage";
import { MemberDetailPage } from "@/pages/MemberDetailPage";
import { EventsPage } from "@/pages/EventsPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { useOAuthRedirect } from "@/hooks/use-oauth-redirect";

function App() {
  useOAuthRedirect();
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
