import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** ghost is the quiet text button. danger is for staff screens only. */
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  fullWidth?: boolean;
}

const variants = {
  primary: "border-accent bg-accent text-white hover:bg-accent-strong hover:border-accent-strong active:translate-y-px",
  secondary: "border-line-strong bg-surface text-ink hover:bg-surface-2 active:translate-y-px",
  ghost: "border-transparent bg-transparent text-accent-ink hover:bg-accent-soft",
  danger: "border-urgent bg-urgent text-white hover:bg-urgent-ink hover:border-urgent-ink active:translate-y-px",
} as const;

const sizes = {
  sm: "min-h-9 px-3 text-sm",
  md: "min-h-11 px-4 text-[0.95rem]",
  lg: "min-h-12 px-6 text-base",
} as const;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, fullWidth = false, className, disabled, children, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-control border font-medium leading-tight",
        "disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-2 disabled:text-muted",
        loading && "cursor-progress",
        variants[variant],
        sizes[size],
        fullWidth && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && (
        <span aria-hidden="true" className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
});
