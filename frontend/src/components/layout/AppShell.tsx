import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { CalendarDays, ListChecks, Sparkles, Users } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/members", label: "Members", icon: Users },
  { to: "/events", label: "Events", icon: ListChecks },
  { to: "/planning", label: "Planning", icon: Sparkles },
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh flex flex-col md:flex-row">
      <aside className="md:w-56 shrink-0 border-b md:border-b-0 md:border-r bg-card">
        <div className="p-4">
          <h1 className="text-lg font-semibold leading-tight">AI Scheduler</h1>
          <p className="text-xs text-muted-foreground">Dance practice planning</p>
        </div>
        <nav className="flex md:flex-col gap-1 px-2 pb-4 overflow-x-auto md:overflow-visible">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )
              }
            >
              <item.icon className="size-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 min-w-0 p-4 md:p-6">{children}</main>
    </div>
  );
}
