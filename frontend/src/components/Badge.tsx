import type { HTMLAttributes } from "react";
import { cx, toneClasses, type Tone } from "@/lib/cx";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  /** urgent (clay red) is an explicit staff-only tone: never use it on patient screens. */
  tone?: Tone;
  /** Leading dot. On by default. */
  dot?: boolean;
}

/** Rectangular chip (radius 6) with a leading dot. */
export function Badge({ tone = "neutral", dot = true, className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cx("inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium leading-5", toneClasses[tone], className)}
      {...rest}
    >
      {dot && <span aria-hidden="true" className="inline-block size-1.5 shrink-0 rounded-full bg-current" />}
      {children}
    </span>
  );
}
