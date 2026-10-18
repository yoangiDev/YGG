import { ChartColumnIncreasing, Sparkles } from "lucide-react";
import { lazy, Suspense, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router";

import { Button, buttonClasses } from "@/components/ui/Button";
import { useAuth } from "@/features/auth/AuthProvider";
import { useGameAnalyses } from "@/features/games/analyses";
import { useAccounts } from "@/features/players/accounts";
import { cn } from "@/lib/cn";

import { AccountMenu, CutoffsMenu } from "./NavMenus";
import { ProfileMenu } from "./ProfileMenu";

const NewAnalysisDialog = lazy(() => import("@/features/games/NewAnalysisDialog").then((m) => ({ default: m.NewAnalysisDialog })));

/**
 * The header frame, the same on all pages. From left to right, as it reads: who you are (the logo, centred
 * in the left margin), the main thing (analyse), where to go (navigation) and, at the end, what is yours (the profile). Everything except
 * the logo starts and ends where the blocks below do (`main`: 80 rem centred, with 1 or 1.5 rem of margin); if the
 * screen is so narrow that the logo doesn't fit in the margin, the button moves aside just enough.
 */
function HeaderFrame({ children }: { children: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-ink/85 backdrop-blur-md">
      <div className="relative [--gutter:max(calc(max(0px,(100%_-_80rem)/2)_+_1rem),4.25rem)] lg:[--gutter:max(calc(max(0px,(100%_-_80rem)/2)_+_1.5rem),12.5rem)]">
        <Link
          to="/"
          className="absolute top-1/2 left-[calc(var(--gutter)/2)] flex -translate-x-1/2 -translate-y-1/2 items-center gap-3 text-xl font-black tracking-[0.2em] text-text"
        >
          <img src="/logo.svg" alt="" width={56} height={56} className="size-12 lg:size-14" />
          <span className="sr-only lg:not-sr-only">YGG</span>
        </Link>
        <div className="flex h-(--header-h) items-center gap-2 pr-[calc(max(0px,(100%_-_80rem)/2)_+_1rem)] pl-(--gutter) sm:gap-4 lg:gap-6 sm:pr-[calc(max(0px,(100%_-_80rem)/2)_+_1.5rem)]">
          {children}
        </div>
      </div>
    </header>
  );
}

/** Signed in: analyse, navigation and the profile. */
function MemberHeader() {
  const navigate = useNavigate();
  // The site's main button: always in view. With the account unlinked or unverified, it leads to where that is done;
  // otherwise, it opens the matches to analyse.
  const { active: player } = useAccounts();
  const quota = useGameAnalyses().data?.quota;
  const [analysing, setAnalysing] = useState(false);

  return (
    <HeaderFrame>
      <Button size="lg" className="shrink-0 px-3 min-[420px]:px-6" onClick={() => (player?.verified ? setAnalysing(true) : void navigate("/account"))}>
        <Sparkles className="size-4" aria-hidden="true" />
        <span className="sr-only min-[420px]:not-sr-only sm:hidden">Analyse</span>
        <span className="hidden sm:inline">New analysis</span>
        {quota && quota.limit !== null && (
          <span className="hidden tabular-nums opacity-70 md:inline">· {Math.max(0, quota.limit - quota.used)} left</span>
        )}
      </Button>

      <span aria-hidden="true" className="hidden h-6 w-px shrink-0 bg-line lg:block" />

      <nav aria-label="Main" className="flex min-w-0 items-center gap-1">
        <AccountMenu />
        <CutoffsMenu />
        <NavLink
          to="/ranks"
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 px-2 py-2 text-sm text-muted transition hover:bg-panel-light hover:text-text lg:px-3",
              isActive && "bg-acid/12 text-acid",
            )
          }
        >
          <ChartColumnIncreasing className="size-4" aria-hidden="true" />
          <span className="sr-only lg:not-sr-only">Stats by rank</span>
        </NavLink>
      </nav>

      <ProfileMenu />

      {analysing && player && (
        <Suspense fallback={null}>
          <NewAnalysisDialog playerId={player.id} open onOpenChange={setAnalysing} />
        </Suspense>
      )}
    </HeaderFrame>
  );
}

/** Signed out (login, terms…): the same frame, with the logo and sign in. */
function GuestHeader() {
  const onLogin = useLocation().pathname === "/login";
  return (
    <HeaderFrame>
      {!onLogin && (
        <Link to="/login" className={cn(buttonClasses({ size: "lg" }), "ml-auto")}>
          Sign in
        </Link>
      )}
    </HeaderFrame>
  );
}

/** The header of all pages: the full one when signed in and the minimal one when not. */
export function SiteHeader() {
  const { status } = useAuth();
  return status === "authenticated" ? <MemberHeader /> : <GuestHeader />;
}
