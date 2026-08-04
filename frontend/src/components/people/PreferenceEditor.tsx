import { useState } from "react";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { PreferredPracticeTime } from "@/api/types";

export const PREFERRED_PRACTICE_TIME_OPTIONS: { value: PreferredPracticeTime; label: string }[] = [
  { value: "morning", label: "Morning (8:00 - 12:00)" },
  { value: "afternoon", label: "Afternoon (12:00 - 16:00)" },
  { value: "evening", label: "Evening (16:00 - 20:00)" },
  { value: "late_night", label: "Late night (20:00 - 24:00)" },
];

export interface PreferenceValue {
  mode: "preset" | "freeform";
  preset: PreferredPracticeTime | undefined;
  raw: string;
}

export function PreferenceEditor({
  value,
  onChange,
}: {
  value: PreferenceValue;
  onChange: (value: PreferenceValue) => void;
}) {
  const [tab, setTab] = useState<"preset" | "freeform">(value.mode);

  return (
    <Tabs
      value={tab}
      onValueChange={(next) => {
        const mode = next as "preset" | "freeform";
        setTab(mode);
        onChange({ ...value, mode });
      }}
    >
      <TabsList>
        <TabsTrigger value="preset">Preset</TabsTrigger>
        <TabsTrigger value="freeform">Freeform</TabsTrigger>
      </TabsList>
      <TabsContent value="preset" className="space-y-2 pt-2">
        <Label htmlFor="preferred-practice-time">Preferred practice time</Label>
        <Select
          value={value.preset}
          onValueChange={(preset) => onChange({ ...value, preset: preset as PreferredPracticeTime })}
        >
          <SelectTrigger id="preferred-practice-time" className="w-full">
            <SelectValue placeholder="Choose a canned option" />
          </SelectTrigger>
          <SelectContent>
            {PREFERRED_PRACTICE_TIME_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TabsContent>
      <TabsContent value="freeform" className="space-y-2 pt-2">
        <Label htmlFor="preferred-practice-time-raw">Describe availability preferences</Label>
        <Textarea
          id="preferred-practice-time-raw"
          placeholder='e.g. "weekends only, never before 9am, avoid Fridays"'
          value={value.raw}
          onChange={(event) => onChange({ ...value, raw: event.target.value })}
          rows={3}
        />
        <p className="text-xs text-muted-foreground">
          This text is sent to an AI parser and cached as structured days/times.
        </p>
      </TabsContent>
    </Tabs>
  );
}

export function PreferenceSummary({
  summary,
  parsed,
}: {
  summary: string | null;
  parsed: {
    preferred_days: string[];
    avoid_days: string[];
    earliest_time: string | null;
    latest_time: string | null;
    notes: string | null;
    summary: string | null;
  } | null;
}) {
  if (!summary && !parsed) {
    return <p className="text-sm text-muted-foreground">No parsed preference yet.</p>;
  }
  return (
    <div className="rounded-md border bg-muted/40 p-3 text-sm space-y-1">
      {summary && <p className="font-medium">{summary}</p>}
      {parsed && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {parsed.preferred_days.length > 0 && <span>Prefers: {parsed.preferred_days.join(", ")}</span>}
          {parsed.avoid_days.length > 0 && <span>Avoids: {parsed.avoid_days.join(", ")}</span>}
          {parsed.earliest_time && <span>From {parsed.earliest_time}</span>}
          {parsed.latest_time && <span>Until {parsed.latest_time}</span>}
        </div>
      )}
    </div>
  );
}
