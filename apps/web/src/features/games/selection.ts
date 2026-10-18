import { createContext, useContext, useSyncExternalStore } from "react";

/**
 * Which moment is chosen. It lives outside the page's state so that choosing one repaints only what shows it (the
 * stage, the lists and the cards) and not the table, the charts or the patterns, which don't change.
 */
export function createSelection(initial: string | null) {
  let value = initial;
  const listeners = new Set<() => void>();
  return {
    get: () => value,
    set: (next: string | null) => {
      if (next === value) return;
      value = next;
      for (const listener of listeners) listener();
    },
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}
export type Selection = ReturnType<typeof createSelection>;

const SelectionContext = createContext<Selection | null>(null);
export const SelectionProvider = SelectionContext.Provider;

export function useSelection(): Selection {
  const selection = useContext(SelectionContext);
  if (!selection) throw new Error("useSelection must be used inside <SelectionProvider>");
  return selection;
}

/** The chosen moment; the component that reads it repaints when it changes. */
export function useSelected(): string | null {
  const selection = useSelection();
  return useSyncExternalStore(selection.subscribe, selection.get);
}
