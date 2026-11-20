import { useTranslation } from "react-i18next";
import { APP_NAME, APP_NAME_AR } from "@/config";
import { cx } from "@/lib/cx";
import { LoopMark } from "./LoopRing";

export interface BrandProps {
  /** Mark size in px. The name scales with it. */
  size?: number;
  /** Hide the name and show only the mark. */
  markOnly?: boolean;
  /** Light text, for the dark demo strip. */
  onDark?: boolean;
  className?: string;
}

/** The loop mark plus the product name. Arabic screens show the Arabic name. */
export function Brand({ size = 24, markOnly, onDark, className }: BrandProps) {
  const { i18n } = useTranslation();
  const name = i18n.language.startsWith("ar") ? APP_NAME_AR : APP_NAME;
  return (
    <span className={cx("inline-flex items-center gap-2 font-semibold", onDark ? "text-demo-ink" : "text-ink", className)}>
      {onDark ? (
        <span className="grid place-items-center rounded-md bg-bg" style={{ padding: Math.round(size * 0.12) }}>
          <LoopMark size={size} />
        </span>
      ) : (
        <LoopMark size={size} />
      )}
      {!markOnly && <span style={{ fontSize: Math.round(size * 0.72) }}>{name}</span>}
    </span>
  );
}
