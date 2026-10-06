import { useEffect, useState, type FormEvent } from "react";
import type { ThemeChoice } from "../hooks/useTheme";

const TICKER_PATTERN = /^[A-Za-z0-9.-]{1,10}$/;
const THEME_ORDER: ThemeChoice[] = ["system", "light", "dark"];
const THEME_LABEL: Record<ThemeChoice, string> = { system: "Auto", light: "Light", dark: "Dark" };

interface Props {
  ticker: string | null;
  loading: boolean;
  onSearch: (ticker: string) => void;
  theme: ThemeChoice;
  onThemeChange: (choice: ThemeChoice) => void;
}

export function TopBar({ ticker, loading, onSearch, theme, onThemeChange }: Props) {
  const [input, setInput] = useState(ticker ?? "");
  const [error, setError] = useState<string | null>(null);

  // Keep the box in sync when the ticker changes elsewhere (example chips, back button).
  useEffect(() => setInput(ticker ?? ""), [ticker]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = input.trim().toUpperCase();
    if (!TICKER_PATTERN.test(value)) {
      setError("Enter a ticker like AAPL or BRK.B");
      return;
    }
    setError(null);
    onSearch(value);
  };

  const nextTheme = THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length]!;

  return (
    <header className="topbar">
      <div className="topbar__inner">
        <a className="brand" href="/" aria-label="Financial Statement Analyzer home">
          <span className="brand__mark" aria-hidden="true">
            FSA
          </span>
          <span className="brand__name">Financial Statement Analyzer</span>
        </a>

        <form className="search" role="search" onSubmit={submit} noValidate>
          <label htmlFor="ticker-input" className="visually-hidden">
            Company ticker
          </label>
          <span className="search__prompt" aria-hidden="true">
            ›
          </span>
          <input
            id="ticker-input"
            className="search__input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ticker, e.g. AAPL"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={10}
            aria-invalid={error !== null}
            aria-describedby={error ? "ticker-error" : undefined}
          />
          <button className="search__button" type="submit" disabled={loading}>
            {loading ? "Loading…" : "Analyze"}
          </button>
          {error && (
            <p id="ticker-error" className="search__error" role="alert">
              {error}
            </p>
          )}
        </form>

        <button
          type="button"
          className="theme-toggle"
          onClick={() => onThemeChange(nextTheme)}
          aria-label={`Color theme: ${THEME_LABEL[theme]}. Switch to ${THEME_LABEL[nextTheme]}.`}
        >
          {THEME_LABEL[theme]}
        </button>
      </div>
    </header>
  );
}
