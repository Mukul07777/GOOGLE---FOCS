import { CircleHelp, Hand, Lightbulb, Rewind, Star, ThumbsUp, type LucideIcon } from "lucide-react";

/** Room reactions: a small fixed set, sent by id and drawn as icons (the same on every device). */
export interface Reaction { id: string; label: string; icon: LucideIcon; color: string }

export const REACTIONS: Reaction[] = [
  { id: "got", label: "Got it", icon: ThumbsUp, color: "var(--ok)" },
  { id: "idea", label: "That clicked", icon: Lightbulb, color: "var(--warn)" },
  { id: "great", label: "Great point", icon: Star, color: "var(--accent)" },
  { id: "slow", label: "Slow down", icon: Rewind, color: "var(--accent-2)" },
  { id: "lost", label: "I'm lost", icon: CircleHelp, color: "var(--bad)" },
  { id: "hand", label: "Raise hand", icon: Hand, color: "var(--warn)" },
];

const BY_ID = new Map(REACTIONS.map((r) => [r.id, r]));
// reactions from people still on an older version of the page arrive as emoji
const LEGACY: Record<string, string> = { "🔥": "great", "👏": "great", "💡": "idea", "🤯": "lost", "😴": "slow", "🙋": "hand" };

export const reactionOf = (id: string): Reaction | undefined => BY_ID.get(id) ?? BY_ID.get(LEGACY[id] ?? "");

/** The badge that floats up over the lecture when someone reacts. */
export function ReactionBadge({ reaction, name }: { reaction: Reaction; name?: string }) {
  const Icon = reaction.icon;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-white/15 bg-black/70 py-1 pl-1 pr-2.5 text-xs font-medium text-white shadow-lg backdrop-blur">
      <span className="grid h-6 w-6 place-items-center rounded-full" style={{ background: reaction.color }}>
        <Icon className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
      </span>
      {name ? `${name.split(" ")[0]} · ${reaction.label}` : reaction.label}
    </span>
  );
}
