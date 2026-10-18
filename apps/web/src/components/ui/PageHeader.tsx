import type { ReactNode } from "react";

import { PageTitle } from "./PageTitle";

/**
 * Page header: green label, heavy headline and actions.
 * `accent` is the second part of the headline, which goes in green (DESIGN.md §3.4).
 */
export function PageHeader({
  documentTitle,
  title,
  accent,
  eyebrow,
  description,
  actions,
  back,
}: {
  /** The browser tab's title; by default, the headline if it is text. */
  documentTitle?: string;
  title: ReactNode;
  accent?: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: ReactNode;
}) {
  const text = (node: ReactNode) => (typeof node === "string" ? node : "");
  const tabTitle = documentTitle ?? [text(title), text(accent)].filter(Boolean).join(" ");
  return (
    <div className="mb-5 flex animate-rise flex-col gap-4 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
      {tabTitle && <PageTitle>{tabTitle}</PageTitle>}
      <div className="min-w-0">
        {back}
        {eyebrow && <p className="eyebrow mb-4">{eyebrow}</p>}
        <h1 className="headline truncate pb-1 text-2xl text-text sm:text-2xl">
          {title}
          {accent && <span className="text-acid"> {accent}</span>}
        </h1>
        {description && <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2.5">{actions}</div>}
    </div>
  );
}
