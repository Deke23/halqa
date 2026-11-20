import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import type { Role } from "@/api/types";
import { Brand } from "@/components/Brand";
import { Loading } from "@/components/States";
import { cx } from "@/lib/cx";
import { PERSONA_META } from "@/routes/personas";

interface NavItem {
  to: string;
  labelKey: string;
  roles: Role[];
}

/** Side navigation entries. Each is shown only to the roles listed. Add new staff pages here. */
const NAV: NavItem[] = [
  { to: "/staff/queue", labelKey: "nav.queue", roles: ["coordinator"] },
  { to: "/staff/worklist", labelKey: "nav.worklist", roles: ["clinician"] },
  { to: "/dashboard", labelKey: "nav.dashboard", roles: ["coordinator", "clinician", "analyst"] },
  { to: "/transparency", labelKey: "nav.transparency", roles: ["coordinator", "clinician", "analyst"] },
];

/** Desktop layout: side navigation with brand, persona and region; content capped at 1280 px. */
export function StaffLayout() {
  const { t } = useTranslation();
  const { user, persona } = useAuth();
  const items = NAV.filter((n) => user && n.roles.includes(user.role));
  const region = persona ? PERSONA_META[persona]?.region : undefined;
  return (
    <div className="flex min-h-0 flex-1 flex-col md:flex-row">
      <nav
        aria-label={t("nav.mainNavigation")}
        className="flex shrink-0 flex-col gap-3 border-b border-line bg-surface px-3 py-3 md:w-64 md:gap-6 md:border-b-0 md:border-e md:px-4 md:py-6"
      >
        <div className="hidden flex-col gap-3 md:flex">
          <Brand size={28} />
          {persona && (
            <div className="rounded-control bg-surface-2 px-3 py-2.5">
              <p className="text-sm font-semibold">{t(`personas.${persona}.name`)}</p>
              <p className="text-xs text-muted">{t(`personas.${persona}.role`)}</p>
              {region && <p className="mt-1 text-xs text-muted">{t(`regions.${region}`)}</p>}
            </div>
          )}
        </div>
        <ul className="m-0 flex list-none gap-1 overflow-x-auto p-0 md:flex-col">
          {items.map((n) => (
            <li key={n.to}>
              <NavLink
                to={n.to}
                className={({ isActive }) =>
                  cx(
                    "flex min-h-11 items-center whitespace-nowrap rounded-control px-3 text-sm font-medium",
                    isActive ? "bg-accent-soft text-accent-ink" : "text-ink hover:bg-surface-2",
                  )
                }
              >
                {t(n.labelKey)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-[1280px] p-4 sm:p-6 lg:p-8">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
