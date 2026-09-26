import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { UserRead } from "@/api/types";

interface MembersPanelProps {
  users: UserRead[];
  visibleMemberIds: Set<string>;
  onToggleVisible: (userId: string, visible: boolean) => void;
  memberColorMap: Map<string, string>;
  showAvailability: boolean;
  onToggleShowAvailability: (show: boolean) => void;
}

export function MembersPanel({
  users,
  visibleMemberIds,
  onToggleVisible,
  memberColorMap,
  showAvailability,
  onToggleShowAvailability,
}: MembersPanelProps) {
  return (
    <Card className="p-5">
      <div className="text-base font-bold mb-1">Members</div>
      <p className="text-xs text-muted-foreground mb-3">
        Toggle whose calendar shows. Shaded blocks are busy time; faint bands are the free time each member declared,
        which is the only time the planner will book them.
      </p>
      <div className="flex items-center gap-2.5 mb-3">
        <Checkbox id="show-availability" checked={showAvailability} onCheckedChange={(checked) => onToggleShowAvailability(Boolean(checked))} />
        <Label htmlFor="show-availability" className="text-sm font-normal cursor-pointer">
          Show declared free time
        </Label>
      </div>

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
