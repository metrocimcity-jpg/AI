const mark: Record<string, string> = { ok: "✓", missing: "!", unknown: "?" };
const tone: Record<string, string> = {
  ok: "text-emerald-500",
  missing: "text-red-500",
  unknown: "text-amber-500",
  absent: "text-amber-500",
};

export function PpeIcons({ ppe }: { ppe: Record<string, string> }) {
  const items = ["helmet", "vest", "gloves", "boots"] as const;
  return (
    <div className="flex gap-2 text-xs" aria-label="PPE status">
      {items.map((item) => {
        const value = ppe[item] || "unknown";
        return (
          <span key={item} className={tone[value] || tone.unknown} title={`${item} ${value}`}>
            {item.slice(0, 1).toUpperCase()}
            {mark[value] || "?"}
          </span>
        );
      })}
    </div>
  );
}
