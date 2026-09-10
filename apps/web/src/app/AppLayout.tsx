import { ChevronDown, LogOut, Shield, Trophy, Users } from "lucide-react";
import { Link, NavLink, Outlet, ScrollRestoration, useNavigate } from "react-router";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/Overlay";
import { useAuth } from "@/features/auth/AuthProvider";
import { cn } from "@/lib/cn";

export function AppLayout() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const links = [
    { to: "/players", label: "Players", icon: Users },
    { to: "/cutoffs", label: "Rank cutoffs", icon: Trophy },
    ...(isAdmin ? [{ to: "/admin", label: "Admin", icon: Shield }] : []),
  ];

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-30 border-b border-border/70 bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
          <Link to="/players" className="flex shrink-0 items-center gap-2 text-sm font-bold tracking-[0.25em] text-fg">
            <img src="/logo.svg" alt="" width={28} height={28} className="size-7" />
            YGG
          </Link>

          <nav aria-label="Main" className="flex min-w-0 items-center gap-1">
            {links.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-muted transition hover:bg-surface-2 hover:text-fg sm:px-3",
                    isActive && "bg-primary/12 text-primary-light",
                  )
                }
              >
                <Icon className="size-4" aria-hidden="true" />
                <span className="sr-only sm:not-sr-only">{label}</span>
              </NavLink>
            ))}
          </nav>

          <DropdownMenu>
            <DropdownMenuTrigger className="ml-auto flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-fg hover:bg-surface-2">
              <span className="grid size-7 place-items-center rounded-full bg-primary-dim text-xs font-bold uppercase">
                {user?.username.charAt(0) ?? "?"}
              </span>
              <span className="hidden max-w-32 truncate md:inline">{user?.username}</span>
              <ChevronDown className="size-3.5 text-muted" aria-hidden="true" />
              <span className="sr-only">Account menu</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <div className="px-3 py-2">
                <p className="truncate text-sm font-semibold text-fg">{user?.username}</p>
                <p className="truncate text-xs text-muted">{user?.email}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => {
                  void logout().then(() => navigate("/login", { replace: true }));
                }}
              >
                <LogOut className="size-4" aria-hidden="true" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto max-w-7xl px-4 py-6 focus:outline-none sm:px-6 sm:py-8">
        <Outlet />
      </main>
      <ScrollRestoration />
    </div>
  );
}

/** Cabecera de página común: título, subtítulo y acciones. */
export function PageHeader({
  title,
  description,
  actions,
  back,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  back?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {back}
        <h1 className="truncate text-2xl font-bold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
