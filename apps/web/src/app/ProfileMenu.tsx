import { ChevronDown, LogOut, Shield, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { ProfileIcon } from "@/components/player/PlayerBits";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/Overlay";
import { useAuth } from "@/features/auth/AuthProvider";
import { useAccounts } from "@/features/players/accounts";

import { DeleteAccountDialog } from "./DeleteAccountDialog";
import { SocialLinks } from "./SocialIcons";

/** The profile menu, large: the LoL icon of your first linked account (the avatar), your username, language,
 * sign out and YGG's social networks. */
export function ProfileMenu() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const { accounts } = useAccounts();
  const [deleting, setDeleting] = useState(false);
  const first = accounts[0];
  const name = user?.username ?? "";

  const avatar = (size: number) =>
    first ? (
      <ProfileIcon iconId={first.profile_icon_id} name={first.game_name} size={size} />
    ) : (
      <span
        style={{ width: size, height: size }}
        className="grid shrink-0 place-items-center rounded-full bg-acid-dark text-lg font-black text-ink uppercase"
      >
        {name.charAt(0)}
      </span>
    );

  return (
    <>
    <DropdownMenu>
      <DropdownMenuTrigger className="ml-auto flex cursor-pointer items-center gap-1.5 px-1 py-1.5 text-text transition hover:bg-panel-light sm:gap-3 sm:px-2">
        <span className="sm:hidden">{avatar(40)}</span>
        <span className="hidden sm:block">{avatar(48)}</span>
        <span className="hidden max-w-40 truncate text-base font-black md:inline">{name}</span>
        <ChevronDown className="hidden size-4 text-muted sm:block" aria-hidden="true" />
        <span className="sr-only">Profile menu</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0">
        <div className="flex items-center gap-4 p-5">
          {avatar(64)}
          <div className="min-w-0">
            <p className="truncate text-lg font-black text-text">{name}</p>
            <p className="truncate text-sm text-muted">{user?.email}</p>
          </div>
        </div>
        <DropdownMenuSeparator />
        {isAdmin && (
          <DropdownMenuItem className="px-5 py-3.5 text-base" onSelect={() => void navigate("/admin")}>
            <Shield className="size-5" aria-hidden="true" />
            Admin
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="px-5 py-3.5 text-base"
          onSelect={() => {
            void logout().then(() => navigate("/login", { replace: true }));
          }}
        >
          <LogOut className="size-5" aria-hidden="true" />
          Sign out
        </DropdownMenuItem>
        {!isAdmin && (
          <DropdownMenuItem
            className="px-5 py-3.5 text-base text-danger data-[highlighted]:bg-danger/10 data-[highlighted]:text-danger"
            onSelect={() => setDeleting(true)}
          >
            <Trash2 className="size-5" aria-hidden="true" />
            Delete account
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <SocialLinks className="flex items-center gap-6 px-5 py-4" />
      </DropdownMenuContent>
    </DropdownMenu>
    <DeleteAccountDialog open={deleting} onOpenChange={setDeleting} />
    </>
  );
}
