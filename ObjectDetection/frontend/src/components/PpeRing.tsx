export function PpeRing({ pct }: { pct: number | null }) {
  const value = pct ?? 0;
  const radius = 36;
  const circ = 2 * Math.PI * radius;
  const dash = (value / 100) * circ;
  return (
    <div className="card flex items-center gap-4 p-4">
      <svg width="96" height="96" viewBox="0 0 96 96" aria-label="PPE compliance">
        <circle cx="48" cy="48" r={radius} stroke="rgba(255,255,255,0.08)" strokeWidth="8" fill="none" />
        <circle
          cx="48"
          cy="48"
          r={radius}
          stroke="#f97316"
          strokeWidth="8"
          fill="none"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          transform="rotate(-90 48 48)"
        />
        <text x="48" y="52" textAnchor="middle" fill="currentColor" fontSize="16" fontFamily="JetBrains Mono">
          {pct === null ? "—" : `${Math.round(pct)}%`}
        </text>
      </svg>
      <div>
        <div className="text-sm text-[var(--muted)]">PPE compliance</div>
        <div className="text-lg font-semibold">Helmet and vest</div>
      </div>
    </div>
  );
}
