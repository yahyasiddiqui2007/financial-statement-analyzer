import { useMemo } from "react";
import type { ResolvedTheme } from "./useTheme";

export interface ChartColors {
  series: [string, string, string];
  grid: string;
  axis: string;
  tick: string;
  surface: string;
}

/**
 * Chart libraries draw SVG with color attributes, which can't use CSS
 * variables directly. Read the current theme's variables from <html> so the
 * charts use exactly the same validated palette as the rest of the page.
 */
export function useChartColors(theme: ResolvedTheme): ChartColors {
  return useMemo(() => {
    void theme; // the dependency below: recompute after the theme's CSS variables change
    const style = getComputedStyle(document.documentElement);
    const read = (name: string, fallback: string) =>
      style.getPropertyValue(name).trim() || fallback;
    return {
      series: [
        read("--series-1", "#2a78d6"),
        read("--series-2", "#eb6834"),
        read("--series-3", "#1baf7a"),
      ],
      grid: read("--grid", "#e1e0d9"),
      axis: read("--axis", "#c3c2b7"),
      tick: read("--text-muted", "#6b6a65"),
      surface: read("--surface-1", "#fcfcfb"),
    };
  }, [theme]);
}
