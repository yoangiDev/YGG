import { CircleCheck, CircleX } from "lucide-react";
import { createContext, use, useCallback, useMemo, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type ToastKind = "success" | "error";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const DISMISS_AFTER_MS = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = nextId.current++;
    setToasts((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, DISMISS_AFTER_MS);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({ success: (message) => push("success", message), error: (message) => push("error", message) }),
    [push],
  );

  return (
    <ToastContext value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(92vw,22rem)] flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              "pointer-events-auto flex items-start gap-2 rounded-lg border px-4 py-3 text-sm text-white shadow-xl",
              toast.kind === "success" ? "border-stat-green/40 bg-[#1a3a2a]" : "border-stat-red/40 bg-[#5a1a1a]",
            )}
          >
            {toast.kind === "success" ? (
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-stat-green" aria-hidden="true" />
            ) : (
              <CircleX className="mt-0.5 size-4 shrink-0 text-stat-red" aria-hidden="true" />
            )}
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext>
  );
}

export function useToast(): ToastApi {
  const context = use(ToastContext);
  if (!context) throw new Error("useToast must be used inside <ToastProvider>");
  return context;
}
