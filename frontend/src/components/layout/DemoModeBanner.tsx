import { Info } from "lucide-react";

import { useHealth } from "@/hooks/use-health";

export function DemoModeBanner() {
  const { data } = useHealth();
  if (!data?.demo_mode) return null;

  return (
    <div className="flex items-center gap-2 border-b border-black/5 bg-amber-50 px-4 py-2 text-xs text-amber-900">
      <Info className="size-3.5 shrink-0" />
      <span>
        Public shared demo &mdash; anyone can view or edit this data, and it resets automatically every few
        hours.
      </span>
    </div>
  );
}
