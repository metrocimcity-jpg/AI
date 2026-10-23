import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { useOutletContext } from "react-router-dom";
import { api } from "../api/client";
import type { Overview } from "../api/types";
import { AlertFeed } from "../components/AlertFeed";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { KpiCard } from "../components/KpiCard";
import { MaterialCard } from "../components/MaterialCard";
import { PostureDonut } from "../components/PostureDonut";
import { PpeRing } from "../components/PpeRing";
import { alertBars, mockOverview, ppeTrend } from "../mock/demo";
import { useLive } from "../store/live";

export function DashboardPage() {
  const { mock } = useOutletContext<{ mock: boolean }>();
  const liveEvents = useLive((s) => s.events);
  const query = useQuery({
    queryKey: ["overview", mock],
    queryFn: () => (mock ? Promise.resolve(mockOverview) : api<Overview>("/api/stats/overview")),
  });
  if (query.isLoading) return <p>Loading dashboard…</p>;
  if (query.isError) return <p className="text-red-500">Could not load the dashboard.</p>;
  const data = query.data;
  if (!data) return null;
  const events = liveEvents.length ? liveEvents : data.recent_events;
  const bars = mock
    ? alertBars
    : Object.entries(
        events.reduce<Record<string, number>>((acc, event) => {
          acc[event.event_type] = (acc[event.event_type] || 0) + 1;
          return acc;
        }, {}),
      ).map(([type, count]) => ({ type, count }));
  const trend = mock ? ppeTrend : [];
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <KpiCard label="People on site" value={String(data.people_now)} />
        <KpiCard label="Active alerts" value={String(data.active_alerts)} />
        <KpiCard label="Cameras online" value={String(data.cameras_online)} />
        <KpiCard label="FPS / latency" value={`${data.fps_avg}`} hint={`${data.latency_ms_avg} ms`} />
      </div>
      <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
        <ErrorBoundary label="Compliance">
          <PpeRing pct={data.ppe_compliance_pct} />
          <div className="card mt-3 h-56 p-4">
            <div className="mb-2 text-sm text-[var(--muted)]">PPE trend</div>
            {trend.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">Hourly PPE samples appear after cameras have been running.</p>
            ) : (
              <ResponsiveContainer width="100%" height="85%">
                <AreaChart data={trend}>
                  <XAxis dataKey="hour" stroke="currentColor" />
                  <Tooltip />
                  <Area dataKey="pct" stroke="#f97316" fill="rgba(249,115,22,0.25)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </ErrorBoundary>
        <div className="card max-h-[420px] overflow-auto p-4">
          <div className="mb-3 text-sm text-[var(--muted)]">Live alerts</div>
          <AlertFeed events={events} mock={mock} />
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <ErrorBoundary label="Posture">
          <PostureDonut counts={data.posture_counts} />
        </ErrorBoundary>
        <div className="card h-64 p-4">
          <div className="mb-2 text-sm text-[var(--muted)]">Alerts by type</div>
          <ResponsiveContainer width="100%" height="85%">
            <BarChart data={bars.length ? bars : [{ type: "none", count: 0 }]}>
              <XAxis dataKey="type" stroke="currentColor" />
              <Tooltip />
              <Bar dataKey="count" fill="#f97316" radius={6} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(data.material_counts).map(([name, count]) => (
          <MaterialCard key={name} name={name} count={count} />
        ))}
      </div>
    </div>
  );
}
