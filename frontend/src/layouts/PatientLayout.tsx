import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "@/config";
import { Loading } from "@/components/States";
import { SimulatedTag } from "@/components/Tag";

/**
 * Mobile-first patient screen. Full width on a phone. On a desktop it sits inside a phone-like
 * frame, max width 480. Pages render in <Outlet />. Patient screens never use red.
 */
export function PatientLayout() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-1 items-start justify-center bg-surface-2 sm:p-6">
      <div className="flex min-h-[calc(100dvh-4rem)] w-full max-w-[480px] flex-col overflow-hidden bg-bg sm:min-h-[760px] sm:rounded-[2rem] sm:border-8 sm:border-ink sm:shadow-xl">
        <header className="flex items-center justify-between gap-2 border-b border-line bg-surface px-4 py-3">
          <span className="text-lg font-semibold text-accent-ink">{APP_NAME}</span>
          <SimulatedTag />
        </header>
        <main aria-label={t("nav.patient")} className="flex flex-1 flex-col overflow-y-auto p-4">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
