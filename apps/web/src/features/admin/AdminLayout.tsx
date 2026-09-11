import { ChartNoAxesColumn, Swords, Users } from "lucide-react";
import { NavLink, Outlet } from "react-router";

import { PageHeader } from "@/components/ui/PageHeader";
import { cn } from "@/lib/cn";

const TABS = [
  { to: "stats", label: "Overview", icon: ChartNoAxesColumn },
  { to: "users", label: "Users", icon: Users },
  { to: "players", label: "Players", icon: Swords },
];

export function AdminLayout() {
  return (
    <>
      <PageHeader title="Administration" description="Accounts, tracked players and platform usage." />
      <nav aria-label="Administration" className="mb-6 inline-flex gap-1 rounded-xl border border-primary/15 bg-[#0f0d18] p-1">
        {TABS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold tracking-wider uppercase transition",
                isActive ? "bg-gradient-to-r from-[#8b48d4] to-[#6b2fa0] text-white" : "text-muted hover:text-fg",
              )
            }
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  );
}
