import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Loading } from "@/components/States";
import { SimulatedTag } from "@/components/Tag";

/**
 * Handset frame for the SMS and WhatsApp thread. The thread renders in <Outlet />: make it a flex
 * column that fills the frame (scrolling message list, fixed reply box). The frame is a demo aid.
 */
export function PhoneThreadLayout() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-0 flex-1 justify-center bg-surface-2 p-3 sm:p-6">
      <div className="flex min-h-0 w-full max-w-[400px] flex-col overflow-hidden rounded-sheet border-[7px] border-ink bg-surface shadow-float sm:max-h-[840px]">
        <div aria-hidden="true" className="mx-auto mt-2 h-1.5 w-16 flex-none rounded-full bg-ink/80" />
        <div className="flex flex-none items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <span className="text-sm font-semibold">{t("nav.phone")}</span>
          <SimulatedTag />
        </div>
        <main className="flex min-h-0 flex-1 flex-col bg-surface-2/60">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
