import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";
import { BACKEND_UNREACHABLE, isApiError } from "@/api/client";
import { Button } from "./Button";

export function Loading({ label, className }: { label?: string; className?: string }) {
  const { t } = useTranslation();
  const text = label ?? t("generic.loading");
  return (
    <div role="status" className={cx("flex items-center justify-center gap-3 p-8 text-muted", className)}>
      <span aria-hidden="true" className="inline-block size-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      <span>{text}</span>
    </div>
  );
}

export interface EmptyStateProps {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  const { t } = useTranslation();
  return (
    <div className={cx("flex flex-col items-center gap-2 rounded-card border border-dashed border-line p-8 text-center", className)}>
      <p className="font-medium">{title ?? t("generic.empty")}</p>
      {description && <p className="max-w-prose text-sm text-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export interface ErrorStateProps {
  /** Pass the caught error. ApiError, Error and strings are understood. */
  error?: unknown;
  title?: ReactNode;
  onRetry?: () => void;
  className?: string;
}

/** Turns an error into text. Status 0 (backend not reachable) gets a translated message. */
export function useErrorText() {
  const { t } = useTranslation();
  return (error: unknown): string => {
    if (isApiError(error)) {
      if (error.status === 0 || error.message === BACKEND_UNREACHABLE) return t("generic.backendUnreachable");
      return error.message;
    }
    if (error instanceof Error) return error.message;
    if (typeof error === "string") return error;
    return t("generic.error");
  };
}

/** Shows the API error message. Never leaves a blank page on failure. */
export function ErrorState({ error, title, onRetry, className }: ErrorStateProps) {
  const { t } = useTranslation();
  const errorText = useErrorText();
  return (
    <div role="alert" className={cx("flex flex-col items-center gap-2 rounded-card border border-line bg-surface-2 p-6 text-center", className)}>
      <p className="font-semibold">{title ?? t("generic.errorTitle")}</p>
      <p className="max-w-prose text-sm text-muted">{errorText(error)}</p>
      {isApiError(error) && error.status > 0 && (
        <p className="text-xs text-muted">
          <span className="clinical">{error.status}</span> {error.code}
        </p>
      )}
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-2">
          {t("generic.retry")}
        </Button>
      )}
    </div>
  );
}
