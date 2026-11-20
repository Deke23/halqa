import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { DemoBar } from "@/components/DemoBar";
import { Loading } from "@/components/States";

/**
 * Root layout for every route. A full-height column: the demo strip takes its own row (so it can
 * never cover content), and the page area below it scrolls. Layouts inside use flex-1 and min-h-0.
 */
export function AppShell() {
  const { t } = useTranslation();
  const { isSignedIn } = useAuth();
  const { pathname } = useLocation();
  const showBar = isSignedIn && pathname !== "/";
  return (
    <div className="flex h-dvh flex-col">
      <a
        href="#main"
        className="sr-only-focusable absolute start-2 top-2 z-50 rounded-md bg-surface px-3 py-2 font-medium text-accent-ink shadow-float"
      >
        {t("nav.skipToContent")}
      </a>
      {showBar && <DemoBar />}
      <div id="main" tabIndex={-1} className="flex min-h-0 flex-1 flex-col overflow-y-auto outline-none">
        <Suspense fallback={<Loading className="flex-1" />}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  );
}
