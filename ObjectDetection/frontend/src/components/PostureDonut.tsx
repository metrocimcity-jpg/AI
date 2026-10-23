import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const colors = ["#34d399", "#38bdf8", "#fbbf24", "#fb923c", "#f97316", "#f87171", "#a78bfa", "#94a3b8"];

export function PostureDonut({ counts }: { counts: Record<string, number> }) {
  const data = Object.entries(counts).map(([name, value]) => ({ name, value }));
  return (
    <div className="card h-64 p-4">
      <div className="mb-2 text-sm text-[var(--muted)]">Posture now</div>
      {data.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No people in view.</p>
      ) : (
        <ResponsiveContainer width="100%" height="85%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72}>
              {data.map((entry, index) => (
                <Cell key={entry.name} fill={colors[index % colors.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
