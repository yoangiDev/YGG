import { Outlet, ScrollRestoration } from "react-router";

import { TooltipProvider } from "@/components/ui/Overlay";
import { useAuth } from "@/features/auth/AuthProvider";
import { SiteFooter } from "@/features/legal/SiteFooter";
import { BackgroundJobs } from "@/features/snapshots/BackgroundJobs";

import { SiteHeader } from "./SiteHeader";

/**
 * Frame of the private screens. Loaded as a separate chunk (see router.tsx):
 * the menu and Radix tooltips aren't needed to render the login.
 */
export function AppLayout() {
  const { user } = useAuth();

  return (
    <TooltipProvider>
      <div className="flex min-h-dvh flex-col">
        {import.meta.env.VITE_DEMO_EMAIL && user?.email === import.meta.env.VITE_DEMO_EMAIL && (
          <p role="note" className="border-b border-stat-gold/30 bg-stat-gold/10 px-4 py-1.5 text-center text-xs text-stat-gold">
            Read-only demo with seeded, anonymized games. Changes are disabled.
          </p>
        )}

        <SiteHeader />

        {/* The footer always starts below the first screenful: if it peeked out while the screen loads, it would jump down when the content arrives. */}
        <main id="main" className="mx-auto min-h-[calc(100dvh-var(--header-h))] w-full max-w-7xl flex-1 px-4 py-5 sm:px-6 sm:py-6">
          <Outlet />
        </main>
        <SiteFooter />
        <ScrollRestoration />
        <BackgroundJobs />
      </div>
    </TooltipProvider>
  );
}
