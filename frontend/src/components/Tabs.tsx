import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cx } from "@/lib/cx";

export interface TabItem {
  id: string;
  label: ReactNode;
  /** Optional count shown next to the label. */
  count?: number;
}

export interface TabsProps {
  tabs: TabItem[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  /** id of the panel element the active tab controls. Optional. */
  panelId?: string;
  className?: string;
}

/** Tab list with roving focus. Arrow keys move, Home and End jump. RTL-aware. */
export function Tabs({ tabs, value, onChange, label, panelId, className }: TabsProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  function onKeyDown(e: KeyboardEvent, index: number) {
    const rtl = getComputedStyle(e.currentTarget as Element).direction === "rtl";
    const next = rtl ? "ArrowLeft" : "ArrowRight";
    const prev = rtl ? "ArrowRight" : "ArrowLeft";
    let target = -1;
    if (e.key === next) target = (index + 1) % tabs.length;
    else if (e.key === prev) target = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") target = 0;
    else if (e.key === "End") target = tabs.length - 1;
    if (target >= 0) {
      e.preventDefault();
      refs.current[target]?.focus();
      onChange(tabs[target]!.id);
    }
  }

  return (
    <div role="tablist" aria-label={label} className={cx("flex gap-1 overflow-x-auto border-b border-line", className)}>
      {tabs.map((tab, i) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="tab"
            type="button"
            id={`tab-${tab.id}`}
            aria-selected={selected}
            aria-controls={panelId}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cx(
              "-mb-px inline-flex min-h-11 items-center gap-2 whitespace-nowrap border-b-2 px-3 text-sm font-medium",
              selected ? "border-accent text-accent-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="rounded-full bg-surface-2 px-2 text-xs text-ink latin-digits">{tab.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
