export function MaterialCard({ name, count }: { name: string; count: number }) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wide text-[var(--muted)]">{name.replaceAll("_", " ")}</div>
      <div className="mono mt-2 text-2xl">{count}</div>
    </div>
  );
}
