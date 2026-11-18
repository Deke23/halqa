import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { DemoBar } from "@/components/DemoBar";
import { Loading } from "@/components/States";

/**
 * Root layout for every route. Adds the skip link, the persistent demo bar when signed in
 * (not on the landing page, which has its own header), and a Suspense boundary for lazy pages.
 */
export function AppShell() {
  const { t } = useTranslation();
  const { isSignedIn } = useAuth();
  const { pathname } = useLocation();
  const showBar = isSignedIn && pathname !== "/";
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only-focusable absolute start-2 top-2 z-50 rounded bg-surface px-3 py-2 font-medium text-accent-ink shadow"
      >
        {t("nav.skipToContent")}
      </a>
      {showBar && <DemoBar />}
      <div id="main" tabIndex={-1} className="flex min-h-0 flex-1 flex-col outline-none">
        <Suspense fallback={<Loading className="flex-1" />}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  );
}
