import type { EventItem } from "../api/types";
import { SeverityBadge } from "./SeverityBadge";

export function EventDrawer({ event, onClose }: { event: EventItem | null; onClose: () => void }) {
  if (!event) return null;
  return (
    <aside className="card fixed bottom-4 right-4 z-20 w-80 p-4" role="dialog" aria-label="Event detail">
      <div className="flex items-center justify-between">
        <SeverityBadge severity={event.severity} />
        <button type="button" onClick={onClose} aria-label="Close event">
          Close
        </button>
      </div>
      <h3 className="mt-3 font-semibold">{event.message}</h3>
      <p className="mono mt-1 text-xs text-[var(--muted)]">{event.id}</p>
      {event.snapshot_url ? <img src={event.snapshot_url} alt="Event snapshot" className="mt-3 w-full rounded-lg" /> : null}
      <pre className="mono mt-3 max-h-40 overflow-auto text-xs text-[var(--muted)]">{JSON.stringify(event.meta, null, 2)}</pre>
    </aside>
  );
}
