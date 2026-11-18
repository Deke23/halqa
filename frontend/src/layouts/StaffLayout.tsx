import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import type { Role } from "@/api/types";
import { Loading } from "@/components/States";
import { cx } from "@/lib/cx";

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

/** Desktop layout with a side navigation. Pages render in <Outlet />. */
export function StaffLayout() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const items = NAV.filter((n) => user && n.roles.includes(user.role));
  return (
    <div className="mx-auto flex w-full max-w-screen-2xl flex-1 flex-col md:flex-row">
      <nav
        aria-label={t("nav.mainNavigation")}
        className="flex shrink-0 gap-1 overflow-x-auto border-b border-line bg-surface p-2 md:w-56 md:flex-col md:border-b-0 md:border-e md:p-3"
      >
        {items.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            className={({ isActive }) =>
              cx(
                "flex min-h-11 items-center whitespace-nowrap rounded-lg px-3 text-sm font-medium",
                isActive ? "bg-accent-soft text-accent-ink" : "text-ink hover:bg-surface-2",
              )
            }
          >
            {t(n.labelKey)}
          </NavLink>
        ))}
      </nav>
      <main className="min-w-0 flex-1 p-4 md:p-6">
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
