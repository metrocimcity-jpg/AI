import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../api/client";
import type { Camera, ModelRow, WorkerRow, Zone } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MaterialCard } from "../components/MaterialCard";
import { ZoneEditor } from "../components/ZoneEditor";
import { mockCameras, mockModels, mockOverview, mockWorkers, mockZones } from "../mock/demo";

function useMock() {
  return useOutletContext<{ mock: boolean }>().mock;
}

export function AnalyticsPage() {
  return (
    <EmptyState
      title="Analytics"
      body="PPE, posture, and incident trends are collected locally from the sample tables. Open the dashboard for the live snapshot, or export a CSV from Events."
      action="All charts stay on this machine."
    />
  );
}

export function MaterialsPage() {
  const mock = useMock();
  const query = useQuery({
    queryKey: ["materials", mock],
    queryFn: async () => {
      if (mock) return mockOverview.material_counts;
      const body = await api<{ material_counts: Record<string, number> }>("/api/stats/overview");
      return body.material_counts;
    },
  });
  const counts = query.data || {};
  if (query.isLoading) return <p>Loading materials…</p>;
  if (Object.keys(counts).length === 0) {
    return <EmptyState title="No materials yet" body="Counts appear after the materials model runs on a camera." action="Add an ONNX file named in models/manifest.json." />;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Object.entries(counts).map(([name, count]) => (
        <MaterialCard key={name} name={name} count={count} />
      ))}
    </div>
  );
}

