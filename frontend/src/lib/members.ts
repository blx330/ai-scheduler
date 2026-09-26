/**
 * How many members' busy time the calendar shows before anyone toggles the panel.
 * A whole roster's classes and shifts stacked into one week is a wall of lanes; a
 * handful reads, and the Members panel is one click away for the rest.
 */
export const DEFAULT_VISIBLE_MEMBER_LIMIT = 4;

/** Roster order is creation order, so the first few are the longest-standing members. */
export function initialVisibleMemberIds(memberIds: string[], limit = DEFAULT_VISIBLE_MEMBER_LIMIT): Set<string> {
  return new Set(memberIds.slice(0, Math.max(0, limit)));
}
