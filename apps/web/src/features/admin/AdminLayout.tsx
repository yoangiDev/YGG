import { ChartNoAxesColumn, Swords, Users } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router";

import { PageHeader } from "@/components/ui/PageHeader";
import { cn } from "@/lib/cn";

const TABS = [
  { to: "stats", label: "Overview", icon: ChartNoAxesColumn },
  { to: "users", label: "Users", icon: Users },
  { to: "players", label: "Players", icon: Swords },
];

export function AdminLayout() {
  const { pathname } = useLocation();
  const current = TABS.find(({ to }) => pathname.endsWith(`/${to}`))?.label;
  return (
    <>
      <PageHeader
        title="Administration"
        documentTitle={current ? `Administration · ${current}` : "Administration"}
        description="Accounts, tracked players and platform usage."
      />
      <nav aria-label="Administration" className="mb-6 inline-flex gap-1 border border-line p-1">
        {TABS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "inline-flex items-center gap-2 px-3 py-2.5 text-xs font-bold tracking-wider uppercase transition sm:px-4",
                isActive ? "bg-acid/12 text-acid" : "text-muted hover:bg-panel-light hover:text-text",
              )
            }
          >
            <Icon className="size-4 max-[399px]:hidden" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  );
}
