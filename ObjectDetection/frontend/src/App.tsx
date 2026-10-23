import { useEffect, useRef, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { Toaster } from "sonner";
import { getToken, setToken } from "./api/client";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { EventsPage } from "./pages/EventsPage";
import { LivePage } from "./pages/LivePage";
import { LoginPage } from "./pages/LoginPage";
import { TestPage } from "./pages/TestPage";
import { AnalyticsPage, CamerasPage, MaterialsPage, SettingsPage, WallPage, WorkersPage, ZonesPage } from "./pages/SimplePages";
import { connectLive, disconnectLive, unlockAudio } from "./ws/client";

export function App() {
  const [mock, setMock] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mock") === "1") sessionStorage.setItem("siteguard_mock", "1");
    return sessionStorage.getItem("siteguard_mock") === "1";
  });
  const [authed, setAuthed] = useState(mock || Boolean(getToken()));
  const navigate = useNavigate();
  const nextPath = useRef("/");

  function leaveSample() {
    sessionStorage.removeItem("siteguard_mock");
    setToken(null);
    setMock(false);
    nextPath.current = "/test";
    setAuthed(false);
  }

  useEffect(() => {
    connectLive(mock);
    const unlock = () => unlockAudio();
    window.addEventListener("pointerdown", unlock, { once: true });
    return () => {
      disconnectLive();
      window.removeEventListener("pointerdown", unlock);
    };
  }, [mock]);

  if (!authed) {
    return (
      <LoginPage
        onDone={() => {
          setAuthed(true);
          navigate(nextPath.current);
        }}
      />
    );
  }

  return (
    <>
      <Toaster theme="dark" />
      <Routes>
        <Route
          element={
            <Layout
              mock={mock}
              leaveSample={leaveSample}
              onLogout={() => {
                sessionStorage.removeItem("siteguard_mock");
                setToken(null);
                setMock(false);
                nextPath.current = "/";
                setAuthed(false);
              }}
            />
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="live" element={<LivePage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="materials" element={<MaterialsPage />} />
          <Route path="workers" element={<WorkersPage />} />
          <Route path="zones" element={<ZonesPage />} />
          <Route path="cameras" element={<CamerasPage />} />
          <Route path="test" element={<TestPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="wall" element={<WallPage />} />
        </Route>
        <Route path="login" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
