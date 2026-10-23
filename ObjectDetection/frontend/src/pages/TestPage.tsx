import { useEffect, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../api/client";

type Clip = {
  id: string;
  title: string;
  detail: string;
  file: string;
  ready: boolean;
  url?: string;
  seconds?: number | null;
};

const FALLBACK: Clip[] = [
  {
    id: "zone",
    title: "Workers in a zone",
    detail: "Intel IoT worker-zone clip, repeated to five minutes.",
    file: "site-test.mp4",
    ready: true,
    url: "/sample/worker-zone-detection.mp4",
    seconds: 300,
  },
  {
    id: "ppe",
    title: "Helmet and vest check",
    detail: "Published photos labeled no-helmet and no-vest, held so the camera can inspect them.",
    file: "ppe-violations.mp4",
    ready: true,
    url: "/sample/ppe-violations.mp4",
  },
  {
    id: "materials",
    title: "Material counting",
    detail: "Brick, concrete, steel, and timber on a conveyor.",
    file: "materials-full.mp4",
    ready: true,
    url: "/sample/materials-full.mp4",
  },
  {
    id: "cement",
    title: "Cement bags",
    detail: "Workers tip cement sacks into the mixer and wheelbarrow the concrete up the building.",
    file: "cement-bags.mp4",
    ready: false,
  },
  {
    id: "gypsum",
    title: "Gypsum board",
    detail: "Drywall work inside a building.",
    file: "gypsum-board.mp4",
    ready: false,
  },
  {
    id: "steel",
    title: "Steel beams",
    detail: "Cranes set the Empire State Building steel frame.",
    file: "steel-beams.mp4",
    ready: false,
  },
];

export function TestPage() {
  const { mock, leaveSample } = useOutletContext<{ mock: boolean; leaveSample: () => void }>();
  const navigate = useNavigate();
  const [clips, setClips] = useState<Clip[]>(FALLBACK);
  const [selected, setSelected] = useState("ppe");
  const [busy, setBusy] = useState(false);
  const [broken, setBroken] = useState<string | null>(null);
  const current = clips.find((clip) => clip.id === selected) ?? clips[0];

  useEffect(() => {
    if (mock) return;
    let stop = false;
    const load = () => {
      void api<{ items: Clip[] }>("/api/samples")
        .then((body) => {
          if (!stop && body.items.length) setClips(body.items);
        })
        .catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [mock]);

  async function runClip() {
    if (!current?.ready || broken === current.id) return;
    if (mock) {
      toast("Sign in to run this clip as a camera.");
      leaveSample();
      return;
    }
    setBusy(true);
    try {
      await api(`/api/samples/${current.id}/camera`, { method: "POST" });
      toast(`${current.title} is running`);
      navigate("/live");
    } catch (error) {
      toast(error instanceof Error ? error.message : "Could not start the clip");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <h2 className="font-semibold">Test</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Pick a clip, then run it as a camera. Cement bags, gypsum board, and steel beams are separate clips.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {clips.map((clip) => (
          <button
            key={clip.id}
            type="button"
            className={`rounded-full px-3 py-1 text-sm ring-1 ring-white/15 ${selected === clip.id ? "bg-safety/15 text-safety" : ""}`}
            onClick={() => setSelected(clip.id)}
          >
            {clip.title}
          </button>
        ))}
      </div>
      {current ? (
        <div className="space-y-3">
          <p className="text-sm text-[var(--muted)]">
            {current.detail}
            {current.seconds ? ` ${current.seconds}s.` : ""}
          </p>
          {!current.ready ? (
            <p className="text-sm text-amber-500">{current.file} is not available yet.</p>
          ) : broken === current.id ? (
            <p className="text-sm text-amber-500">The file is on disk. This browser cannot preview that encoding. Run it on the dashboard to watch the camera stream.</p>
          ) : (
            <video
              key={current.url}
              className="w-full max-w-4xl rounded-2xl bg-black"
              controls
              loop
              src={current.url}
              onError={() => setBroken(current.id)}
            />
          )}
          <button
            type="button"
            className="rounded-xl bg-safety px-3 py-2 text-sm text-black disabled:opacity-50"
            disabled={busy || !current.ready}
            onClick={() => void runClip()}
          >
            {busy ? "Starting…" : "Run on the dashboard"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
