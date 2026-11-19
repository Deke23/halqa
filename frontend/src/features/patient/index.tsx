import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading } from "@/components";
import { cx } from "@/lib/cx";
import { usePatientCase } from "./api";
import { Shortcuts } from "./Shortcuts";
import { CaseProvider, useCurrentCase } from "./ui";

import Home from "./Home";
import Result from "./Result";

const Understand = lazy(() => import("./Understand"));
const Journey = lazy(() => import("./Journey"));
const Confirm = lazy(() => import("./Confirm"));
const Visit = lazy(() => import("./Visit"));
const Weekly = lazy(() => import("./Weekly"));
const Messages = lazy(() => import("./Messages"));
const Privacy = lazy(() => import("./Privacy"));

const NAV = [
  { to: "/patient", key: "home", end: true },
  { to: "/patient/result", key: "result", end: false },
  { to: "/patient/journey", key: "journey", end: false },
  { to: "/patient/messages", key: "messages", end: false },
  { to: "/patient/privacy", key: "privacy", end: false },
] as const;

/**
 * Patient app (Abu Dhabi persona, mobile first). It renders inside PatientLayout, which provides the
 * header and the scrolling main area. Every screen reads the one shared case.
 */
export default function PatientApp() {
  const { t } = useTranslation("patient");
  const q = usePatientCase();

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <EmptyState title={t("noCase.title")} description={t("noCase.description")} />;

  return (
    <CaseProvider value={q.data}>
      <div className="flex flex-1 flex-col gap-6">
        <div className="flex flex-1 flex-col gap-4">
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route index element={<Home />} />
              <Route path="result" element={<Result />} />
              <Route path="understand" element={<Understand />} />
              <Route path="journey" element={<Journey />} />
              <Route path="confirm" element={<Confirm />} />
              <Route path="visit" element={<Visit />} />
              <Route path="weekly" element={<Weekly />} />
              <Route path="messages" element={<Messages />} />
              <Route path="privacy" element={<Privacy />} />
              <Route path="*" element={<Navigate to="/patient" replace />} />
            </Routes>
          </Suspense>
        </div>
        <ShortcutsHost />
        <BottomNav />
      </div>
    </CaseProvider>
  );
}

function ShortcutsHost() {
  const c = useCurrentCase();
  return <Shortcuts c={c} flow="auh" />;
}

function BottomNav() {
  const { t } = useTranslation("patient");
  return (
    <nav
      aria-label={t("nav.label")}
      className="sticky -bottom-4 z-20 -mx-4 -mb-4 border-t border-line bg-surface"
    >
      <ul className="m-0 flex list-none p-0">
        {NAV.map((n) => (
          <li key={n.to} className="min-w-0 flex-1">
            <NavLink
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cx(
                  "flex min-h-14 items-center justify-center px-1 py-2 text-center text-xs font-semibold leading-tight",
                  isActive ? "bg-accent-soft text-accent-ink" : "text-muted hover:bg-surface-2",
                )
              }
            >
              {t(`nav.${n.key}`)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
