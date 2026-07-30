import { useState, type FormEvent } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PreferenceEditor, type PreferenceValue } from "./PreferenceEditor";
import { useCreateUser } from "@/hooks/use-users";
import { guessLocalTimezone, IANA_TIMEZONES } from "@/lib/timezones";

const EMPTY_PREFERENCE: PreferenceValue = { mode: "preset", preset: undefined, raw: "" };

export function CreateMemberDialog() {
  const [open, setOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [timezone, setTimezone] = useState(guessLocalTimezone());
  const [preference, setPreference] = useState<PreferenceValue>(EMPTY_PREFERENCE);
  const createUser = useCreateUser();

  function reset() {
    setDisplayName("");
    setEmail("");
    setTimezone(guessLocalTimezone());
    setPreference(EMPTY_PREFERENCE);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createUser.mutate(
      {
        display_name: displayName.trim(),
        timezone,
        email: email.trim() || undefined,
        preferred_practice_time: preference.mode === "preset" ? preference.preset : undefined,
        preferred_practice_time_raw: preference.mode === "freeform" ? preference.raw.trim() || undefined : undefined,
      },
      {
        onSuccess: () => {
          setOpen(false);
          reset();
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus /> Add member
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a team member</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="member-name">Display name</Label>
            <Input
              id="member-name"
              required
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="member-email">Email</Label>
            <Input
              id="member-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="member-timezone">Timezone</Label>
            <Select value={timezone} onValueChange={setTimezone}>
              <SelectTrigger id="member-timezone" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {IANA_TIMEZONES.map((tz) => (
                  <SelectItem key={tz} value={tz}>
                    {tz}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Practice time preference (optional)</Label>
            <PreferenceEditor value={preference} onChange={setPreference} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={createUser.isPending || !displayName.trim()}>
              {createUser.isPending ? "Adding..." : "Add member"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
