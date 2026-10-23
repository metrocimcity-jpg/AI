import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { toast } from "sonner";
import { api, getToken } from "../api/client";
import type { Camera, FrameMsg, PersonBox } from "../api/types";
import { CameraTile } from "../components/CameraTile";
import { PersonTable } from "../components/PersonTable";
import { VideoOverlayCanvas, type OverlayToggles } from "../components/VideoOverlayCanvas";
import { mockCameras, mockFrame } from "../mock/demo";
import { useLive } from "../store/live";

const defaultToggles: OverlayToggles = {
  boxes: true,
  skeleton: true,
  labels: true,
  zones: true,
  motion: false,
  materials: true,
  helmet: true,
  vest: true,
};

export function LivePage() {
  const { mock } = useOutletContext<{ mock: boolean }>();
  const frames = useLive((s) => s.frames);
  const forgetCamera = useLive((s) => s.forgetCamera);
  const client = useQueryClient();
  const [focus, setFocus] = useState<string | null>(null);
  const [toggles, setToggles] = useState(defaultToggles);
  const [selected, setSelected] = useState<PersonBox | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [pendingRemove, setPendingRemove] = useState<string | null>(null);
  const cameras = useQuery({
    queryKey: ["cameras", mock],
    queryFn: () => (mock ? Promise.resolve(mockCameras) : api<Camera[]>("/api/cameras")),
  });
  const list = cameras.data || [];
  const active = focus || list[0]?.id || null;
  const frame: FrameMsg | null = useMemo(() => {
    if (!active) return null;
    if (frames[active]) return frames[active];
    return mock ? mockFrame(active) : null;
  }, [active, frames, mock]);
  const token = getToken();
  if (cameras.isError) return <p className="text-red-500">Could not load cameras.</p>;

  function flip(key: keyof OverlayToggles) {
    setToggles((current) => ({ ...current, [key]: !current[key] }));
  }

  function askRemove(camera: Camera) {
    if (mock) {
      toast("Sign in to remove a camera.");
      return;
    }
    setPendingRemove(camera.id);
  }

  async function removeCamera(camera: Camera) {
    setRemovingId(camera.id);
    try {
      await api(`/api/cameras/${camera.id}`, { method: "DELETE" });
      forgetCamera(camera.id);
      client.setQueryData<Camera[]>(["cameras", mock], (current) =>
        (current || []).filter((item) => item.id !== camera.id),
      );
      if (focus === camera.id) {
        setFocus(null);
        setSelected(null);
      }
      toast(`${camera.name} removed`);
      void client.invalidateQueries({ queryKey: ["cameras"] });
    } catch (error) {
      toast(error instanceof Error ? error.message : "Could not remove the camera");
    } finally {
      setRemovingId(null);
      setPendingRemove(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {list.map((camera) => (
          <CameraTile
            key={camera.id}
            camera={camera}
            frame={frames[camera.id]}
            mock={mock}
            removing={removingId === camera.id}
            pendingRemove={pendingRemove === camera.id}
            onOpen={() => setFocus(camera.id)}
            onAskRemove={() => askRemove(camera)}
            onRemove={() => void removeCamera(camera)}
            onCancelRemove={() => setPendingRemove(null)}
          />
        ))}
      </div>
      {cameras.isPending ? (
        <p className="text-sm text-[var(--muted)]">Loading cameras…</p>
      ) : list.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">Add a camera to start a live view.</p>
      ) : null}
      {active ? (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
          <div className="relative aspect-video overflow-hidden rounded-2xl bg-slate-950">
            {mock ? (
              <div className="absolute inset-0 bg-gradient-to-br from-slate-800 to-slate-950" />
            ) : (
              <img
                alt="Live camera"
                className="h-full w-full object-contain"
                src={`/api/cameras/${active}/stream.mjpg${token ? `?token=${encodeURIComponent(token)}` : ""}`}
              />
            )}
            {frame ? <VideoOverlayCanvas frame={frame} zones={[]} toggles={toggles} /> : null}
          </div>
          <div className="card p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-sm font-medium">{list.find((camera) => camera.id === active)?.name}</p>
              {pendingRemove === active ? (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-[var(--muted)]">Remove this camera?</span>
                  <button
                    type="button"
                    className="rounded-full bg-red-500 px-2 py-1 text-white disabled:opacity-40"
                    disabled={removingId === active}
                    onClick={() => {
                      const camera = list.find((item) => item.id === active);
                      if (camera) void removeCamera(camera);
                    }}
                  >
                    {removingId === active ? "Removing…" : "Confirm"}
                  </button>
                  <button type="button" className="rounded-full px-2 py-1 ring-1 ring-white/15" onClick={() => setPendingRemove(null)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="rounded-full px-2 py-1 text-xs text-red-400 ring-1 ring-red-400/40 disabled:opacity-40"
                  disabled={removingId === active}
                  onClick={() => {
                    const camera = list.find((item) => item.id === active);
                    if (camera) askRemove(camera);
                  }}
                >
                  Remove camera
                </button>
              )}
            </div>
            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              {(Object.keys(toggles) as (keyof OverlayToggles)[]).map((key) => (
                <button key={key} type="button" className={`rounded-full px-2 py-1 ring-1 ring-white/15 ${toggles[key] ? "text-safety" : ""}`} onClick={() => flip(key)}>
                  {key}
                </button>
              ))}
            </div>
            {frame ? <PersonTable people={frame.persons} onSelect={setSelected} /> : (
              <p className="text-sm text-[var(--muted)]">Waiting for detections.</p>
            )}
            {selected ? (
              <p className="mt-3 text-sm text-[var(--muted)]">
                Track #{selected.track_id} · {selected.posture}
                {selected.worker ? ` · ${selected.worker.name}` : ""}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
