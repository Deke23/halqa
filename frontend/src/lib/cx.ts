/** Join class names, skipping falsy values. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export type Tone = "neutral" | "accent" | "due" | "urgent" | "info";

/** Background and text classes per tone. All pairs meet WCAG AA. */
export const toneClasses: Record<Tone, string> = {
  neutral: "bg-surface-2 text-ink",
  accent: "bg-accent-soft text-accent-ink",
  due: "bg-due-soft text-due-ink",
  urgent: "bg-urgent-soft text-urgent-ink",
  info: "bg-info-soft text-info-ink",
};
