import { useQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { api, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

type Player = Schemas["PlayerResponse"];

/** What the API admits (`MAX_ACCOUNTS`): the main one and a smurf or two. */
export const MAX_ACCOUNTS = 5;

// The account you are viewing the site with: remembered between visits, and the bar and the account screen share it.
const KEY = "ygg.account";
const listeners = new Set<() => void>();
let active: number | null = null;
try {
  active = Number(localStorage.getItem(KEY)) || null;
} catch {
  // no storage (private window): valid for this visit
}

export function setActiveAccount(id: number | null) {
  active = id;
  try {
    if (id === null) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, String(id));
  } catch {
    // same
  }
  listeners.forEach((listener) => listener());
}

/** Your linked accounts and the active one (the chosen one if it is still linked; otherwise, the first). */
export function useAccounts() {
  const query = useQuery({
    queryKey: queryKeys.playerList(),
    queryFn: () => unwrap(api.GET("/players/", { params: { query: { limit: MAX_ACCOUNTS } } })),
  });
  const chosen = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => active,
  );
  const accounts: Player[] = query.data?.items ?? [];
  return { query, accounts, active: accounts.find((account) => account.id === chosen) ?? accounts[0] };
}
