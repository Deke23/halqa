import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/api/auth";
import type { Role } from "@/api/types";
import { homeFor } from "./personas";

/** Sends signed-out visitors to the landing page. Wrap every signed-in route group. */
export function RequireAuth() {
  const { isSignedIn } = useAuth();
  const loc = useLocation();
  if (!isSignedIn) return <Navigate to="/" replace state={{ from: loc.pathname }} />;
  return <Outlet />;
}

/**
 * Only lets the listed roles through. Anyone else goes to their own home screen.
 * Usage in the route table: <Route element={<RoleGuard roles={["clinician"]} />}> ... </Route>
 */
export function RoleGuard({ roles }: { roles: Role[] }) {
  const { user, persona } = useAuth();
  if (!user) return <Navigate to="/" replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(persona, user.role)} replace />;
  return <Outlet />;
}
