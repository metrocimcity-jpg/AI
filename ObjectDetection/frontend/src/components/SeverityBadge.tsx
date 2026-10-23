const tones: Record<string, string> = {
  critical: "bg-red-500/15 text-red-500",
  warning: "bg-amber-500/15 text-amber-500",
  info: "bg-sky-500/15 text-sky-500",
  ok: "bg-emerald-500/15 text-emerald-500",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tones[severity] || tones.info}`}>
      {severity}
    </span>
  );
}
