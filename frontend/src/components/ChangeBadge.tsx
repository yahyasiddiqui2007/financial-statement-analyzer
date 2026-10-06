import type { Tone } from "../lib/tone";

interface Props {
  text: string;
  dir: -1 | 0 | 1 | null;
  tone: Tone;
  /** Shown on hover, e.g. "vs FY2024" or why a change can't be computed. */
  title?: string;
  className?: string;
}

const ARROWS = { 1: "▲", [-1]: "▼", 0: "■" } as const;
const SPOKEN = { 1: "up", [-1]: "down", 0: "unchanged" } as const;

/** A signed change with an arrow, so direction never relies on color alone. */
export function ChangeBadge({ text, dir, tone, title, className = "" }: Props) {
  if (dir === null) {
    return (
      <span className={`change change--na ${className}`} title={title}>
        {text}
      </span>
    );
  }
  return (
    <span className={`change change--${tone} ${className}`} title={title}>
      <span aria-hidden="true" className="change__arrow">
        {ARROWS[dir]}
      </span>
      <span className="visually-hidden">{SPOKEN[dir]} </span>
      {text}
    </span>
  );
}
