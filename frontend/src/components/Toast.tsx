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

  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const show = useCallback(
    (message: string, tone: Tone = "accent") => {
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
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4"
      >
        {items.map((it) => (
          <div
            key={it.id}
            className={cx(
              "pointer-events-auto flex max-w-md items-center gap-3 rounded-lg border border-line px-4 py-3 text-sm shadow-lg",
              toneClasses[it.tone],
            )}
          >
            <span>{it.message}</span>
            <button
              type="button"
              onClick={() => dismiss(it.id)}
              className="rounded px-1 font-semibold underline"
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