export function WorkersPage() {
  const mock = useMock();
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["workers", mock],
    queryFn: () => (mock ? Promise.resolve(mockWorkers) : api<WorkerRow[]>("/api/workers")),
  });
  const create = useMutation({
    mutationFn: () => api("/api/workers", { method: "POST", body: JSON.stringify({ name, consent }) }),
    onSuccess: () => {
      toast("Worker saved");
      void client.invalidateQueries({ queryKey: ["workers"] });
      setName("");
    },
  });
  return (
    <div className="space-y-4">
      <form
        className="card flex flex-wrap items-end gap-3 p-4"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (!mock) create.mutate();
        }}
      >
        <label className="text-sm">
          Name
          <input className="mt-1 block rounded-lg bg-transparent px-3 py-2 ring-1 ring-white/15" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          Consent to store face embeddings locally
        </label>
        <button className="rounded-xl bg-safety px-3 py-2 text-sm text-black" type="submit">Add worker</button>
      </form>
      <p className="text-sm text-[var(--muted)]">Face enrollment stays off until face recognition is enabled. The API never returns embeddings.</p>
      <ul className="space-y-2">
        {(query.data || []).map((worker) => (
          <li key={worker.id} className="card flex items-center justify-between p-4">
            <div>
              <div className="font-medium">{worker.name}</div>
              <div className="text-xs text-[var(--muted)]">{worker.employee_id || worker.role || "worker"} · faces {worker.face_count}</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ZonesPage() {
  const mock = useMock();
  const [draft, setDraft] = useState<number[][]>([]);
  const [cameraId, setCameraId] = useState("");
  const cameras = useQuery({
    queryKey: ["cameras", mock],
    queryFn: () => (mock ? Promise.resolve(mockCameras) : api<Camera[]>("/api/cameras")),
  });
  const chosen = cameraId || cameras.data?.[0]?.id || "";
  const zones = useQuery({
    queryKey: ["zones", chosen, mock],
    enabled: Boolean(chosen),
    queryFn: () => (mock ? Promise.resolve(mockZones) : api<Zone[]>(`/api/cameras/${chosen}/zones`)),
  });
  async function save(event: FormEvent) {
    event.preventDefault();
    if (mock || draft.length < 3 || !chosen) return;
    const form = new FormData(event.currentTarget as HTMLFormElement);
    await api(`/api/cameras/${chosen}/zones`, {
      method: "POST",
      body: JSON.stringify({
        name: String(form.get("name") || "Zone"),
        type: String(form.get("type") || "restricted"),
        polygon: draft,
      }),
    });
    toast("Zone saved");
    setDraft([]);
  }
  return (
    <form className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]" onSubmit={(event) => void save(event)}>
      <div className="card p-4">
        <ZoneEditor zones={(zones.data || []).filter((z) => z.camera_id === chosen || mock)} onChange={setDraft} />
      </div>
      <div className="card space-y-3 p-4">
        <label className="block text-sm">
          Camera
          <select className="mt-1 block w-full rounded-lg bg-transparent px-2 py-2 ring-1 ring-white/15" value={chosen} onChange={(e) => setCameraId(e.target.value)} aria-label="Camera">
            {(cameras.data || []).map((camera) => (
              <option key={camera.id} value={camera.id}>{camera.name}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Name
          <input name="name" className="mt-1 block w-full rounded-lg bg-transparent px-3 py-2 ring-1 ring-white/15" defaultValue="Restricted" />
        </label>
        <label className="block text-sm">
          Type
          <select name="type" className="mt-1 block w-full rounded-lg bg-transparent px-2 py-2 ring-1 ring-white/15" aria-label="Zone type">
            <option value="restricted">restricted</option>
            <option value="walkway">walkway</option>
            <option value="ladder">ladder</option>
            <option value="office">office</option>
          </select>
        </label>
        <p className="text-xs text-[var(--muted)]">{draft.length} points · coordinates are 0–1</p>
        <button className="rounded-xl bg-safety px-3 py-2 text-sm text-black" type="submit">Save zone</button>
      </div>
    </form>
  );
}

export function CamerasPage() {
  const mock = useMock();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["cameras", mock],
    queryFn: () => (mock ? Promise.resolve(mockCameras) : api<Camera[]>("/api/cameras")),
  });
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mock) return;
    const form = new FormData(event.currentTarget);
    await api("/api/cameras", {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"),
        source: form.get("source"),
        enabled: true,
      }),
    });
    toast("Camera added");
    void client.invalidateQueries({ queryKey: ["cameras"] });
    event.currentTarget.reset();
  }
  return (
    <div className="space-y-4">
      <form className="card flex flex-wrap gap-3 p-4" onSubmit={(event) => void add(event)}>
        <input name="name" required placeholder="Name" aria-label="Camera name" className="rounded-lg bg-transparent px-3 py-2 ring-1 ring-white/15" />
        <input name="source" required placeholder="rtsp://… or file path or 0" aria-label="Camera source" className="min-w-64 flex-1 rounded-lg bg-transparent px-3 py-2 ring-1 ring-white/15" />
        <button className="rounded-xl bg-safety px-3 py-2 text-sm text-black" type="submit">Add</button>
      </form>
      <ul className="space-y-2">
        {(query.data || []).map((camera) => (
          <li key={camera.id} className="card flex items-center justify-between p-4">
            <div>
              <div className="font-medium">{camera.name}</div>
              <div className="mono text-xs text-[var(--muted)]">{camera.source}</div>
            </div>
            <div className="text-right text-sm">
              <div>{camera.status}</div>
              <div className="mono text-xs text-[var(--muted)]">{camera.fps} fps</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SettingsPage() {
  const mock = useMock();
  const models = useQuery({
    queryKey: ["models", mock],
    queryFn: async () => {
      if (mock) {
        return mockModels as ModelRow[];
      }
      const body = await api<{ models: ModelRow[] }>("/api/models");
      return body.models;
    },
  });
  return (
    <div className="space-y-4">
      <div className="card p-4">
        <h2 className="font-semibold">Offline status</h2>
        <p className="mt-1 text-sm text-emerald-500">No internet required. Models, fonts, and video stay on this machine.</p>
      </div>
      <div className="card overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[var(--muted)]">
            <tr>
              <th className="p-3">Model</th>
              <th>Task</th>
              <th>License</th>
              <th>File</th>
            </tr>
          </thead>
          <tbody>
            {(models.data || []).map((model) => (
              <tr key={model.name} className="border-t border-white/10">
                <td className="p-3">{model.name}</td>
                <td>{model.task}</td>
                <td>{model.license}</td>
                <td className={model.exists ? "text-emerald-500" : "text-amber-500"}>{model.exists ? "present" : "missing"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function WallPage() {
  const { mock } = useOutletContext<{ mock: boolean }>();
  const cameras = useQuery({
    queryKey: ["cameras", mock],
    queryFn: () => (mock ? Promise.resolve(mockCameras) : api<Camera[]>("/api/cameras")),
  });
  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {(cameras.data || []).map((camera) => (
        <div key={camera.id} className="card p-3">
          <div className="text-sm">{camera.name}</div>
          <div className="mono text-xs text-[var(--muted)]">{camera.status} · {camera.fps} fps</div>
        </div>
      ))}
    </div>
  );
}
