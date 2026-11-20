import type { ReactNode } from "react";

/**
 * The loop ring is the signature of the product: one segment per step of a case.
 * Reached steps are filled, the next step breathes, and a closed case is drawn as one
 * unbroken ring. Use it only where the case itself speaks (patient home, case header,
 * queue rows, the brand mark), never as decoration.
 */
export type LoopRingProps = {
  /** Number of steps in the loop. */
  total?: number;
  /** How many steps have been reached, 0 to total. The next one is drawn as current. */
  reached: number;
  /** A closed case draws one unbroken ring. */
  closed?: boolean;
  /** Staff screens only: the current step is drawn in the urgency colour. */
  urgent?: boolean;
  /** Outer size in CSS pixels. */
  size?: number;
  /** Stroke width in CSS pixels. Defaults to a tenth of the size, within 3 to 14. */
  thickness?: number;
  /** Accessible description, already translated, for example "Step 3 of 8". */
  label: string;
  /** Content shown in the middle, for example the reading or the step count. */
  children?: ReactNode;
  className?: string;
};

function point(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = (deg * Math.PI) / 180;
  return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)];
}

function arcPath(cx: number, cy: number, r: number, from: number, to: number): string {
  const [x0, y0] = point(cx, cy, r, from);
  const [x1, y1] = point(cx, cy, r, to);
  const large = to - from > 180 ? 1 : 0;
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r.toFixed(2)} ${r.toFixed(2)} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

export function LoopRing({
  total = 8,
  reached,
  closed = false,
  urgent = false,
  size = 56,
  thickness,
  label,
  children,
  className,
}: LoopRingProps) {
  const t = thickness ?? Math.min(14, Math.max(3, Math.round(size / 10)));
  const c = size / 2;
  const r = (size - t) / 2;
  const done = Math.max(0, Math.min(total, Math.floor(reached)));
  const step = 360 / total;
  // Round caps extend past the end of the arc, so pull each end in by the cap plus half the gap.
  const capDeg = ((t / 2 / r) * 180) / Math.PI;
  const gapDeg = size >= 96 ? 3 : 4;
  const inset = capDeg + gapDeg / 2;

  return (
    <span
      className={["relative inline-grid shrink-0 place-items-center align-middle", className].filter(Boolean).join(" ")}
      style={{ width: size, height: size }}
      role="img"
      aria-label={label}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
        {closed ? (
          <circle cx={c} cy={c} r={r} fill="none" stroke="var(--color-accent)" strokeWidth={t} className="loop-ring-seg" />
        ) : (
          Array.from({ length: total }, (_, i) => {
            const from = i * step + inset;
            const to = (i + 1) * step - inset;
            const d = arcPath(c, c, r, from, to);
            const isDone = i < done;
            const isCurrent = i === done;
            if (isCurrent) {
              const colour = urgent ? "var(--color-urgent)" : "var(--color-accent)";
              return (
                <g key={i}>
                  <path d={d} fill="none" stroke="var(--color-line)" strokeWidth={t} strokeLinecap="round" />
                  <path
                    d={d}
                    fill="none"
                    stroke={colour}
                    strokeWidth={t}
                    strokeLinecap="round"
                    className="loop-ring-current"
                  />
                </g>
              );
            }
            return (
              <path
                key={i}
                d={d}
                fill="none"
                stroke={isDone ? "var(--color-accent)" : "var(--color-line)"}
                strokeWidth={t}
                strokeLinecap="round"
                className="loop-ring-seg"
              />
            );
          })
        )}
      </svg>
      {children != null && (
        <span className="absolute inset-0 grid place-items-center text-center" style={{ padding: t + 4 }}>
          {children}
        </span>
      )}
    </span>
  );
}

/** Brand mark: a ring with one step left to close. Decorative; pair it with the product name. */
export function LoopMark({ size = 22, className }: { size?: number; className?: string }) {
  const t = Math.max(2.5, size / 7);
  const c = size / 2;
  const r = (size - t) / 2;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path
        d={arcPath(c, c, r, 38, 322)}
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth={t}
        strokeLinecap="round"
      />
      <circle cx={c} cy={c - r} r={t / 2} fill="var(--color-due)" />
    </svg>
  );
}
