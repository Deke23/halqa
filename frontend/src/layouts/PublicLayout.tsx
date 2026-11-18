import { Suspense } from "react";
import { Link, Outlet } from "react-router-dom";
import { APP_NAME } from "@/config";
import { useAuth } from "@/api/auth";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { Loading } from "@/components/States";

/** For pages that work without signing in (transparency, kitchen sink). Signed-in users also get the demo bar from AppShell. */
export function PublicLayout() {
  const { isSignedIn } = useAuth();
  return (
    <>
      {!isSignedIn && (
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
            <Link to="/" className="text-lg font-semibold text-accent-ink">
              {APP_NAME}
            </Link>
            <LanguageSwitch compact />
          </div>
        </header>
      )}
      <main className="mx-auto w-full max-w-5xl flex-1 p-4 md:p-6">
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
      </main>
    </>
  );
}
