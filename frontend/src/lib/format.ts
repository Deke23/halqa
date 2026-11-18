import type { Language } from "@/config";

/** BCP 47 tags that force Latin digits for every language. */
const LOCALE: Record<Language, string> = {
  en: "en-GB-u-nu-latn",
  ar: "ar-AE-u-nu-latn",
  fr: "fr-FR-u-nu-latn",
};

export function localeFor(lng: string): string {
  return LOCALE[(lng as Language)] ?? "en-GB-u-nu-latn";
}

export function formatDateTime(iso: string | null | undefined, lng: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(localeFor(lng), {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(d) + " UTC";
}

export function formatDate(iso: string | null | undefined, lng: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(localeFor(lng), {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

export function formatNumber(n: number, lng: string, opts?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(localeFor(lng), opts).format(n);
}

export function formatPercent(rate: number, lng: string): string {
  return formatNumber(rate, lng, { style: "percent", maximumFractionDigits: 0 });
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

export const HOUR_MS = 3_600_000;
export const DAY_MS = 24 * HOUR_MS;

export type DueStatus = "none" | "on_time" | "due_soon" | "overdue";

export interface DueInfo {
  status: DueStatus;
  /** Positive hours until due, or positive hours overdue. */
  hours: number;
}

/** Due soon means less than 24 hours left. This is display only, never routing. */
export function dueInfo(dueAt: string | null | undefined, now: Date, dueSoonHours = 24): DueInfo {
  if (!dueAt) return { status: "none", hours: 0 };
  const diff = (new Date(dueAt).getTime() - now.getTime()) / HOUR_MS;
  if (Number.isNaN(diff)) return { status: "none", hours: 0 };
  if (diff < 0) return { status: "overdue", hours: -diff };
  if (diff <= dueSoonHours) return { status: "due_soon", hours: diff };
  return { status: "on_time", hours: diff };
}
