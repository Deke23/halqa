import type { HTMLAttributes } from "react";
import { cx, toneClasses, type Tone } from "@/lib/cx";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  /** urgent (red) is for clinical urgency on staff screens only. */
  tone?: Tone;
}

export function Badge({ tone = "neutral", className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", toneClasses[tone], className)}
      {...rest}
    >
      {children}
    </span>
  );
}
