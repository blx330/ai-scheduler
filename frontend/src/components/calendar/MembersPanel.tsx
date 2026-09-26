import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
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
        {users.map((member) => {
          const checkboxId = `member-visible-${member.id}`;
          return (
            <div key={member.id} className="flex items-center gap-2.5">
              <Checkbox
                id={checkboxId}
                checked={visibleMemberIds.has(member.id)}
                onCheckedChange={(checked) => onToggleVisible(member.id, Boolean(checked))}
              />
              <span aria-hidden className="size-2.5 rounded-full shrink-0" style={{ background: memberColorMap.get(member.id) }} />
              <Label htmlFor={checkboxId} className="flex-1 min-w-0 text-sm font-normal truncate cursor-pointer">
                {member.display_name}
              </Label>
            </div>
          );
        })}
        {users.length === 0 && <p className="text-xs text-muted-foreground">No members yet.</p>}
      </div>
    </Card>
  );
}
