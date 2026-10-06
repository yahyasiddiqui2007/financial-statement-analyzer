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
