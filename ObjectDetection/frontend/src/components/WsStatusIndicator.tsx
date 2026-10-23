import { useLive } from "../store/live";

export function WsStatusIndicator() {
  const status = useLive((s) => s.status);
  const color = status === "live" ? "bg-emerald-500" : status === "reconnecting" ? "bg-amber-500" : "bg-slate-500";
  const label = status === "live" ? "Live" : status === "reconnecting" ? "Reconnecting" : "Offline";
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${color} ${status === "live" ? "animate-pulse" : ""}`} />
      {label}
    </span>
  );
}
