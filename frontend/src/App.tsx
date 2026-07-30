import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { MembersPage } from "@/pages/MembersPage";
import { MemberDetailPage } from "@/pages/MemberDetailPage";
import { EventsPage } from "@/pages/EventsPage";
import { EventDetailPage } from "@/pages/EventDetailPage";
import { PlanningPage } from "@/pages/PlanningPage";
import { CalendarPage } from "@/pages/CalendarPage";

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/members" replace />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/members/:userId" element={<MemberDetailPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/events/:eventId" element={<EventDetailPage />} />
        <Route path="/planning" element={<PlanningPage />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="*" element={<Navigate to="/members" replace />} />
      </Routes>
    </AppShell>
  );
}

export default App;
