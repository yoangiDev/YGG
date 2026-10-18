import { Navigate, Outlet, useLocation } from "react-router";

import { Spinner } from "@/components/ui/Spinner";
import { ErrorState } from "@/components/ui/States";

import { useAuth } from "./AuthProvider";

export function FullPageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="grid min-h-dvh place-items-center text-acid">
      <Spinner className="size-8" label={label} />
    </div>
  );
}

/** Private routes: waits to know whether there is a session and, if not, sends to the login remembering where it was going. */
export function RequireAuth() {
  const { status, error, retry } = useAuth();
  const location = useLocation();

  if (status === "loading") return <FullPageLoader label="Restoring session" />;
  if (status === "error") {
    return (
      <div className="grid min-h-dvh place-items-center">
        <ErrorState error={error} onRetry={retry} />
      </div>
    );
  }
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

/** The API already rejects non-administrators (403); this only avoids showing them an empty screen. */
export function RequireAdmin() {
  const { isAdmin } = useAuth();
  return isAdmin ? <Outlet /> : <Navigate to="/account" replace />;
}
