import type { ReactNode } from "react";

/** Chart palette from the design system. Petrol is with-loop, a warm neutral is baseline, amber means delay or due. */
export const COLOR = {
  loop: "var(--color-accent)",
  baseline: "var(--color-line-strong)",
  baselineStroke: "var(--color-muted)",
  delay: "var(--color-due)",
  grid: "var(--color-line)",
  axis: "var(--color-muted)",
} as const;

function wrap(text: string, max: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if (cur && (cur + " " + w).length > max) {
      lines.push(cur);
      cur = w;
    } else cur = cur ? cur + " " + w : w;
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 4);
}

interface TickProps {
  x?: number;
  y?: number;
  payload?: { value: string };
  max?: number;
}

/** Category tick that wraps onto several lines, so Arabic and French labels are never clipped or rotated. */
export function WrapTick({ x = 0, y = 0, payload, max = 14 }: TickProps) {
  const lines = wrap(String(payload?.value ?? ""), max);
  return (
    <text x={x} y={y + 12} textAnchor="middle" fill="var(--color-muted)" fontSize={11}>
      {lines.map((l, i) => (
        <tspan key={i} x={x} dy={i === 0 ? 0 : 13}>
          {l}
        </tspan>
      ))}
    </text>
  );
}

/** Legend text in ink, because the default takes the bar colour and the baseline bar is pale. */
export function legendText(v: ReactNode) {
  return <span style={{ color: "var(--color-ink)" }}>{v}</span>;
}
