import { Badge } from "@/components/ui/badge";
import type { DanceEventStatus } from "@/api/types";

const STATUS_VARIANT: Record<DanceEventStatus, "default" | "secondary" | "outline" | "success" | "warning"> = {
  unscheduled: "outline",
  partially_scheduled: "warning",
  scheduled: "success",
  completed: "secondary",
  archived: "secondary",
};

export function EventStatusBadge({ status }: { status: DanceEventStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{status.replace("_", " ")}</Badge>;
}
