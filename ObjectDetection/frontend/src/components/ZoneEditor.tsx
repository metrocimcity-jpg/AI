import { useState, type MouseEvent } from "react";
import type { Zone } from "../api/types";

export function ZoneEditor({
  zones,
  onChange,
}: {
  zones: Zone[];
  onChange: (polygon: number[][]) => void;
}) {
  const [points, setPoints] = useState<number[][]>([]);

  function add(event: MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Number(((event.clientX - rect.left) / rect.width).toFixed(3));
    const y = Number(((event.clientY - rect.top) / rect.height).toFixed(3));
    const next = [...points, [x, y]];
    setPoints(next);
    onChange(next);
  }

  return (
    <div>
      <svg viewBox="0 0 100 56" className="aspect-video w-full rounded-xl bg-slate-900" onClick={add} role="img" aria-label="Zone drawing surface">
        {zones.map((zone) => (
          <polygon
            key={zone.id}
            points={zone.polygon.map((p) => `${p[0] * 100},${p[1] * 56}`).join(" ")}
            fill="rgba(249,115,22,0.15)"
            stroke="#f97316"
          />
        ))}
        <polyline points={points.map((p) => `${p[0] * 100},${p[1] * 56}`).join(" ")} fill="none" stroke="#38bdf8" />
        {points.map((p, i) => (
          <circle key={i} cx={p[0] * 100} cy={p[1] * 56} r="1.2" fill="#38bdf8" />
        ))}
      </svg>
      <button type="button" className="mt-2 text-sm text-safety" onClick={() => { setPoints([]); onChange([]); }}>
        Clear draft
      </button>
    </div>
  );
}
