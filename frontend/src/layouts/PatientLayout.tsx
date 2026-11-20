import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Loading } from "@/components/States";

/**
 * Phone first. Full screen on a phone; on a desktop a clean handset frame centred on the paper.
 * The main area is the scroll container (the patient bottom navigation is sticky inside it) and
 * keeps its 16 px padding. Patient screens never use red. The demo strip above provides the brand.
 */
export function PatientLayout() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-0 flex-1 justify-center bg-surface-2 sm:px-6 sm:py-6">
      <div className="flex min-h-0 w-full max-w-[480px] flex-col overflow-hidden bg-bg sm:max-h-[880px] sm:rounded-sheet sm:border sm:border-line-strong sm:shadow-float">
        <main aria-label={t("nav.patient")} className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
