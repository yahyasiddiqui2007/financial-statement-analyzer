import { useEffect, useState } from "react";

export type ThemeChoice = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "fsa-theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function readStoredChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // Storage can be blocked (private mode); fall back to the OS setting.
  }
  return "system";
}

function systemTheme(): ResolvedTheme {
  return window.matchMedia?.(DARK_QUERY).matches ? "dark" : "light";
}

/** Apply a choice to <html> right away, so CSS variables are correct before React renders. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
}

export function initTheme(): void {
  applyTheme(readStoredChoice());
}

export function useTheme(): {
  choice: ThemeChoice;
  resolved: ResolvedTheme;
  setChoice: (choice: ThemeChoice) => void;
} {
  const [choice, setChoiceState] = useState<ThemeChoice>(readStoredChoice);
  const [system, setSystem] = useState<ResolvedTheme>(systemTheme);

  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY);
    if (!media) return;
    const update = () => setSystem(media.matches ? "dark" : "light");
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const setChoice = (next: ThemeChoice) => {
    applyTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not persisted; the choice still applies for this visit.
    }
    setChoiceState(next);
  };

  return { choice, resolved: choice === "system" ? system : choice, setChoice };
}
