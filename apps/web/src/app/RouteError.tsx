import { Compass } from "lucide-react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router";

import { buttonClasses } from "@/components/ui/Button";
import { PageTitle } from "@/components/ui/PageTitle";
import { EmptyState, ErrorState } from "@/components/ui/States";

export function RouteError() {
  const error = useRouteError();

  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />;

  // A new deployment invalidates the hashed chunks of the previous version: reloading fixes it.
  const staleChunk = error instanceof Error && /dynamically imported module|Importing a module script failed/i.test(error.message);

  return (
    <div className="grid min-h-[60dvh] place-items-center">
      <PageTitle>Something went wrong</PageTitle>
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
    <>
    <PageTitle>Page not found</PageTitle>
    <EmptyState
      heading="h1"
      className="min-h-[60dvh] justify-center"
      icon={<Compass className="size-10" />}
      title="Page not found"
      description="This page does not exist or you do not have access to it."
      action={
        <Link to="/account" className={buttonClasses({ variant: "outline", size: "sm" })}>
          Back to players
        </Link>
      }
    />
    </>
  );
}
