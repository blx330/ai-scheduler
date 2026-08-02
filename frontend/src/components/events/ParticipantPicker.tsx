import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ParticipantRole, UserRead } from "@/api/types";
import { userColor } from "@/lib/userColor";

export type ParticipantSelection = ParticipantRole | "none";

export function ParticipantPicker({
  users,
  value,
  onChange,
}: {
  users: UserRead[];
  value: Record<string, ParticipantSelection>;
  onChange: (userId: string, selection: ParticipantSelection) => void;
}) {
  if (users.length === 0) {
    return <p className="text-sm text-muted-foreground">Add members first to assign participants.</p>;
  }

  return (
    <div className="space-y-2 rounded-md border p-3">
      {users.map((user) => (
        <div key={user.id} className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="size-2.5 rounded-full shrink-0" style={{ background: userColor(user.id) }} />
            <Label className="font-normal">{user.display_name}</Label>
          </div>
          <Select
            value={value[user.id] ?? "none"}
            onValueChange={(selection) => onChange(user.id, selection as ParticipantSelection)}
          >
            <SelectTrigger size="sm" className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Not involved</SelectItem>
              <SelectItem value="required">Required</SelectItem>
              <SelectItem value="optional">Optional</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ))}
    </div>
  );
}
