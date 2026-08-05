import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import type { UserRead } from "@/api/types";

interface MembersPanelProps {
  users: UserRead[];
  visibleMemberIds: Set<string>;
  onToggleVisible: (userId: string, visible: boolean) => void;
  memberColorMap: Map<string, string>;
}

export function MembersPanel({ users, visibleMemberIds, onToggleVisible, memberColorMap }: MembersPanelProps) {
  return (
    <Card className="p-5">
      <div className="text-base font-bold mb-1">Members</div>
      <p className="text-xs text-muted-foreground mb-3">Toggle whose busy time shows on the calendar.</p>

      <div className="flex flex-col gap-2.5">
        {users.map((member) => (
          <div key={member.id} className="flex items-center gap-2.5">
            <Checkbox
              checked={visibleMemberIds.has(member.id)}
              onCheckedChange={(checked) => onToggleVisible(member.id, Boolean(checked))}
            />
            <span className="size-2.5 rounded-full shrink-0" style={{ background: memberColorMap.get(member.id) }} />
            <span className="flex-1 min-w-0 text-sm truncate">{member.display_name}</span>
          </div>
        ))}
        {users.length === 0 && <p className="text-xs text-muted-foreground">No members yet.</p>}
      </div>
    </Card>
  );
}
