import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatTimeRange } from "@/lib/datetime";
import type { PlanningRecommendationRead, UserRead } from "@/api/types";

export function RecommendationCard({
  recommendation,
  selected,
  onSelect,
  users,
}: {
  recommendation: PlanningRecommendationRead;
  selected: boolean;
  onSelect: () => void;
  users: UserRead[];
}) {
  const usersById = new Map(users.map((u) => [u.id, u.display_name]));
  const missingNames = recommendation.missing_required_user_ids.map((id) => usersById.get(id) ?? id);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition-colors",
        selected ? "border-primary ring-2 ring-primary/30 bg-primary/5" : "hover:bg-accent/50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{formatTimeRange(recommendation.start_at, recommendation.end_at)}</p>
          <p className="text-xs text-muted-foreground">Rank #{recommendation.rank}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant="outline">score {recommendation.total_score.toFixed(2)}</Badge>
          {recommendation.is_fallback && <Badge variant="warning">fallback</Badge>}
        </div>
      </div>

      <p className="mt-2 text-sm">{recommendation.explanation.summary}</p>

      {recommendation.explanation.reasons.length > 0 && (
        <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
          {recommendation.explanation.reasons.slice(0, 3).map((reason, index) => (
            <li key={`${reason.code}-${index}`}>&bull; {reason.message}</li>
          ))}
        </ul>
      )}

      {missingNames.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          <Badge variant="destructive">missing: {missingNames.join(", ")}</Badge>
        </div>
      )}

      <p className="mt-2 text-xs text-muted-foreground">
        {recommendation.optional_available_count} optional participant(s) available
      </p>
    </button>
  );
}
