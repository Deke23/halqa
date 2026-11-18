import { lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/api/auth";
import { isApiError } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { AppShell } from "@/layouts/AppShell";
import { PatientLayout } from "@/layouts/PatientLayout";
import { PhoneThreadLayout } from "@/layouts/PhoneThreadLayout";
import { PublicLayout } from "@/layouts/PublicLayout";
import { StaffLayout } from "@/layouts/StaffLayout";
import Landing from "@/routes/Landing";
import { RequireAuth, RoleGuard } from "@/routes/RoleGuard";

// Each feature is a lazy chunk. The owning workstream replaces the file behind the import.
const PatientApp = lazy(() => import("@/features/patient"));
const PhoneApp = lazy(() => import("@/features/phone"));
const StaffQueue = lazy(() => import("@/features/staff/queue"));
const StaffCase = lazy(() => import("@/features/staff/case"));
const StaffWorklist = lazy(() => import("@/features/staff/worklist"));
const Dashboard = lazy(() => import("@/features/dashboard"));
const Transparency = lazy(() => import("@/features/transparency"));
const KitchenSink = lazy(() => import("@/routes/KitchenSink"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      refetchOnWindowFocus: false,
      retry: (count, error) => !(isApiError(error) && error.status >= 400 && error.status < 500) && count < 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<Landing />} />

                <Route element={<PublicLayout />}>
                  <Route path="transparency" element={<Transparency />} />
                  {/* Hidden from navigation. Renders every shared component. */}
                  <Route path="kitchen-sink" element={<KitchenSink />} />
                </Route>

                <Route element={<RequireAuth />}>
                  <Route element={<RoleGuard roles={["patient"]} />}>
                    <Route element={<PatientLayout />}>
                      <Route path="patient/*" element={<PatientApp />} />
                    </Route>
                    <Route element={<PhoneThreadLayout />}>
                      <Route path="phone/*" element={<PhoneApp />} />
                    </Route>
                  </Route>

                  <Route element={<StaffLayout />}>
                    <Route element={<RoleGuard roles={["coordinator"]} />}>
                      <Route path="staff/queue" element={<StaffQueue />} />
                    </Route>
                    <Route element={<RoleGuard roles={["clinician"]} />}>
                      <Route path="staff/worklist" element={<StaffWorklist />} />
                    </Route>
                    <Route element={<RoleGuard roles={["coordinator", "clinician"]} />}>
                      <Route path="staff/cases/:id" element={<StaffCase />} />
                    </Route>
                    <Route element={<RoleGuard roles={["coordinator", "clinician", "analyst"]} />}>
                      <Route path="dashboard" element={<Dashboard />} />
                    </Route>
                  </Route>
                </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
