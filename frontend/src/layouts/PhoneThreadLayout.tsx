import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Loading } from "@/components/States";
import { SimulatedTag } from "@/components/Tag";

/**
 * Handset frame for the SMS and WhatsApp thread. The thread itself renders in <Outlet />.
 * The outer frame is decorative; the content area is the scroll region.
 */
export function PhoneThreadLayout() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-1 items-start justify-center bg-surface-2 p-2 sm:p-8">
      <div className="flex h-[min(780px,calc(100dvh-6.5rem))] w-full max-w-[380px] flex-col overflow-hidden rounded-[2rem] border-[6px] sm:rounded-[2.5rem] sm:border-[10px] border-ink bg-surface shadow-xl">
        <div aria-hidden="true" className="mx-auto mt-1 h-1.5 w-20 rounded-full bg-ink/70" />
        <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2">
          <span className="text-sm font-semibold">{t("nav.phone")}</span>
          <SimulatedTag />
        </div>
        <main className="flex min-h-0 flex-1 flex-col">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
