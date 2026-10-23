export function EmptyState({ title, body, action }: { title: string; body: string; action?: string }) {
  return (
    <div className="card flex flex-col items-start gap-2 p-6">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="max-w-md text-sm text-[var(--muted)]">{body}</p>
      {action ? <p className="text-sm text-safety">{action}</p> : null}
    </div>
  );
}
