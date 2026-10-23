import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/jetbrains-mono/400.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./i18n";
import "./index.css";

if (localStorage.getItem("siteguard_lang") === "ar") {
  document.documentElement.lang = "ar";
  document.documentElement.dir = "rtl";
}

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
