import { Navigate, Outlet, useLocation } from "react-router";

import { Spinner } from "@/components/ui/Spinner";
import { ErrorState } from "@/components/ui/States";

import { useAuth } from "./AuthProvider";

export function FullPageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="grid min-h-dvh place-items-center text-primary-light">
      <Spinner className="size-8" label={label} />
    </div>
  );
}

/** Rutas privadas: espera a saber si hay sesión y, si no la hay, manda al login recordando a dónde se iba. */
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

/** La API ya rechaza a los no administradores (403); esto solo evita enseñarles una pantalla vacía. */
export function RequireAdmin() {
  const { isAdmin } = useAuth();
  return isAdmin ? <Outlet /> : <Navigate to="/players" replace />;
}
