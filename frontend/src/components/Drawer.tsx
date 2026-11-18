import { useEffect, useId, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  width?: "md" | "lg" | "xl";
}

const widths = { md: "w-[28rem]", lg: "w-[40rem]", xl: "w-[56rem]" } as const;

/** Side panel that slides in from the end edge (right in LTR, left in RTL). Native dialog. */
export function Drawer({ open, onClose, title, children, width = "lg" }: DrawerProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cx(
        "m-0 h-dvh max-h-none max-w-full border-s border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/40",
        "ms-auto me-0",
        widths[width],
      )}
    >
      {open && (
        <div className="flex h-full flex-col">
          <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("generic.close")}
              className="-me-2 inline-flex size-10 items-center justify-center rounded-lg text-muted hover:bg-surface-2"
            >
              <span aria-hidden="true" className="text-xl leading-none">
                &times;
              </span>
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}
