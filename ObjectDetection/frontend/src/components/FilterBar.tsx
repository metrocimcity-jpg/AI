export function FilterBar({
  severity,
  status,
  onSeverity,
  onStatus,
}: {
  severity: string;
  status: string;
  onSeverity: (value: string) => void;
  onStatus: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <label className="text-sm">
        Severity
        <select className="ml-2 rounded-lg bg-transparent px-2 py-1 ring-1 ring-white/15" value={severity} onChange={(e) => onSeverity(e.target.value)} aria-label="Severity">
          <option value="">Any</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
      </label>
      <label className="text-sm">
        Status
        <select className="ml-2 rounded-lg bg-transparent px-2 py-1 ring-1 ring-white/15" value={status} onChange={(e) => onStatus(e.target.value)} aria-label="Status">
          <option value="">Any</option>
          <option value="open">Open</option>
          <option value="ack">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
      </label>
    </div>
  );
}
