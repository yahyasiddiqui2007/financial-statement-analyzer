import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initTheme } from "./hooks/useTheme";
import "./styles.css";

// Apply the saved theme before the first render so there's no flash of the wrong colors.
initTheme();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// In the built app, register the service worker so the site can be installed
// ("Add to Home Screen" / "Install app"). Skipped in development, where it
// would cache files while you're editing them.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err: unknown) => {
      console.warn("Service worker registration failed; the app still works.", err);
    });
  });
}
