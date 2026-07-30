import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { AvailabilityPanel } from "@/components/people/AvailabilityPanel";
import { GoogleCalendarPanel } from "@/components/people/GoogleCalendarPanel";
import { MemberPreferencesCard } from "@/components/people/MemberPreferencesCard";
import { useDeleteUser, useUser } from "@/hooks/use-users";

export function MemberDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const { data: user, isLoading, isError } = useUser(userId);
  const deleteUser = useDeleteUser();
  const navigate = useNavigate();

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading member...</p>;
  if (isError || !user) return <p className="text-sm text-destructive">Member not found.</p>;

  return (
    <div className="space-y-4 max-w-3xl">
      <Button variant="ghost" size="sm" onClick={() => navigate("/members")}>
        <ArrowLeft /> Back to members
      </Button>

      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold">{user.display_name}</h2>
          <p className="text-sm text-muted-foreground">
            {user.email ?? "No email"} &middot; {user.timezone}
          </p>
        </div>
        <Button
          variant="destructive"
          size="sm"
          onClick={() => {
            if (confirm(`Remove ${user.display_name}? This cannot be undone.`)) {
              deleteUser.mutate(user.id, { onSuccess: () => navigate("/members") });
            }
          }}
        >
          <Trash2 /> Remove member
        </Button>
      </div>

      <Separator />

      <MemberPreferencesCard user={user} />
      <AvailabilityPanel user={user} />
      <GoogleCalendarPanel user={user} />
    </div>
  );
}
