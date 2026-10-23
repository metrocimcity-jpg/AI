import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../api/client";
import type { EventItem } from "../api/types";
import { EventDrawer } from "../components/EventDrawer";
import { FilterBar } from "../components/FilterBar";
import { SeverityBadge } from "../components/SeverityBadge";
import { mockEvents } from "../mock/demo";

export function EventsPage() {
  const { mock } = useOutletContext<{ mock: boolean }>();
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<EventItem | null>(null);
  const query = useQuery({
    queryKey: ["events", mock, severity, status],
    queryFn: async () => {
      if (mock) return mockEvents;
      const params = new URLSearchParams();
      if (severity) params.set("severity", severity);
      if (status) params.set("status", status);
      const body = await api<{ items: EventItem[] }>(`/api/events?${params.toString()}`);
      return body.items;
    },
  });
  const rows = (query.data || []).filter((row) => (severity ? row.severity === severity : true) && (status ? row.status === status : true));

  async function exportCsv() {
    if (mock) {
      toast("Sample mode does not download a file");
      return;
    }
    const blob = await api<Blob>("/api/reports/export", {
      method: "POST",
      body: JSON.stringify({ type: "events", format: "csv" }),
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "events.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <FilterBar severity={severity} status={status} onSeverity={setSeverity} onStatus={setStatus} />
        <button type="button" className="rounded-xl bg-safety px-3 py-2 text-sm text-black" onClick={() => void exportCsv()}>
          Export CSV
        </button>
      </div>
      {query.isLoading ? <p>Loading events…</p> : null}
      {query.isError ? <p className="text-red-500">Could not load events.</p> : null}
      {rows.length === 0 && !query.isLoading ? <p className="text-sm text-[var(--muted)]">No events match these filters.</p> : null}
      <div className="card overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[var(--muted)]">
            <tr>
              <th className="p-3">Time</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-white/10">
                <td className="mono p-3">{row.ts?.replace("T", " ").slice(0, 19)}</td>
                <td>{row.event_type}</td>
                <td><SeverityBadge severity={row.severity} /></td>
                <td>{row.status}</td>
                <td>
                  <button type="button" className="text-left hover:text-safety" onClick={() => setOpen(row)}>
                    {row.message}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <EventDrawer event={open} onClose={() => setOpen(null)} />
    </div>
  );
}
