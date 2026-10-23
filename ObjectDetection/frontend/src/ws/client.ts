import { getToken } from "../api/client";
import type { EventItem, FrameMsg } from "../api/types";
import { useLive } from "../store/live";

let socket: WebSocket | null = null;
let timer: number | null = null;
let attempt = 0;
let audioUnlocked = false;

export function unlockAudio(): void {
  audioUnlocked = true;
  const audio = new Audio("/alert.wav");
  audio.volume = 0;
  void audio.play().catch(() => undefined);
}

function beep(): void {
  if (!audioUnlocked || useLive.getState().muted) return;
  const audio = new Audio("/alert.wav");
  void audio.play().catch(() => undefined);
}

export function connectLive(mock: boolean): void {
  if (mock) {
    useLive.getState().setStatus("live");
    return;
  }
  if (socket && socket.readyState <= WebSocket.OPEN) return;
  const token = getToken();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  socket = new WebSocket(url);
  socket.onopen = () => {
    attempt = 0;
    useLive.getState().setStatus("live");
    socket?.send(JSON.stringify({ type: "subscribe", frames: true }));
  };
  socket.onmessage = (ev) => {
    const msg = JSON.parse(String(ev.data)) as { type: string; event?: EventItem };
    if (msg.type === "frame") useLive.getState().pushFrame(msg as FrameMsg);
    if (msg.type === "event" && msg.event) {
      useLive.getState().pushEvent(msg.event);
      if (msg.event.severity === "critical") beep();
    }
  };
  socket.onclose = () => {
    useLive.getState().setStatus("reconnecting");
    const delay = Math.min(10000, 500 * 2 ** attempt);
    attempt += 1;
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(() => connectLive(false), delay);
  };
}

export function disconnectLive(): void {
  if (timer) window.clearTimeout(timer);
  socket?.close();
  socket = null;
}
