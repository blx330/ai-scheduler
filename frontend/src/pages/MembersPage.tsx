import { useNavigate } from "react-router-dom";

import { Card, CardContent } from "@/components/ui/card";
import { CreateMemberDialog } from "@/components/people/CreateMemberDialog";
import { useUsers } from "@/hooks/use-users";

function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function MembersPage() {
  const { data: users, isLoading, isError } = useUsers();
  const navigate = useNavigate();

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Dashboard / Members</p>
          <h2 className="text-2xl font-bold tracking-tight">Members</h2>
        </div>
        <CreateMemberDialog />
      </div>

      <Card className="p-2">
        <CardContent className="px-0">
          {isLoading && <p className="text-sm text-muted-foreground px-4 py-3">Loading members...</p>}
          {isError && <p className="text-sm text-destructive px-4 py-3">Failed to load members.</p>}
          {users && users.length === 0 && (
            <p className="text-sm text-muted-foreground px-4 py-3">No members yet. Add your first dancer.</p>
          )}
          {users?.map((user) => (
            <button
              key={user.id}
              type="button"
              onClick={() => navigate(`/members/${user.id}`)}
              className="w-full flex items-center gap-3.5 px-4 py-3.5 border-b last:border-b-0 text-left hover:bg-accent/40 transition-colors"
            >
              <div className="size-9 rounded-full bg-black/[0.06] border flex items-center justify-center font-bold text-sm text-foreground/70 shrink-0">
                {initialsFor(user.display_name)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold">{user.display_name}</div>
                <div className="text-xs text-muted-foreground truncate">
                  {user.email ?? "No email"} &middot; {user.timezone}
                </div>
              </div>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
