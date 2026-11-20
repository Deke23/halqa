import { Suspense } from "react";
import { Link, Outlet } from "react-router-dom";
import { useAuth } from "@/api/auth";
import { Brand } from "@/components/Brand";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { Loading } from "@/components/States";

/** For pages that work without signing in (transparency, kitchen sink). Signed-in users also get the demo strip from AppShell. */
export function PublicLayout() {
  const { isSignedIn } = useAuth();
  return (
    <>
      {!isSignedIn && (
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
            <Link to="/">
              <Brand size={26} />
            </Link>
            <LanguageSwitch />
          </div>
        </header>
      )}
      <main className="mx-auto w-full max-w-5xl flex-1 p-4 sm:p-6 lg:py-10">
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
      </main>
    </>
  );
}
