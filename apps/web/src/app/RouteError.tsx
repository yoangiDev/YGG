import { Compass } from "lucide-react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router";

import { buttonClasses } from "@/components/ui/Button";
import { EmptyState, ErrorState } from "@/components/ui/States";

export function RouteError() {
  const error = useRouteError();

  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />;

  // Un despliegue nuevo invalida los chunks con hash de la versión anterior: recargar lo resuelve.
  const staleChunk = error instanceof Error && /dynamically imported module|Importing a module script failed/i.test(error.message);

  return (
    <div className="grid min-h-[60dvh] place-items-center">
      <ErrorState
        error={staleChunk ? new Error("A new version of YGG is available.") : error}
        onRetry={() => {
          window.location.reload();
        }}
      />
    </div>
  );
}

export function NotFound() {
  return (
    <EmptyState
      className="min-h-[60dvh] justify-center"
      icon={<Compass className="size-10" />}
      title="Page not found"
      description="This page does not exist or you do not have access to it."
      action={
        <Link to="/players" className={buttonClasses({ variant: "outline", size: "sm" })}>
          Back to players
        </Link>
      }
    />
  );
}
