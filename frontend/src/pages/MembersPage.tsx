import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreateMemberDialog } from "@/components/people/CreateMemberDialog";
import { useUsers } from "@/hooks/use-users";

export function MembersPage() {
  const { data: users, isLoading, isError } = useUsers();
  const navigate = useNavigate();

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Members</h2>
          <p className="text-sm text-muted-foreground">
            Manage dancers, their timezones, and practice-time preferences.
          </p>
        </div>
        <CreateMemberDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All members</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-sm text-muted-foreground">Loading members...</p>}
          {isError && <p className="text-sm text-destructive">Failed to load members.</p>}
          {users && users.length === 0 && (
            <p className="text-sm text-muted-foreground">No members yet. Add your first dancer.</p>
          )}
          {users && users.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Timezone</TableHead>
                  <TableHead>Preference</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow
                    key={user.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/members/${user.id}`)}
                  >
                    <TableCell className="font-medium">{user.display_name}</TableCell>
                    <TableCell className="text-muted-foreground">{user.email ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{user.timezone}</TableCell>
                    <TableCell>
                      {user.preferred_practice_time_summary ? (
                        <Badge variant="secondary" className="max-w-64 truncate">
                          {user.preferred_practice_time_summary}
                        </Badge>
                      ) : user.preferred_practice_time ? (
                        <Badge variant="outline">{user.preferred_practice_time.replace("_", " ")}</Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">Not set</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <ChevronRight className="size-4 text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
