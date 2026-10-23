import { useEffect, useRef } from "react";
import type { FrameMsg, Zone } from "../api/types";

export type OverlayToggles = {
  boxes: boolean;
  skeleton: boolean;
  labels: boolean;
  zones: boolean;
  motion: boolean;
  materials: boolean;
  helmet: boolean;
  vest: boolean;
};

const BONES: [number, number][] = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10], [5, 11], [6, 12], [11, 12],
  [11, 13], [13, 15], [12, 14], [14, 16], [0, 5], [0, 6],
];

function violation(ppe: Record<string, string>, posture: string): "ok" | "bad" | "unknown" {
  if (posture === "lying" || posture === "crawling") return "bad";
  if (Object.values(ppe).includes("missing")) return "bad";
  if (Object.values(ppe).every((v) => v === "unknown" || v === "absent")) return "unknown";
  return "ok";
}

export function VideoOverlayCanvas({
  frame,
  zones,
  toggles,
}: {
  frame: FrameMsg | null;
  zones: Zone[];
  toggles: OverlayToggles;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = frame?.w || 1280;
    const h = frame?.h || 720;
    canvas.width = w;
    canvas.height = h;
    ctx.clearRect(0, 0, w, h);
    if (!frame) return;
    if (toggles.zones) {
      ctx.strokeStyle = "rgba(56,189,248,0.9)";
      ctx.lineWidth = 2;
      for (const zone of zones.filter((z) => z.camera_id === frame.camera_id)) {
        ctx.beginPath();
        zone.polygon.forEach((pt, i) => {
          const x = pt[0] <= 1.5 ? pt[0] * w : pt[0];
          const y = pt[1] <= 1.5 ? pt[1] * h : pt[1];
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();
        ctx.stroke();
      }
    }
    if (toggles.motion && frame.motion?.detected) {
      ctx.strokeStyle = "rgba(251,191,36,0.8)";
      for (const box of frame.motion.regions) {
        ctx.strokeRect(box[0], box[1], box[2] - box[0], box[3] - box[1]);
      }
    }
    const ppeClass = (name: string) => name === "helmet" || name === "no_helmet" || name === "vest" || name === "no_vest";
    const drawObject = (obj: FrameMsg["objects"][number], color: string) => {
      const [x1, y1, x2, y2] = obj.bbox;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.fillStyle = color;
      ctx.font = "14px JetBrains Mono";
      ctx.fillText(obj.class, x1, Math.max(14, y1 - 4));
    };
    if (toggles.materials) {
      for (const obj of frame.objects) {
        if (ppeClass(obj.class)) continue;
        drawObject(obj, "#38bdf8");
      }
    }
    if (toggles.helmet) {
      for (const obj of frame.objects) {
        if (obj.class !== "helmet" && obj.class !== "no_helmet") continue;
        drawObject(obj, obj.class === "helmet" ? "#facc15" : "#ef4444");
      }
    }
    if (toggles.vest) {
      for (const obj of frame.objects) {
        if (obj.class !== "vest" && obj.class !== "no_vest") continue;
        drawObject(obj, obj.class === "vest" ? "#f97316" : "#ef4444");
      }
    }
    for (const person of frame.persons) {
      const kind = violation(person.ppe, person.posture);
      const color = kind === "bad" ? "#ef4444" : kind === "unknown" ? "#f59e0b" : "#10b981";
      const [x1, y1, x2, y2] = person.bbox;
      if (toggles.boxes) {
        ctx.strokeStyle = color;
        ctx.lineWidth = person.posture === "lying" || person.posture === "crawling" ? 4 : 2;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      }
      if (toggles.skeleton && person.keypoints) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        for (const [a, b] of BONES) {
          const pa = person.keypoints[a];
          const pb = person.keypoints[b];
          if (!pa || !pb || pa[2] < 0.3 || pb[2] < 0.3) continue;
          ctx.beginPath();
          ctx.moveTo(pa[0], pa[1]);
          ctx.lineTo(pb[0], pb[1]);
          ctx.stroke();
        }
      }
      if (toggles.labels) {
        const name = person.worker?.name ? ` ${person.worker.name}` : "";
        ctx.fillStyle = color;
        ctx.font = "14px Inter";
        ctx.fillText(`#${person.track_id} ${person.posture}${name}`, x1, Math.max(16, y1 - 6));
      }
    }
  }, [frame, zones, toggles]);

  return <canvas ref={ref} className="absolute inset-0 h-full w-full" />;
}
