import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { CalendarDays, ListChecks, LogOut, User } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useCurrentUser, useLogout } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import { DemoModeBanner } from "./DemoModeBanner";

const NAV_ITEMS = [
  { to: "/calendar", label: "Calendar", icon: CalendarDays },
  { to: "/members", label: "Members", icon: User },
  { to: "/events", label: "Events", icon: ListChecks },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { data: currentUser } = useCurrentUser();
  const logout = useLogout();

  return (
    <div className="h-svh flex flex-col bg-background">
      <DemoModeBanner />
      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        <aside className="md:w-64 shrink-0 border-b md:border-b-0 md:border-r border-black/5 flex flex-col">
          <div className="p-5 pb-6">
            <div className="text-lg font-bold tracking-tight">AI Scheduler</div>
            <div className="text-xs text-muted-foreground mt-0.5">Dance practice planning</div>
          </div>
          <nav className="flex md:flex-col gap-1 px-3 pb-4 overflow-x-auto md:overflow-visible">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-semibold whitespace-nowrap transition-colors",
                    isActive
                      ? "bg-secondary text-primary"
                      : "text-foreground/65 hover:bg-accent/60",
                  )
                }
              >
                <item.icon className="size-4" />
                {item.label}
              </NavLink>
            ))}
          </nav>
          {currentUser ? (
            <div className="mt-auto p-3 border-t border-black/5 flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold truncate">{currentUser.display_name}</div>
                <div className="text-xs text-muted-foreground capitalize">{currentUser.role}</div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                title="Sign out"
                onClick={() => logout.mutate()}
                disabled={logout.isPending}
              >
                <LogOut />
              </Button>
            </div>
          ) : null}
        </aside>
        <main className="flex-1 min-w-0 min-h-0 overflow-y-auto p-6 md:p-8 pb-14 flex flex-col">{children}</main>
      </div>
    </div>
  );
}
