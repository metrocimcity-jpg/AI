const tones: Record<string, string> = {
  standing: "bg-emerald-500/15 text-emerald-500",
  walking: "bg-sky-500/15 text-sky-500",
  sitting: "bg-amber-500/15 text-amber-500",
  crouching: "bg-amber-500/15 text-amber-500",
  bending: "bg-orange-500/15 text-orange-400",
  lying: "bg-red-500/15 text-red-500",
  crawling: "bg-red-500/15 text-red-500",
  climbing: "bg-sky-500/15 text-sky-500",
  unknown: "bg-slate-500/15 text-slate-300",
};

export function PostureBadge({ posture, since }: { posture: string; since?: number }) {
  const seconds = since ? Math.max(0, Math.round(Date.now() / 1000 - since)) : null;
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs ${tones[posture] || tones.unknown}`}>
      {posture}
      {seconds !== null ? ` · ${seconds}s` : ""}
    </span>
  );
}
