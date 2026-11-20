import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "@/lib/cx";

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  /** Content aligned to the end of the header (a Badge, a Button). */
  action?: ReactNode;
  padded?: boolean;
  as?: "section" | "div" | "article";
}

/** Flat card: solid surface, hair border, no shadow. Body padding is 16 px, 20 px from the sm breakpoint. */
export function Card({ title, action, padded = true, as: Tag = "section", className, children, ...rest }: CardProps) {
  return (
    <Tag className={cx("rounded-card border border-line bg-surface", className)} {...rest}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={padded ? "p-4 sm:p-5" : undefined}>{children}</div>
    </Tag>
  );
}
