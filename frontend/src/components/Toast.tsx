import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cx, toneClasses, type Tone } from "@/lib/cx";

interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}

interface ToastApi {
  /** Show a short message. Default tone is accent. Errors on staff screens may use "urgent". */
  show: (message: string, tone?: Tone) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const [top, setTop] = useState(8);

  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const show = useCallback(
    (message: string, tone: Tone = "accent") => {
      // Sit just under the demo strip, wherever it ends right now.
      const strip = document.querySelector("[data-demo-strip]");
      setTop((strip ? Math.max(0, strip.getBoundingClientRect().bottom) : 0) + 8);
      const id = nextId.current++;
      setItems((xs) => [...xs, { id, message, tone }]);
      window.setTimeout(() => dismiss(id), 5000);
    },
    [dismiss],
  );
  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        aria-label={t("generic.notifications")}
        style={{ top }}
        className="pointer-events-none fixed inset-x-0 z-[100] flex flex-col items-center gap-2 px-3"
      >
        {items.map((it) => (
          <div
            key={it.id}
            className={cx(
              "rise-in pointer-events-auto flex max-w-[min(28rem,100%)] items-center gap-3 rounded-control border border-line-strong px-3 py-2 text-sm font-medium shadow-float",
              toneClasses[it.tone],
            )}
          >
            <span className="min-w-0">{it.message}</span>
            <button
              type="button"
              onClick={() => dismiss(it.id)}
              className="shrink-0 rounded px-1 text-xs font-semibold underline"
              aria-label={t("generic.dismiss")}
            >
              {t("generic.dismiss")}
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
