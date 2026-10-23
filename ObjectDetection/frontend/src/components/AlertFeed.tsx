import { api } from "../api/client";
import type { EventItem } from "../api/types";
import { SeverityBadge } from "./SeverityBadge";

export function AlertFeed({ events, mock }: { events: EventItem[]; mock: boolean }) {
  async function ack(id: string) {
    if (mock) return;
    await api(`/api/events/${id}/ack`, { method: "POST" });
  }
  if (events.length === 0) return <p className="text-sm text-[var(--muted)]">No alerts.</p>;
  return (
    <ul className="space-y-2">
      {events.map((event) => (
        <li key={event.id} className="rounded-xl border border-white/10 p-3">
          <div className="flex items-center justify-between gap-2">
            <SeverityBadge severity={event.severity} />
            <span className="mono text-xs text-[var(--muted)]">{event.ts?.slice(11, 19)}</span>
          </div>
          <p className="mt-2 text-sm">{event.message}</p>
          {event.status === "open" ? (
            <button type="button" className="mt-2 text-xs text-safety" onClick={() => void ack(event.id)}>
              Acknowledge
            </button>
          ) : (
            <span className="mt-2 block text-xs text-[var(--muted)]">{event.status}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
