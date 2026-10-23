import { create } from "zustand";
import type { EventItem, FrameMsg } from "../api/types";

type Status = "offline" | "live" | "reconnecting";

type LiveState = {
  status: Status;
  frames: Record<string, FrameMsg>;
  events: EventItem[];
  muted: boolean;
  setStatus: (status: Status) => void;
  pushFrame: (frame: FrameMsg) => void;
  forgetCamera: (cameraId: string) => void;
  pushEvent: (event: EventItem) => void;
  setMuted: (muted: boolean) => void;
};

export const useLive = create<LiveState>((set) => ({
  status: "offline",
  frames: {},
  events: [],
  muted: localStorage.getItem("siteguard_muted") === "1",
  setStatus: (status) => set({ status }),
  pushFrame: (frame) =>
    set((state) => ({ frames: { ...state.frames, [frame.camera_id]: frame } })),
  forgetCamera: (cameraId) =>
    set((state) => {
      if (!state.frames[cameraId]) return state;
      const frames = { ...state.frames };
      delete frames[cameraId];
      return { frames };
    }),
  pushEvent: (event) => set((state) => ({ events: [event, ...state.events].slice(0, 40) })),
  setMuted: (muted) => {
    localStorage.setItem("siteguard_muted", muted ? "1" : "0");
    set({ muted });
  },
}));
