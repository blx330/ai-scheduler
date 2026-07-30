import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PreferenceEditor, PreferenceSummary, type PreferenceValue } from "./PreferenceEditor";
import { useUpdateUser } from "@/hooks/use-users";
import type { UserRead } from "@/api/types";

export function MemberPreferencesCard({ user }: { user: UserRead }) {
  const updateUser = useUpdateUser();
  const [preference, setPreference] = useState<PreferenceValue>({
    mode: user.preferred_practice_time_raw ? "freeform" : "preset",
    preset: user.preferred_practice_time ?? undefined,
    raw: user.preferred_practice_time_raw ?? "",
  });

  function handleSave() {
    updateUser.mutate({
      id: user.id,
      body: {
        preferred_practice_time: preference.mode === "preset" ? preference.preset ?? null : null,
        preferred_practice_time_raw: preference.mode === "freeform" ? preference.raw.trim() || null : null,
      },
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Practice-time preference</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <PreferenceEditor value={preference} onChange={setPreference} />
        <Button onClick={handleSave} disabled={updateUser.isPending}>
          {updateUser.isPending ? "Saving..." : "Save preferences"}
        </Button>
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">AI-parsed preview</p>
          <PreferenceSummary
            summary={user.preferred_practice_time_summary}
            parsed={user.preferred_practice_time_parsed}
          />
        </div>
      </CardContent>
    </Card>
  );
}
