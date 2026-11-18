import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  fullWidth?: boolean;
}

const variants = {
  primary: "bg-accent text-white hover:bg-accent-strong border-transparent",
  secondary: "bg-surface text-ink border-line hover:bg-surface-2",
  ghost: "bg-transparent text-accent-ink border-transparent hover:bg-accent-soft",
  // Staff screens only. Do not use on patient screens.
  danger: "bg-urgent text-white hover:bg-urgent-ink border-transparent",
} as const;

const sizes = {
  sm: "min-h-9 px-3 text-sm",
  md: "min-h-11 px-4 text-base",
  lg: "min-h-12 px-5 text-lg",
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
        "inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-60",
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
