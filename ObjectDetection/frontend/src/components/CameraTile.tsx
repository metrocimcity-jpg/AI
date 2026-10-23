import { getToken } from "../api/client";
import type { Camera, FrameMsg } from "../api/types";

export function CameraTile({
  camera,
  frame,
  mock,
  onOpen,
  onAskRemove,
  onRemove,
  onCancelRemove,
  removing,
  pendingRemove,
}: {
  camera: Camera;
  frame?: FrameMsg;
  mock: boolean;
  onOpen: () => void;
  onAskRemove?: () => void;
  onRemove?: () => void;
  onCancelRemove?: () => void;
  removing?: boolean;
  pendingRemove?: boolean;
}) {
  const token = getToken();
  const src = mock
    ? undefined
    : `/api/cameras/${camera.id}/stream.mjpg${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  return (
    <div className="card overflow-hidden text-left">
      <button type="button" onClick={onOpen} className="block w-full text-left" aria-label={`Open ${camera.name}`}>
        <div className="relative aspect-video bg-slate-900">
          {src ? (
            <img src={src} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-400">Sample view</div>
          )}
          <div className="absolute left-2 top-2 rounded bg-black/60 px-2 py-1 text-xs">{camera.name}</div>
          <div className="mono absolute right-2 top-2 rounded bg-black/60 px-2 py-1 text-xs">
            {frame?.metrics.fps ?? camera.fps} fps
          </div>
        </div>
      </button>
      <div className="flex items-center justify-between gap-2 px-3 py-2 text-xs text-[var(--muted)]">
        <span>{camera.status}</span>
        <span>{frame?.persons.length ?? 0} people</span>
        {pendingRemove ? (
          <span className="flex items-center gap-1">
            <button
              type="button"
              className="rounded-full bg-red-500 px-2 py-1 text-white disabled:opacity-40"
              disabled={removing}
              onClick={onRemove}
            >
              {removing ? "Removing…" : "Confirm"}
            </button>
            <button type="button" className="rounded-full px-2 py-1 ring-1 ring-white/15" onClick={onCancelRemove}>
              Cancel
            </button>
          </span>
        ) : onAskRemove ? (
          <button
            type="button"
            className="rounded-full px-2 py-1 text-red-400 ring-1 ring-red-400/40 disabled:opacity-40"
            disabled={removing}
            onClick={onAskRemove}
          >
            Remove
          </button>
        ) : null}
      </div>
    </div>
  );
}
