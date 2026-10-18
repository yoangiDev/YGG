import { Check, ChevronDown, Plus, Trophy, Users, type LucideIcon } from "lucide-react";
import { useLocation, useNavigate } from "react-router";

import { ProfileIcon } from "@/components/player/PlayerBits";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/Overlay";
import { MAX_ACCOUNTS, setActiveAccount, useAccounts } from "@/features/players/accounts";
import { cn } from "@/lib/cn";
import { REGIONS } from "@/lib/roles";

/** The button of a bar menu: same look as a navigation link (the active one, with the accent). */
function NavTrigger({ to, label, icon: Icon }: { to: string; label: string; icon: LucideIcon }) {
  const active = useLocation().pathname.startsWith(to);
  return (
    <DropdownMenuTrigger
      className={cn(
        "flex cursor-pointer items-center gap-2 px-2 py-2 text-sm text-muted transition hover:bg-panel-light hover:text-text lg:px-3",
        active && "bg-acid/12 text-acid",
      )}
    >
      <Icon className="size-4" aria-hidden="true" />
      <span className="sr-only lg:not-sr-only">{label}</span>
      <ChevronDown className="hidden size-3.5 lg:block" aria-hidden="true" />
    </DropdownMenuTrigger>
  );
}

/** "Account": your linked accounts (choosing one makes it active) and linking another. */
export function AccountMenu() {
  const navigate = useNavigate();
  const { accounts, active } = useAccounts();
  const canLink = accounts.length < MAX_ACCOUNTS;
  return (
    <DropdownMenu>
      <NavTrigger to="/account" label="Account" icon={Users} />
      <DropdownMenuContent align="start" className="min-w-64">
        {accounts.map((account) => (
          <DropdownMenuItem
            key={account.id}
            onSelect={() => {
              setActiveAccount(account.id);
              void navigate("/account");
            }}
          >
            <ProfileIcon iconId={account.profile_icon_id} name={account.game_name} size={24} />
            <span className={cn("min-w-0 flex-1 truncate", account.id === active?.id && "text-acid")}>
              {account.game_name}
              <span className="text-muted">#{account.tag_line}</span>
            </span>
            <span className="text-xs text-muted">{account.region}</span>
            {account.id === active?.id && <Check className="size-4 text-acid" aria-hidden="true" />}
          </DropdownMenuItem>
        ))}
        {accounts.length > 0 && canLink && <DropdownMenuSeparator />}
        {canLink && (
          <DropdownMenuItem onSelect={() => void navigate(accounts.length > 0 ? "/account?link=1" : "/account")}>
            <Plus className="size-4" aria-hidden="true" />
            {accounts.length > 0 ? "Link another account" : "Link your account"}
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** All the servers, with just their abbreviation; choosing one opens its cutoffs. */
function Servers() {
  const navigate = useNavigate();
  return REGIONS.map((region) => (
    <DropdownMenuItem key={region.value} onSelect={() => void navigate(`/cutoffs?region=${region.value}`)}>
      <span className="font-black text-text">{region.value}</span>
    </DropdownMenuItem>
  ));
}

/** "Rank cutoffs": the list of servers. */
export function CutoffsMenu() {
  return (
    <DropdownMenu>
      <NavTrigger to="/cutoffs" label="Rank cutoffs" icon={Trophy} />
      <DropdownMenuContent align="start" className="min-w-32">
        <Servers />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
